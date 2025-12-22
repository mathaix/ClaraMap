"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from clara.agents.design_assistant import session_manager
from clara.agents.simulation_agent import simulation_manager
from clara.api.design_sessions import router as design_sessions_router
from clara.api.projects import router as projects_router
from clara.api.simulation_sessions import router as simulation_sessions_router
from clara.config import settings
from clara.db import Base, engine

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Clara API...")
    # Create tables on startup (dev only - use Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")
    yield
    logger.info("Shutting down Clara API...")
    # Cleanup agent sessions
    await session_manager.close_all()
    logger.info("Design assistant sessions closed")
    # Cleanup simulation sessions
    for session_id in list(simulation_manager._sessions.keys()):
        await simulation_manager.close_session(session_id)
    logger.info("Simulation sessions closed")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS middleware - allow frontend to make requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"→ {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"← {request.method} {request.url.path} {response.status_code}")
    return response


# Include routers
app.include_router(projects_router, prefix="/api/v1")
app.include_router(design_sessions_router, prefix="/api/v1")
app.include_router(simulation_sessions_router, prefix="/api/v1")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}
