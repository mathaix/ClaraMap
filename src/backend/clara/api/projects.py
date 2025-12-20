"""Projects API router."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from clara.db import get_db
from clara.db.models import ProjectStatus
from clara.services.project_service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


class TimelineValidationMixin:
    """Mixin for timeline date validation."""

    @model_validator(mode="after")
    def validate_timeline(self):
        if self.timeline_start and self.timeline_end:
            if self.timeline_end <= self.timeline_start:
                raise ValueError("timeline_end must be after timeline_start")
        return self


# Request/Response models
class ProjectCreate(TimelineValidationMixin, BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=2000)
    timeline_start: datetime | None = None
    timeline_end: datetime | None = None
    tags: list[str] = Field(default_factory=list)


class ProjectUpdate(TimelineValidationMixin, BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, min_length=1, max_length=2000)
    status: ProjectStatus | None = None
    timeline_start: datetime | None = None
    timeline_end: datetime | None = None
    tags: list[str] | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str
    timeline_start: datetime | None
    timeline_end: datetime | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    created_by: str

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
    limit: int
    offset: int


class ProjectDuplicate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)


# Endpoints
@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new project."""
    logger.info(f"Creating project: name={data.name}, tags={data.tags}")
    service = ProjectService(db)
    # TODO: Get created_by from authenticated user
    created_by = "user_placeholder"

    try:
        project = await service.create(
            name=data.name,
            description=data.description,
            created_by=created_by,
            timeline_start=data.timeline_start,
            timeline_end=data.timeline_end,
            tags=data.tags,
        )
        logger.info(f"Created project: id={project.id}")
        return project
    except ValueError as e:
        logger.warning(f"Failed to create project: {e}")
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    status: ProjectStatus | None = None,
    search: str | None = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List projects with optional filters."""
    service = ProjectService(db)
    # TODO: Filter by authenticated user's access
    projects, total = await service.list_projects(
        status=status,
        search=search,
        limit=limit,
        offset=offset,
    )
    return ProjectListResponse(
        items=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a project by ID."""
    service = ProjectService(db)
    project = await service.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a project."""
    service = ProjectService(db)
    try:
        project = await service.update(
            project_id=project_id,
            name=data.name,
            description=data.description,
            status=data.status,
            timeline_start=data.timeline_start,
            timeline_end=data.timeline_end,
            tags=data.tags,
        )
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Archive a project."""
    service = ProjectService(db)
    project = await service.archive(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a project (soft delete, draft only)."""
    service = ProjectService(db)
    try:
        deleted = await service.delete(project_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Project not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/duplicate", response_model=ProjectResponse, status_code=201)
async def duplicate_project(
    project_id: str,
    data: ProjectDuplicate | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Duplicate a project configuration."""
    service = ProjectService(db)
    # TODO: Get created_by from authenticated user
    created_by = "user_placeholder"

    # Get source project to generate default name if not provided
    source = await service.get(project_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source project not found")

    new_name = data.name if data and data.name else f"{source.name} (Copy)"

    try:
        project = await service.duplicate(project_id, new_name, created_by)
        if not project:
            raise HTTPException(status_code=404, detail="Source project not found")
        return project
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
