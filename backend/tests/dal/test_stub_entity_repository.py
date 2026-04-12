"""Tests for the StubEntityRepository class - template for creating real repository tests."""

from project_management_crud_example.dal.sqlite.repository import StubEntityRepository
from project_management_crud_example.domain_models import StubEntityCreateCommand, StubEntityData

# Explicitly import pytest fixtures as per project rules
from tests.conftest import test_stub_entity_repo  # noqa: F401


class TestStubEntityRepository:
    """Test the StubEntityRepository CRUD operations - template for real repository tests."""

    def test_create_stub_entity(self, test_stub_entity_repo: StubEntityRepository) -> None:
        """Test creating a stub entity in the database."""
        stub_entity_data = StubEntityData(name="Test Stub Entity", description="A test stub entity")
        stub_entity_create_command = StubEntityCreateCommand(stub_entity_data=stub_entity_data)

        stub_entity = test_stub_entity_repo.create_stub_entity(stub_entity_create_command)

        assert stub_entity.name == "Test Stub Entity"
        assert stub_entity.description == "A test stub entity"
        assert stub_entity.id is not None
        assert stub_entity.created_at is not None
        assert stub_entity.updated_at is not None

    def test_get_stub_entity_by_id(self, test_stub_entity_repo: StubEntityRepository) -> None:
        """Test retrieving a stub entity by ID."""
        # Create a stub entity
        stub_entity_data = StubEntityData(name="Retrievable Stub Entity", description="Can be retrieved")
        stub_entity_create_command = StubEntityCreateCommand(stub_entity_data=stub_entity_data)
        created_stub_entity = test_stub_entity_repo.create_stub_entity(stub_entity_create_command)

        # Retrieve it
        retrieved_stub_entity = test_stub_entity_repo.get_stub_entity_by_id(created_stub_entity.id)

        assert retrieved_stub_entity is not None
        assert retrieved_stub_entity.id == created_stub_entity.id
        assert retrieved_stub_entity.name == "Retrievable Stub Entity"
        assert retrieved_stub_entity.description == "Can be retrieved"

    def test_get_stub_entity_by_id_not_found(self, test_stub_entity_repo: StubEntityRepository) -> None:
        """Test retrieving a non-existent stub entity returns None."""
        retrieved_stub_entity = test_stub_entity_repo.get_stub_entity_by_id("non-existent-id")

        assert retrieved_stub_entity is None

    def test_get_all_stub_entities(self, test_stub_entity_repo: StubEntityRepository) -> None:
        """Test retrieving all stub entities."""
        # Create multiple stub entities
        stub_entity1_data = StubEntityData(name="Stub Entity 1", description="First stub entity")
        stub_entity2_data = StubEntityData(name="Stub Entity 2", description="Second stub entity")

        test_stub_entity_repo.create_stub_entity(StubEntityCreateCommand(stub_entity_data=stub_entity1_data))
        test_stub_entity_repo.create_stub_entity(StubEntityCreateCommand(stub_entity_data=stub_entity2_data))

        # Get all stub entities
        all_stub_entities = test_stub_entity_repo.get_all_stub_entities()

        assert len(all_stub_entities) == 2
        stub_entity_names = {stub_entity.name for stub_entity in all_stub_entities}
        assert stub_entity_names == {"Stub Entity 1", "Stub Entity 2"}

    def test_get_all_stub_entities_empty(self, test_stub_entity_repo: StubEntityRepository) -> None:
        """Test retrieving all stub entities when database is empty."""
        all_stub_entities = test_stub_entity_repo.get_all_stub_entities()

        assert all_stub_entities == []

    def test_delete_stub_entity(self, test_stub_entity_repo: StubEntityRepository) -> None:
        """Test deleting a stub entity."""
        # Create a stub entity
        stub_entity_data = StubEntityData(name="Delete Me", description="Will be deleted")
        stub_entity_create_command = StubEntityCreateCommand(stub_entity_data=stub_entity_data)
        created_stub_entity = test_stub_entity_repo.create_stub_entity(stub_entity_create_command)

        # Delete it
        success = test_stub_entity_repo.delete_stub_entity(created_stub_entity.id)

        assert success is True

        # Verify it's gone
        retrieved_stub_entity = test_stub_entity_repo.get_stub_entity_by_id(created_stub_entity.id)
        assert retrieved_stub_entity is None

    def test_delete_stub_entity_not_found(self, test_stub_entity_repo: StubEntityRepository) -> None:
        """Test deleting a non-existent stub entity returns False."""
        success = test_stub_entity_repo.delete_stub_entity("non-existent-id")

        assert success is False
