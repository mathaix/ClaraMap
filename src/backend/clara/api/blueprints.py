"""Blueprint API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from clara.db.session import get_db
from clara.models.blueprint import InterviewBlueprint
from clara.services.blueprint_service import BlueprintService
from clara.services.blueprint_validation import validate_blueprint

router = APIRouter(prefix="/blueprints", tags=["blueprints"])


class BlueprintCreate(BaseModel):
    """Request model for creating a blueprint."""

    project_id: str
    blueprint: InterviewBlueprint


class BlueprintUpdate(BaseModel):
    """Request model for updating a blueprint."""

    blueprint: InterviewBlueprint
    change_summary: str | None = None


class BlueprintStatusUpdate(BaseModel):
    """Request model for updating blueprint status."""

    status: str = Field(..., pattern=r"^(draft|review|approved|active|archived)$")


class BlueprintSummary(BaseModel):
    """Summary response model for blueprint lists."""

    id: str
    project_id: str
    version: str
    status: str
    project_type: str | None
    agent_count: int
    quality_score: float | None
    created_at: str
    updated_at: str


class BlueprintResponse(BaseModel):
    """Response model for a full blueprint."""

    id: str
    project_id: str
    version: str
    status: str
    project_type: str | None
    agent_count: int
    quality_score: float | None
    content: InterviewBlueprint
    created_at: str
    updated_at: str


class BlueprintVersionSummary(BaseModel):
    """Summary of a blueprint version."""

    id: str
    version: str
    change_summary: str | None
    created_at: str
    created_by: str


class ValidationIssueResponse(BaseModel):
    """A single validation issue."""

    severity: str
    code: str
    message: str
    path: str
    agent_id: str | None


class QualityDimensionResponse(BaseModel):
    """Score for a quality dimension."""

    name: str
    score: float
    weight: float
    weighted_score: float
    issues: list[str]


class ValidationResponse(BaseModel):
    """Full validation result."""

    is_valid: bool
    error_count: int
    warning_count: int
    issues: list[ValidationIssueResponse]
    quality_score: float
    quality_dimensions: list[QualityDimensionResponse]
    ready_for_deployment: bool


class ValidateBlueprintRequest(BaseModel):
    """Request to validate a blueprint."""

    blueprint: InterviewBlueprint


@router.post("", response_model=BlueprintResponse, status_code=status.HTTP_201_CREATED)
async def create_blueprint(
    request: BlueprintCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new interview blueprint."""
    # TODO: Get user from auth context
    created_by = "user_system"

    service = BlueprintService(db)
    db_blueprint = await service.create(
        project_id=request.project_id,
        blueprint=request.blueprint,
        created_by=created_by,
    )

    return BlueprintResponse(
        id=db_blueprint.id,
        project_id=db_blueprint.project_id,
        version=db_blueprint.version,
        status=db_blueprint.status,
        project_type=db_blueprint.project_type,
        agent_count=db_blueprint.agent_count,
        quality_score=db_blueprint.quality_score,
        content=service.to_pydantic(db_blueprint),
        created_at=db_blueprint.created_at.isoformat(),
        updated_at=db_blueprint.updated_at.isoformat()
        if db_blueprint.updated_at
        else db_blueprint.created_at.isoformat(),
    )


@router.get("/{blueprint_id}", response_model=BlueprintResponse)
async def get_blueprint(
    blueprint_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a blueprint by ID."""
    service = BlueprintService(db)
    db_blueprint = await service.get_by_id(blueprint_id)

    if not db_blueprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blueprint {blueprint_id} not found",
        )

    return BlueprintResponse(
        id=db_blueprint.id,
        project_id=db_blueprint.project_id,
        version=db_blueprint.version,
        status=db_blueprint.status,
        project_type=db_blueprint.project_type,
        agent_count=db_blueprint.agent_count,
        quality_score=db_blueprint.quality_score,
        content=service.to_pydantic(db_blueprint),
        created_at=db_blueprint.created_at.isoformat(),
        updated_at=db_blueprint.updated_at.isoformat()
        if db_blueprint.updated_at
        else db_blueprint.created_at.isoformat(),
    )


@router.get("/project/{project_id}", response_model=list[BlueprintSummary])
async def get_blueprints_by_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all blueprints for a project."""
    service = BlueprintService(db)
    blueprints = await service.get_by_project(project_id)

    return [
        BlueprintSummary(
            id=bp.id,
            project_id=bp.project_id,
            version=bp.version,
            status=bp.status,
            project_type=bp.project_type,
            agent_count=bp.agent_count,
            quality_score=bp.quality_score,
            created_at=bp.created_at.isoformat(),
            updated_at=bp.updated_at.isoformat() if bp.updated_at else bp.created_at.isoformat(),
        )
        for bp in blueprints
    ]


@router.put("/{blueprint_id}", response_model=BlueprintResponse)
async def update_blueprint(
    blueprint_id: str,
    request: BlueprintUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a blueprint."""
    # TODO: Get user from auth context
    updated_by = "user_system"

    service = BlueprintService(db)
    db_blueprint = await service.update(
        blueprint_id=blueprint_id,
        blueprint=request.blueprint,
        updated_by=updated_by,
        change_summary=request.change_summary,
    )

    if not db_blueprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blueprint {blueprint_id} not found",
        )

    return BlueprintResponse(
        id=db_blueprint.id,
        project_id=db_blueprint.project_id,
        version=db_blueprint.version,
        status=db_blueprint.status,
        project_type=db_blueprint.project_type,
        agent_count=db_blueprint.agent_count,
        quality_score=db_blueprint.quality_score,
        content=service.to_pydantic(db_blueprint),
        created_at=db_blueprint.created_at.isoformat(),
        updated_at=db_blueprint.updated_at.isoformat()
        if db_blueprint.updated_at
        else db_blueprint.created_at.isoformat(),
    )


@router.patch("/{blueprint_id}/status", response_model=BlueprintSummary)
async def update_blueprint_status(
    blueprint_id: str,
    request: BlueprintStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update the status of a blueprint."""
    service = BlueprintService(db)
    db_blueprint = await service.update_status(blueprint_id, request.status)

    if not db_blueprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blueprint {blueprint_id} not found",
        )

    return BlueprintSummary(
        id=db_blueprint.id,
        project_id=db_blueprint.project_id,
        version=db_blueprint.version,
        status=db_blueprint.status,
        project_type=db_blueprint.project_type,
        agent_count=db_blueprint.agent_count,
        quality_score=db_blueprint.quality_score,
        created_at=db_blueprint.created_at.isoformat(),
        updated_at=db_blueprint.updated_at.isoformat()
        if db_blueprint.updated_at
        else db_blueprint.created_at.isoformat(),
    )


@router.delete("/{blueprint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blueprint(
    blueprint_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a blueprint and all its versions."""
    service = BlueprintService(db)
    deleted = await service.delete(blueprint_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blueprint {blueprint_id} not found",
        )


@router.get("/{blueprint_id}/versions", response_model=list[BlueprintVersionSummary])
async def get_blueprint_versions(
    blueprint_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all versions of a blueprint."""
    service = BlueprintService(db)
    versions = await service.get_versions(blueprint_id)

    if not versions:
        # Check if blueprint exists
        bp = await service.get_by_id(blueprint_id)
        if not bp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Blueprint {blueprint_id} not found",
            )

    return [
        BlueprintVersionSummary(
            id=v.id,
            version=v.version,
            change_summary=v.change_summary,
            created_at=v.created_at.isoformat(),
            created_by=v.created_by,
        )
        for v in versions
    ]


@router.post("/{blueprint_id}/versions/{version}/restore", response_model=BlueprintResponse)
async def restore_blueprint_version(
    blueprint_id: str,
    version: str,
    db: AsyncSession = Depends(get_db),
):
    """Restore a blueprint to a specific version."""
    # TODO: Get user from auth context
    restored_by = "user_system"

    service = BlueprintService(db)
    db_blueprint = await service.restore_version(
        blueprint_id=blueprint_id,
        version=version,
        restored_by=restored_by,
    )

    if not db_blueprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blueprint {blueprint_id} or version {version} not found",
        )

    return BlueprintResponse(
        id=db_blueprint.id,
        project_id=db_blueprint.project_id,
        version=db_blueprint.version,
        status=db_blueprint.status,
        project_type=db_blueprint.project_type,
        agent_count=db_blueprint.agent_count,
        quality_score=db_blueprint.quality_score,
        content=service.to_pydantic(db_blueprint),
        created_at=db_blueprint.created_at.isoformat(),
        updated_at=db_blueprint.updated_at.isoformat()
        if db_blueprint.updated_at
        else db_blueprint.created_at.isoformat(),
    )


@router.post("/validate", response_model=ValidationResponse)
async def validate_blueprint_endpoint(
    request: ValidateBlueprintRequest,
):
    """Validate a blueprint and return quality score.

    This endpoint validates:
    - Cross-reference integrity (question IDs, entity references, goal references)
    - Structural completeness
    - Quality scoring with weighted dimensions

    Quality Score Weights:
    - Completeness: 25%
    - Coherence: 20%
    - Question Quality: 20%
    - Extraction Coverage: 20%
    - Persona Quality: 15%

    A score of 70+ is considered ready for deployment.
    """
    result = validate_blueprint(request.blueprint)

    return ValidationResponse(
        is_valid=result.is_valid,
        error_count=result.error_count,
        warning_count=result.warning_count,
        issues=[
            ValidationIssueResponse(
                severity=issue.severity.value,
                code=issue.code,
                message=issue.message,
                path=issue.path,
                agent_id=issue.agent_id,
            )
            for issue in result.issues
        ],
        quality_score=result.quality_score,
        quality_dimensions=[
            QualityDimensionResponse(
                name=dim.name,
                score=dim.score,
                weight=dim.weight,
                weighted_score=dim.weighted_score,
                issues=dim.issues,
            )
            for dim in result.quality_dimensions
        ],
        ready_for_deployment=result.ready_for_deployment,
    )


@router.post("/{blueprint_id}/validate", response_model=ValidationResponse)
async def validate_stored_blueprint(
    blueprint_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Validate an existing stored blueprint and return quality score."""
    service = BlueprintService(db)
    db_blueprint = await service.get_by_id(blueprint_id)

    if not db_blueprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blueprint {blueprint_id} not found",
        )

    blueprint = service.to_pydantic(db_blueprint)
    result = validate_blueprint(blueprint)

    # Update quality score in database
    await service.update_quality_score(blueprint_id, result.quality_score)

    return ValidationResponse(
        is_valid=result.is_valid,
        error_count=result.error_count,
        warning_count=result.warning_count,
        issues=[
            ValidationIssueResponse(
                severity=issue.severity.value,
                code=issue.code,
                message=issue.message,
                path=issue.path,
                agent_id=issue.agent_id,
            )
            for issue in result.issues
        ],
        quality_score=result.quality_score,
        quality_dimensions=[
            QualityDimensionResponse(
                name=dim.name,
                score=dim.score,
                weight=dim.weight,
                weighted_score=dim.weighted_score,
                issues=dim.issues,
            )
            for dim in result.quality_dimensions
        ],
        ready_for_deployment=result.ready_for_deployment,
    )
