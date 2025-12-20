"""Unit tests for ProjectService."""

import pytest
from clara.services.project_service import ProjectService
from clara.db.models import ProjectStatus


class TestProjectService:
    """Tests for ProjectService."""

    @pytest.mark.asyncio
    async def test_create_project(self, db_session):
        """Test creating a project."""
        service = ProjectService(db_session)
        
        project = await service.create(
            name="Test Project",
            description="This is a test project description that is long enough.",
            created_by="user_123",
        )
        
        assert project.id.startswith("proj_")
        assert project.name == "Test Project"
        assert project.status == ProjectStatus.DRAFT.value

    @pytest.mark.asyncio
    async def test_create_project_duplicate_name(self, db_session):
        """Test that duplicate project names are rejected."""
        service = ProjectService(db_session)
        
        await service.create(
            name="Duplicate Name",
            description="This is a test project description that is long enough.",
            created_by="user_123",
        )
        
        with pytest.raises(ValueError, match="already exists"):
            await service.create(
                name="Duplicate Name",
                description="Another project with same name description here.",
                created_by="user_123",
            )

    @pytest.mark.asyncio
    async def test_get_project(self, db_session):
        """Test getting a project by ID."""
        service = ProjectService(db_session)
        
        created = await service.create(
            name="Get Test",
            description="This is a test project description that is long enough.",
            created_by="user_123",
        )
        
        project = await service.get(created.id)
        assert project is not None
        assert project.name == "Get Test"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, db_session):
        """Test getting a non-existent project."""
        service = ProjectService(db_session)
        project = await service.get("proj_nonexistent")
        assert project is None

    @pytest.mark.asyncio
    async def test_list_projects(self, db_session):
        """Test listing projects."""
        service = ProjectService(db_session)
        
        await service.create(
            name="Project One",
            description="This is the first test project description here.",
            created_by="user_123",
        )
        await service.create(
            name="Project Two",
            description="This is the second test project description here.",
            created_by="user_123",
        )
        
        projects, total = await service.list_projects()
        assert total == 2
        assert len(projects) == 2

    @pytest.mark.asyncio
    async def test_list_projects_with_search(self, db_session):
        """Test listing projects with search filter."""
        service = ProjectService(db_session)

        await service.create(
            name="Alpha Project",
            description="This is the alpha test project description here.",
            created_by="user_123",
        )
        await service.create(
            name="Beta Project",
            description="This is the beta test project description here.",
            created_by="user_123",
        )

        projects, total = await service.list_projects(search="Alpha")
        assert total == 1
        assert projects[0].name == "Alpha Project"

    @pytest.mark.asyncio
    async def test_update_project(self, db_session):
        """Test updating a project."""
        service = ProjectService(db_session)
        
        created = await service.create(
            name="Update Test",
            description="This is a test project description that is long enough.",
            created_by="user_123",
        )
        
        updated = await service.update(created.id, name="Updated Name")
        assert updated.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_archive_project(self, db_session):
        """Test archiving a project."""
        service = ProjectService(db_session)
        
        created = await service.create(
            name="Archive Test",
            description="This is a test project description that is long enough.",
            created_by="user_123",
        )
        
        archived = await service.archive(created.id)
        assert archived.status == ProjectStatus.ARCHIVED.value

    @pytest.mark.asyncio
    async def test_delete_project(self, db_session):
        """Test deleting a draft project."""
        service = ProjectService(db_session)
        
        created = await service.create(
            name="Delete Test",
            description="This is a test project description that is long enough.",
            created_by="user_123",
        )
        
        deleted = await service.delete(created.id)
        assert deleted is True
        
        # Verify it's soft deleted
        project = await service.get(created.id)
        assert project is None

    @pytest.mark.asyncio
    async def test_delete_non_draft_project_fails(self, db_session):
        """Test that deleting a non-draft project fails."""
        service = ProjectService(db_session)
        
        created = await service.create(
            name="Active Delete Test",
            description="This is a test project description that is long enough.",
            created_by="user_123",
        )
        await service.update(created.id, status=ProjectStatus.ACTIVE)
        
        with pytest.raises(ValueError, match="Only draft projects"):
            await service.delete(created.id)

    @pytest.mark.asyncio
    async def test_duplicate_project(self, db_session):
        """Test duplicating a project."""
        service = ProjectService(db_session)
        
        original = await service.create(
            name="Original Project",
            description="This is the original project description here.",
            created_by="user_123",
            tags=["tag1", "tag2"],
        )
        
        duplicate = await service.duplicate(original.id, "Copied Project", "user_456")
        
        assert duplicate.id != original.id
        assert duplicate.name == "Copied Project"
        assert duplicate.description == original.description
        assert duplicate.tags == original.tags
        assert duplicate.created_by == "user_456"
        assert duplicate.status == ProjectStatus.DRAFT.value
