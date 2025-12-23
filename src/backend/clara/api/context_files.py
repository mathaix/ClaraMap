"""Context Files API endpoints.

Provides file upload/download/delete endpoints for agent context files.
Files are linked to InterviewAgent (canonical source of truth) and sandboxed per project.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from clara.config import settings
from clara.db.models import AgentContextFile, ContextFileStatus, InterviewAgent
from clara.db.session import get_db
from clara.services.file_service import FileUploadService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/context-files", tags=["context-files"])

# Instantiate upload service
file_service = FileUploadService()


class ContextFileResponse(BaseModel):
    """Response model for a context file."""
    id: str
    name: str  # original filename
    type: str  # mime type
    size: int
    status: str
    extraction_status: str | None
    uploaded_at: str


class ContextFileListResponse(BaseModel):
    """Response model for listing context files."""
    files: list[ContextFileResponse]
    total: int


class UploadResponse(BaseModel):
    """Response after uploading a file."""
    success: bool
    file: ContextFileResponse | None = None
    error: str | None = None


@router.post("/agents/{agent_id}/upload", response_model=UploadResponse)
async def upload_context_file(
    agent_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
) -> UploadResponse:
    """Upload a context file for an agent.

    Files are validated for:
    - Allowed file types (extension + content verification)
    - Maximum file size
    - Security (path traversal, dangerous content)

    The file content is extracted for use in agent context.
    """
    # Verify agent exists and get project_id
    result = await db.execute(
        select(InterviewAgent).where(InterviewAgent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    project_id = agent.project_id

    # Check file count limit
    count_result = await db.execute(
        select(func.count(AgentContextFile.id))
        .where(AgentContextFile.agent_id == agent_id)
        .where(AgentContextFile.deleted_at.is_(None))
    )
    current_count = count_result.scalar() or 0
    if current_count >= settings.max_files_per_agent:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.max_files_per_agent} files allowed per agent"
        )

    # Read file content
    try:
        content = await file.read()
    except Exception:
        logger.exception("Failed to read uploaded file")
        return UploadResponse(success=False, error="Failed to read file")

    # Process upload
    upload_result = await file_service.upload_file(
        file_content=content,
        filename=file.filename or "unnamed",
        project_id=project_id,
        agent_index=0  # Not used for path, keeping for compatibility
    )

    if not upload_result.success:
        return UploadResponse(success=False, error=upload_result.error_message)

    # Create database record
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    context_file = AgentContextFile(
        id=upload_result.file_id,
        agent_id=agent_id,
        original_filename=file.filename or "unnamed",
        stored_filename=upload_result.stored_filename,
        file_extension=ext,
        mime_type=upload_result.mime_type,
        file_size=upload_result.file_size,
        storage_path=upload_result.storage_path,
        extracted_text=upload_result.extracted_text,
        extraction_status=upload_result.extraction_status,
        checksum=upload_result.checksum,
        status=ContextFileStatus.READY.value,
    )
    db.add(context_file)
    await db.commit()

    return UploadResponse(
        success=True,
        file=ContextFileResponse(
            id=upload_result.file_id,
            name=file.filename or "unnamed",
            type=upload_result.mime_type,
            size=upload_result.file_size,
            status=ContextFileStatus.READY.value,
            extraction_status=upload_result.extraction_status,
            uploaded_at=datetime.now(UTC).isoformat(),
        )
    )


@router.get("/agents/{agent_id}", response_model=ContextFileListResponse)
async def list_context_files(
    agent_id: str,
    db: AsyncSession = Depends(get_db)
) -> ContextFileListResponse:
    """List all context files for an agent."""
    # Verify agent exists
    result = await db.execute(
        select(InterviewAgent).where(InterviewAgent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get files
    result = await db.execute(
        select(AgentContextFile)
        .where(AgentContextFile.agent_id == agent_id)
        .where(AgentContextFile.deleted_at.is_(None))
        .order_by(AgentContextFile.created_at.desc())
    )
    files = result.scalars().all()

    return ContextFileListResponse(
        files=[
            ContextFileResponse(
                id=f.id,
                name=f.original_filename,
                type=f.mime_type,
                size=f.file_size,
                status=f.status,
                extraction_status=f.extraction_status,
                uploaded_at=f.created_at.isoformat() if f.created_at else "",
            )
            for f in files
        ],
        total=len(files)
    )


@router.delete("/agents/{agent_id}/files/{file_id}")
async def delete_context_file(
    agent_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a context file (soft delete)."""
    # Verify agent exists
    result = await db.execute(
        select(InterviewAgent).where(InterviewAgent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Find file
    result = await db.execute(
        select(AgentContextFile)
        .where(AgentContextFile.id == file_id)
        .where(AgentContextFile.agent_id == agent_id)
    )
    context_file = result.scalar_one_or_none()
    if not context_file:
        raise HTTPException(status_code=404, detail="File not found")

    # Soft delete
    context_file.deleted_at = datetime.now(UTC)
    context_file.status = ContextFileStatus.FAILED.value
    context_file.status_message = "Deleted by user"

    await db.commit()

    return {"status": "deleted", "file_id": file_id}


@router.get("/agents/{agent_id}/files/{file_id}/content")
async def get_extracted_content(
    agent_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get the extracted text content of a file for agent context."""
    # Find file
    result = await db.execute(
        select(AgentContextFile)
        .where(AgentContextFile.id == file_id)
        .where(AgentContextFile.agent_id == agent_id)
        .where(AgentContextFile.deleted_at.is_(None))
    )
    context_file = result.scalar_one_or_none()
    if not context_file:
        raise HTTPException(status_code=404, detail="File not found")

    return {
        "file_id": file_id,
        "filename": context_file.original_filename,
        "extraction_status": context_file.extraction_status,
        "content": context_file.extracted_text,
    }
