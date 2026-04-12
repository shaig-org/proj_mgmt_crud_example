"""Tests for Stub Entity API endpoints - template for creating real API tests."""

from fastapi.testclient import TestClient

# Explicitly import pytest fixtures as per project rules
from tests.conftest import client  # noqa: F401


class TestStubEntityAPIEndpoints:
    """Test all stub entity API endpoints for CRUD operations - template for real API tests."""

    def test_create_stub_entity(self, client: TestClient) -> None:
        """Test creating a stub entity via API."""
        stub_entity_data = {"name": "Test Stub Entity", "description": "A test stub entity"}
        response = client.post("/stub_entities", json=stub_entity_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Stub Entity"
        assert data["description"] == "A test stub entity"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_stub_entity_without_description(self, client: TestClient) -> None:
        """Test creating a stub entity without description."""
        stub_entity_data = {"name": "Stub Entity No Description"}
        response = client.post("/stub_entities", json=stub_entity_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Stub Entity No Description"
        assert data["description"] is None

    def test_get_stub_entity_by_id(self, client: TestClient) -> None:
        """Test retrieving a stub entity by ID via API."""
        # Create a stub entity first
        stub_entity_data = {"name": "Retrievable Stub Entity", "description": "Can be retrieved"}
        create_response = client.post("/stub_entities", json=stub_entity_data)
        created_stub_entity = create_response.json()
        stub_entity_id = created_stub_entity["id"]

        # Get the stub entity
        response = client.get(f"/stub_entities/{stub_entity_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == stub_entity_id
        assert data["name"] == "Retrievable Stub Entity"
        assert data["description"] == "Can be retrieved"

    def test_get_stub_entity_by_id_not_found(self, client: TestClient) -> None:
        """Test getting a non-existent stub entity returns 404."""
        response = client.get("/stub_entities/non-existent-id")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Stub entity not found"

    def test_get_all_stub_entities_empty(self, client: TestClient) -> None:
        """Test getting all stub entities when database is empty."""
        response = client.get("/stub_entities")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_get_all_stub_entities_with_data(self, client: TestClient) -> None:
        """Test getting all stub entities when database has data."""
        # Create multiple stub entities
        stub_entity1_data = {"name": "Stub Entity 1", "description": "First stub entity"}
        stub_entity2_data = {"name": "Stub Entity 2", "description": "Second stub entity"}
        client.post("/stub_entities", json=stub_entity1_data)
        client.post("/stub_entities", json=stub_entity2_data)

        # Get all stub entities
        response = client.get("/stub_entities")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        stub_entity_names = {stub_entity["name"] for stub_entity in data}
        assert stub_entity_names == {"Stub Entity 1", "Stub Entity 2"}

    def test_delete_stub_entity(self, client: TestClient) -> None:
        """Test deleting a stub entity via API."""
        # Create a stub entity first
        stub_entity_data = {"name": "Delete Me", "description": "Will be deleted"}
        create_response = client.post("/stub_entities", json=stub_entity_data)
        created_stub_entity = create_response.json()
        stub_entity_id = created_stub_entity["id"]

        # Delete the stub entity
        response = client.delete(f"/stub_entities/{stub_entity_id}")

        assert response.status_code == 204
        assert response.content == b""

        # Verify it's gone
        get_response = client.get(f"/stub_entities/{stub_entity_id}")
        assert get_response.status_code == 404

    def test_delete_stub_entity_not_found(self, client: TestClient) -> None:
        """Test deleting a non-existent stub entity returns 404."""
        response = client.delete("/stub_entities/non-existent-id")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Stub entity not found"


class TestStubEntityAPICRUDWorkflow:
    """Test complete CRUD workflow for stub entities - template for real workflow tests."""

    def test_complete_stub_entity_crud_workflow(self, client: TestClient) -> None:
        """Test a complete CRUD workflow for a stub entity."""
        # 1. Create a stub entity
        stub_entity_data = {"name": "Workflow Stub Entity", "description": "Full CRUD test"}
        create_response = client.post("/stub_entities", json=stub_entity_data)
        assert create_response.status_code == 201
        created_stub_entity = create_response.json()
        stub_entity_id = created_stub_entity["id"]

        # 2. Read the stub entity
        get_response = client.get(f"/stub_entities/{stub_entity_id}")
        assert get_response.status_code == 200
        stub_entity = get_response.json()
        assert stub_entity["name"] == "Workflow Stub Entity"
        assert stub_entity["description"] == "Full CRUD test"

        # 3. Verify it appears in list
        list_response = client.get("/stub_entities")
        assert list_response.status_code == 200
        stub_entities = list_response.json()
        assert len(stub_entities) == 1
        assert stub_entities[0]["id"] == stub_entity_id

        # 4. Delete the stub entity
        delete_response = client.delete(f"/stub_entities/{stub_entity_id}")
        assert delete_response.status_code == 204

        # 5. Verify deletion
        final_get_response = client.get(f"/stub_entities/{stub_entity_id}")
        assert final_get_response.status_code == 404

        # 6. Verify list is empty
        final_list_response = client.get("/stub_entities")
        assert final_list_response.status_code == 200
        final_stub_entities = final_list_response.json()
        assert len(final_stub_entities) == 0
