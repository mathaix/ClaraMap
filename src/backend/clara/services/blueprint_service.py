"""Blueprint service for CRUD operations."""

import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from clara.db.models import Blueprint, BlueprintVersion
from clara.models.blueprint import InterviewBlueprint


def generate_blueprint_id() -> str:
    """Generate a unique blueprint ID."""
    return f"bp_{secrets.token_hex(8)}"


def generate_version_id() -> str:
    """Generate a unique version ID."""
    return f"bpv_{secrets.token_hex(8)}"


class BlueprintService:
    """Service for managing interview blueprints."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        project_id: str,
        blueprint: InterviewBlueprint,
        created_by: str,
    ) -> Blueprint:
        """Create a new blueprint.

        Args:
            project_id: ID of the project this blueprint belongs to
            blueprint: The InterviewBlueprint Pydantic model
            created_by: ID of the user creating the blueprint

        Returns:
            The created Blueprint ORM model
        """
        blueprint_id = generate_blueprint_id()

        # Extract denormalized fields for querying
        content = blueprint.model_dump(mode="json")

        db_blueprint = Blueprint(
            id=blueprint_id,
            project_id=project_id,
            version=blueprint.metadata.version,
            content=content,
            project_type=blueprint.project.type,
            agent_count=len(blueprint.agents),
            status=blueprint.metadata.status.value,
            created_by=created_by,
        )

        self.db.add(db_blueprint)

        # Create initial version record
        version = BlueprintVersion(
            id=generate_version_id(),
            blueprint_id=blueprint_id,
            version=blueprint.metadata.version,
            content=content,
            change_summary="Initial version",
            created_by=created_by,
        )
        self.db.add(version)

        await self.db.flush()
        return db_blueprint

    async def get_by_id(self, blueprint_id: str) -> Blueprint | None:
        """Get a blueprint by ID."""
        result = await self.db.execute(
            select(Blueprint)
            .options(selectinload(Blueprint.versions))
            .where(Blueprint.id == blueprint_id)
        )
        return result.scalar_one_or_none()

    async def get_by_project(self, project_id: str) -> list[Blueprint]:
        """Get all blueprints for a project."""
        result = await self.db.execute(
            select(Blueprint)
            .where(Blueprint.project_id == project_id)
            .order_by(Blueprint.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_active_for_project(self, project_id: str) -> Blueprint | None:
        """Get the active blueprint for a project."""
        result = await self.db.execute(
            select(Blueprint)
            .where(Blueprint.project_id == project_id)
            .where(Blueprint.status == "active")
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        blueprint_id: str,
        blueprint: InterviewBlueprint,
        updated_by: str,
        change_summary: str | None = None,
    ) -> Blueprint | None:
        """Update a blueprint, creating a new version.

        Args:
            blueprint_id: ID of the blueprint to update
            blueprint: The updated InterviewBlueprint
            updated_by: ID of the user making the update
            change_summary: Optional summary of changes

        Returns:
            The updated Blueprint, or None if not found
        """
        db_blueprint = await self.get_by_id(blueprint_id)
        if not db_blueprint:
            return None

        content = blueprint.model_dump(mode="json")

        # Update the main record
        db_blueprint.version = blueprint.metadata.version
        db_blueprint.content = content
        db_blueprint.project_type = blueprint.project.type
        db_blueprint.agent_count = len(blueprint.agents)
        db_blueprint.status = blueprint.metadata.status.value
        db_blueprint.updated_at = datetime.now(UTC)

        # Create a new version record
        version = BlueprintVersion(
            id=generate_version_id(),
            blueprint_id=blueprint_id,
            version=blueprint.metadata.version,
            content=content,
            change_summary=change_summary,
            created_by=updated_by,
        )
        self.db.add(version)

        await self.db.flush()
        return db_blueprint

    async def update_status(
        self,
        blueprint_id: str,
        status: str,
    ) -> Blueprint | None:
        """Update only the status of a blueprint."""
        db_blueprint = await self.get_by_id(blueprint_id)
        if not db_blueprint:
            return None

        db_blueprint.status = status
        db_blueprint.updated_at = datetime.now(UTC)
        await self.db.flush()
        return db_blueprint

    async def update_quality_score(
        self,
        blueprint_id: str,
        score: float,
    ) -> Blueprint | None:
        """Update the quality score of a blueprint."""
        db_blueprint = await self.get_by_id(blueprint_id)
        if not db_blueprint:
            return None

        db_blueprint.quality_score = score
        await self.db.flush()
        return db_blueprint

    async def delete(self, blueprint_id: str) -> bool:
        """Delete a blueprint and all its versions.

        Returns True if deleted, False if not found.
        """
        db_blueprint = await self.get_by_id(blueprint_id)
        if not db_blueprint:
            return False

        await self.db.delete(db_blueprint)
        await self.db.flush()
        return True

    async def get_versions(self, blueprint_id: str) -> list[BlueprintVersion]:
        """Get all versions of a blueprint."""
        result = await self.db.execute(
            select(BlueprintVersion)
            .where(BlueprintVersion.blueprint_id == blueprint_id)
            .order_by(BlueprintVersion.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_version(self, blueprint_id: str, version: str) -> BlueprintVersion | None:
        """Get a specific version of a blueprint."""
        result = await self.db.execute(
            select(BlueprintVersion)
            .where(BlueprintVersion.blueprint_id == blueprint_id)
            .where(BlueprintVersion.version == version)
        )
        return result.scalar_one_or_none()

    async def restore_version(
        self,
        blueprint_id: str,
        version: str,
        restored_by: str,
    ) -> Blueprint | None:
        """Restore a blueprint to a specific version.

        This creates a new version with the content from the specified version.
        """
        version_record = await self.get_version(blueprint_id, version)
        if not version_record:
            return None

        db_blueprint = await self.get_by_id(blueprint_id)
        if not db_blueprint:
            return None

        # Parse the version content back to a Pydantic model
        restored_blueprint = InterviewBlueprint.model_validate(version_record.content)

        # Increment the version number
        current_parts = db_blueprint.version.split(".")
        new_version = f"{current_parts[0]}.{current_parts[1]}.{int(current_parts[2]) + 1}"

        # Update the blueprint with the restored content
        db_blueprint.version = new_version
        db_blueprint.content = version_record.content
        db_blueprint.project_type = restored_blueprint.project.type
        db_blueprint.agent_count = len(restored_blueprint.agents)
        db_blueprint.updated_at = datetime.now(UTC)

        # Create a version record for the restore
        new_version_record = BlueprintVersion(
            id=generate_version_id(),
            blueprint_id=blueprint_id,
            version=new_version,
            content=version_record.content,
            change_summary=f"Restored from version {version}",
            created_by=restored_by,
        )
        self.db.add(new_version_record)

        await self.db.flush()
        return db_blueprint

    def to_pydantic(self, db_blueprint: Blueprint) -> InterviewBlueprint:
        """Convert a database Blueprint to a Pydantic InterviewBlueprint."""
        return InterviewBlueprint.model_validate(db_blueprint.content)
