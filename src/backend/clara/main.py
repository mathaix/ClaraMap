"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from clara.api.projects import router as projects_router
from clara.config import settings
from clara.db import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Create tables on startup (dev only - use Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# Include routers
app.include_router(projects_router, prefix="/api/v1")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}
