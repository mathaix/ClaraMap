"""Migration script to convert embedded blueprint agents to InterviewAgent entities.

This script migrates agents stored in DesignSession.blueprint_state.agents (JSON)
to the new interview_agents table as first-class entities.

Usage:
    cd src/backend
    uv run python -m clara.db.migrations.migrate_agents_to_entities

The migration is idempotent - running it multiple times is safe.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from clara.config import settings
from clara.db.models import (
    Base,
    DesignSession,
    InterviewAgent,
    InterviewAgentStatus,
    Project,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_session_agents(
    db: AsyncSession,
    session: DesignSession,
    project: Project,
) -> list[InterviewAgent]:
    """Migrate agents from a design session's blueprint_state to InterviewAgent entities.

    Args:
        db: Database session
        session: The design session containing embedded agents
        project: The project the agents belong to

    Returns:
        List of created InterviewAgent entities
    """
    created_agents = []
    blueprint_state = session.blueprint_state or {}
    agents_data = blueprint_state.get("agents", [])

    if not agents_data:
        logger.info(f"  Session {session.id}: No agents to migrate")
        return created_agents

    for i, agent_data in enumerate(agents_data):
        # Check if this agent was already migrated (by matching name and session)
        existing = await db.execute(
            select(InterviewAgent)
            .where(InterviewAgent.design_session_id == session.id)
            .where(InterviewAgent.name == agent_data.get("name", f"Agent {i + 1}"))
        )
        if existing.scalar_one_or_none():
            logger.info(
                f"  Session {session.id}: Agent '{agent_data.get('name')}' already migrated"
            )
            continue

        # Create new InterviewAgent entity
        agent = InterviewAgent(
            id=f"agent_{uuid.uuid4().hex[:16]}",
            project_id=project.id,
            name=agent_data.get("name", f"Agent {i + 1}"),
            persona=agent_data.get("persona"),
            topics=agent_data.get("topics", []),
            tone=agent_data.get("tone"),
            system_prompt=agent_data.get("system_prompt"),
            capabilities=session.agent_capabilities,
            status=InterviewAgentStatus.DRAFT.value,
            design_session_id=session.id,
            created_at=session.created_at or datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        db.add(agent)
        created_agents.append(agent)
        logger.info(f"  Session {session.id}: Created agent '{agent.name}' ({agent.id})")

    return created_agents


async def run_migration():
    """Run the agent migration."""
    logger.info("Starting agent migration...")
    logger.info(f"Database URL: {settings.database_url}")

    engine = create_async_engine(settings.database_url, echo=False)
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as db:
        # Get all design sessions with their projects
        result = await db.execute(
            select(DesignSession).order_by(DesignSession.created_at)
        )
        sessions = result.scalars().all()

        logger.info(f"Found {len(sessions)} design sessions to process")

        total_agents_created = 0

        for session in sessions:
            logger.info(f"Processing session {session.id} (project: {session.project_id})")

            # Get the project
            project_result = await db.execute(
                select(Project).where(Project.id == session.project_id)
            )
            project = project_result.scalar_one_or_none()

            if not project:
                logger.warning(
                    f"  Session {session.id}: Project {session.project_id} not found, skipping"
                )
                continue

            created = await migrate_session_agents(db, session, project)
            total_agents_created += len(created)

        await db.commit()
        logger.info(f"Migration complete. Created {total_agents_created} agent entities.")


if __name__ == "__main__":
    asyncio.run(run_migration())
