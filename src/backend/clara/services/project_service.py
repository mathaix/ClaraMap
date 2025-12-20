"""Project service - business logic for project operations."""

from datetime import UTC, datetime

import ulid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from clara.db.models import InterviewSession, Project, ProjectStatus


class ProjectService:
    """Service for project CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        name: str,
        description: str,
        created_by: str,
        timeline_start: datetime | None = None,
        timeline_end: datetime | None = None,
        tags: list[str] | None = None,
    ) -> Project:
        """Create a new project."""
        # Check for duplicate name
        existing = await self.db.execute(
            select(Project).where(Project.name == name, Project.deleted_at.is_(None))
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Project with name '{name}' already exists")

        project = Project(
            id=f"proj_{ulid.new().str.lower()}",
            name=name,
            description=description,
            created_by=created_by,
            timeline_start=timeline_start,
            timeline_end=timeline_end,
            tags=tags or [],
            status=ProjectStatus.DRAFT.value,
        )
        self.db.add(project)
        await self.db.flush()
        return project

    async def get(self, project_id: str) -> Project | None:
        """Get a project by ID."""
        result = await self.db.execute(
            select(Project)
            .where(Project.id == project_id, Project.deleted_at.is_(None))
            .options(selectinload(Project.interview_sessions))
        )
        return result.scalar_one_or_none()

    async def list_projects(
        self,
        created_by: str | None = None,
        status: ProjectStatus | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Project], int]:
        """List projects with optional filters."""
        query = select(Project).where(Project.deleted_at.is_(None))

        if created_by:
            query = query.where(Project.created_by == created_by)
        if status:
            query = query.where(Project.status == status.value)
        if search:
            query = query.where(
                Project.name.ilike(f"%{search}%") | Project.description.ilike(f"%{search}%")
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results
        query = query.order_by(Project.updated_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        projects = result.scalars().all()

        return [p for p in projects], total

    async def update(
        self,
        project_id: str,
        name: str | None = None,
        description: str | None = None,
        status: ProjectStatus | None = None,
        timeline_start: datetime | None = None,
        timeline_end: datetime | None = None,
        tags: list[str] | None = None,
    ) -> Project | None:
        """Update a project."""
        project = await self.get(project_id)
        if not project:
            return None

        if name is not None:
            # Check for duplicate name
            existing = await self.db.execute(
                select(Project).where(
                    Project.name == name,
                    Project.id != project_id,
                    Project.deleted_at.is_(None),
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"Project with name '{name}' already exists")
            project.name = name

        if description is not None:
            project.description = description
        if status is not None:
            project.status = status.value
        if timeline_start is not None:
            project.timeline_start = timeline_start
        if timeline_end is not None:
            project.timeline_end = timeline_end
        if tags is not None:
            project.tags = tags

        await self.db.flush()
        await self.db.refresh(project)
        return project

    async def archive(self, project_id: str) -> Project | None:
        """Archive a project."""
        return await self.update(project_id, status=ProjectStatus.ARCHIVED)

    async def delete(self, project_id: str) -> bool:
        """Soft delete a project (only if in draft status with no interviews)."""
        project = await self.get(project_id)
        if not project:
            return False

        # Check if project has interviews
        session_count = await self.db.execute(
            select(func.count()).where(InterviewSession.project_id == project_id)
        )
        if (session_count.scalar() or 0) > 0:
            raise ValueError("Cannot delete project with interview sessions. Archive instead.")

        if project.status != ProjectStatus.DRAFT.value:
            raise ValueError("Only draft projects can be deleted. Archive instead.")

        project.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    async def duplicate(self, project_id: str, new_name: str, created_by: str) -> Project | None:
        """Duplicate a project configuration."""
        source = await self.get(project_id)
        if not source:
            return None

        return await self.create(
            name=new_name,
            description=source.description,
            created_by=created_by,
            timeline_start=source.timeline_start,
            timeline_end=source.timeline_end,
            tags=source.tags.copy() if source.tags else [],
        )
