"""Integration tests for Projects API."""

import pytest


class TestProjectsAPI:
    """Integration tests for /api/v1/projects endpoints."""

    @pytest.mark.asyncio
    async def test_create_project(self, client):
        """Test POST /api/v1/projects."""
        response = await client.post(
            "/api/v1/projects",
            json={
                "name": "Test Project",
                "description": "This is a test project description that is long enough.",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Project"
        assert data["id"].startswith("proj_")
        assert data["status"] == "draft"

    @pytest.mark.asyncio
    async def test_create_project_validation_error(self, client):
        """Test POST /api/v1/projects with invalid data."""
        response = await client.post(
            "/api/v1/projects",
            json={
                "name": "X",
                "description": "Too short",  # Less than 20 chars
            },
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_project_duplicate_name(self, client):
        """Test POST /api/v1/projects with duplicate name."""
        await client.post(
            "/api/v1/projects",
            json={
                "name": "Duplicate Name",
                "description": "This is a test project description that is long enough.",
            },
        )
        
        response = await client.post(
            "/api/v1/projects",
            json={
                "name": "Duplicate Name",
                "description": "Another project with the same name here for testing.",
            },
        )
        
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_list_projects(self, client):
        """Test GET /api/v1/projects."""
        # Create some projects
        await client.post(
            "/api/v1/projects",
            json={
                "name": "Project One",
                "description": "This is the first test project description here.",
            },
        )
        await client.post(
            "/api/v1/projects",
            json={
                "name": "Project Two",
                "description": "This is the second test project description here.",
            },
        )
        
        response = await client.get("/api/v1/projects")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_projects_with_search(self, client):
        """Test GET /api/v1/projects with search."""
        await client.post(
            "/api/v1/projects",
            json={
                "name": "Alpha Project",
                "description": "This is the alpha test project description here.",
            },
        )
        await client.post(
            "/api/v1/projects",
            json={
                "name": "Beta Project",
                "description": "This is the beta test project description here.",
            },
        )
        
        response = await client.get("/api/v1/projects", params={"search": "Alpha"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Alpha Project"

    @pytest.mark.asyncio
    async def test_get_project(self, client):
        """Test GET /api/v1/projects/{id}."""
        create_response = await client.post(
            "/api/v1/projects",
            json={
                "name": "Get Test Project",
                "description": "This is a test project description that is long enough.",
            },
        )
        project_id = create_response.json()["id"]
        
        response = await client.get(f"/api/v1/projects/{project_id}")
        
        assert response.status_code == 200
        assert response.json()["name"] == "Get Test Project"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, client):
        """Test GET /api/v1/projects/{id} with non-existent ID."""
        response = await client.get("/api/v1/projects/proj_nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_project(self, client):
        """Test PATCH /api/v1/projects/{id}."""
        create_response = await client.post(
            "/api/v1/projects",
            json={
                "name": "Update Test",
                "description": "This is a test project description that is long enough.",
            },
        )
        project_id = create_response.json()["id"]
        
        response = await client.patch(
            f"/api/v1/projects/{project_id}",
            json={"name": "Updated Name"},
        )
        
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_archive_project(self, client):
        """Test POST /api/v1/projects/{id}/archive."""
        create_response = await client.post(
            "/api/v1/projects",
            json={
                "name": "Archive Test",
                "description": "This is a test project description that is long enough.",
            },
        )
        project_id = create_response.json()["id"]
        
        response = await client.post(f"/api/v1/projects/{project_id}/archive")
        
        assert response.status_code == 200
        assert response.json()["status"] == "archived"

    @pytest.mark.asyncio
    async def test_delete_project(self, client):
        """Test DELETE /api/v1/projects/{id}."""
        create_response = await client.post(
            "/api/v1/projects",
            json={
                "name": "Delete Test",
                "description": "This is a test project description that is long enough.",
            },
        )
        project_id = create_response.json()["id"]
        
        response = await client.delete(f"/api/v1/projects/{project_id}")
        assert response.status_code == 204
        
        # Verify deleted
        get_response = await client.get(f"/api/v1/projects/{project_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_duplicate_project(self, client):
        """Test POST /api/v1/projects/{id}/duplicate."""
        create_response = await client.post(
            "/api/v1/projects",
            json={
                "name": "Original Project",
                "description": "This is the original project description here.",
                "tags": ["tag1", "tag2"],
            },
        )
        project_id = create_response.json()["id"]
        
        response = await client.post(
            f"/api/v1/projects/{project_id}/duplicate",
            json={"name": "Copied Project"},
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Copied Project"
        assert data["tags"] == ["tag1", "tag2"]
        assert data["status"] == "draft"
