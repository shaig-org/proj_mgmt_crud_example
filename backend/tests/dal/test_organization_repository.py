"""Tests for organization operations through Repository interface."""

import pytest
from sqlalchemy.exc import IntegrityError

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    OrganizationCreateCommand,
    OrganizationData,
    OrganizationUpdateCommand,
)
from tests.conftest import test_repo  # noqa: F401


class TestOrganizationOperations:
    """Test organization operations through Repository interface."""

    def test_create_organization(self, test_repo: Repository) -> None:
        """Test creating an organization through repository."""
        org_data = OrganizationData(
            name="Acme Corporation",
            description="A test organization",
        )
        command = OrganizationCreateCommand(organization_data=org_data)

        organization = test_repo.organizations.create(command)

        assert organization.name == "Acme Corporation"
        assert organization.description == "A test organization"
        assert organization.is_active is True
        assert organization.id is not None
        assert organization.created_at is not None
        assert organization.updated_at is not None

    def test_create_organization_without_description(self, test_repo: Repository) -> None:
        """Test creating organization with only required fields."""
        org_data = OrganizationData(name="Minimal Organization")
        command = OrganizationCreateCommand(organization_data=org_data)

        organization = test_repo.organizations.create(command)

        assert organization.name == "Minimal Organization"
        assert organization.description is None
        assert organization.is_active is True
        assert organization.id is not None

    def test_create_organization_with_special_characters(self, test_repo: Repository) -> None:
        """Test creating organization with special characters in name."""
        org_data = OrganizationData(name="Acme Corp. & Partners!")
        command = OrganizationCreateCommand(organization_data=org_data)

        organization = test_repo.organizations.create(command)

        assert organization.name == "Acme Corp. & Partners!"

    def test_create_organization_with_unicode(self, test_repo: Repository) -> None:
        """Test creating organization with unicode characters in name."""
        org_data = OrganizationData(name="日本株式会社")
        command = OrganizationCreateCommand(organization_data=org_data)

        organization = test_repo.organizations.create(command)

        assert organization.name == "日本株式会社"

    def test_create_organization_with_max_length_name(self, test_repo: Repository) -> None:
        """Test creating organization with maximum length name."""
        max_name = "a" * 255
        org_data = OrganizationData(name=max_name)
        command = OrganizationCreateCommand(organization_data=org_data)

        organization = test_repo.organizations.create(command)

        assert organization.name == max_name
        assert len(organization.name) == 255

    def test_create_organization_with_duplicate_name_fails(self, test_repo: Repository) -> None:
        """Test that creating organization with duplicate name fails."""
        org_data = OrganizationData(name="Duplicate Org")
        command = OrganizationCreateCommand(organization_data=org_data)

        # Create first organization
        test_repo.organizations.create(command)

        # Attempt to create second organization with same name
        with pytest.raises(IntegrityError):
            test_repo.organizations.create(command)

    def test_get_organization_by_id(self, test_repo: Repository) -> None:
        """Test retrieving organization by ID through repository."""
        # Create organization
        org_data = OrganizationData(name="Get By ID Org", description="Test org")
        command = OrganizationCreateCommand(organization_data=org_data)
        created_org = test_repo.organizations.create(command)

        # Retrieve organization
        retrieved_org = test_repo.organizations.get_by_id(created_org.id)

        assert retrieved_org is not None
        assert retrieved_org.id == created_org.id
        assert retrieved_org.name == "Get By ID Org"
        assert retrieved_org.description == "Test org"

    def test_get_organization_by_id_not_found(self, test_repo: Repository) -> None:
        """Test retrieving non-existent organization returns None."""
        retrieved_org = test_repo.organizations.get_by_id("non-existent-id")

        assert retrieved_org is None

    def test_get_all_organizations(self, test_repo: Repository) -> None:
        """Test retrieving all organizations through repository."""
        # Create multiple organizations
        org1_data = OrganizationData(name="Organization 1", description="First org")
        org2_data = OrganizationData(name="Organization 2", description="Second org")

        test_repo.organizations.create(OrganizationCreateCommand(organization_data=org1_data))
        test_repo.organizations.create(OrganizationCreateCommand(organization_data=org2_data))

        # Get all organizations
        all_orgs = test_repo.organizations.get_all()

        assert len(all_orgs) == 2
        org_names = {org.name for org in all_orgs}
        assert org_names == {"Organization 1", "Organization 2"}

    def test_get_all_organizations_empty(self, test_repo: Repository) -> None:
        """Test retrieving all organizations when database is empty."""
        all_orgs = test_repo.organizations.get_all()

        assert all_orgs == []

    def test_update_organization_name(self, test_repo: Repository) -> None:
        """Test updating organization name."""
        # Create organization
        org_data = OrganizationData(name="Original Name", description="Test org")
        command = OrganizationCreateCommand(organization_data=org_data)
        created_org = test_repo.organizations.create(command)

        # Update name
        update_command = OrganizationUpdateCommand(name="Updated Name")
        updated_org = test_repo.organizations.update(created_org.id, update_command)

        assert updated_org is not None
        assert updated_org.id == created_org.id
        assert updated_org.name == "Updated Name"
        assert updated_org.description == "Test org"  # Unchanged

        # Verify via get_by_id
        retrieved_org = test_repo.organizations.get_by_id(created_org.id)
        assert retrieved_org is not None
        assert retrieved_org.name == "Updated Name"

    def test_update_organization_description(self, test_repo: Repository) -> None:
        """Test updating organization description."""
        # Create organization
        org_data = OrganizationData(name="Test Org", description="Original description")
        command = OrganizationCreateCommand(organization_data=org_data)
        created_org = test_repo.organizations.create(command)

        # Update description
        update_command = OrganizationUpdateCommand(description="Updated description")
        updated_org = test_repo.organizations.update(created_org.id, update_command)

        assert updated_org is not None
        assert updated_org.name == "Test Org"  # Unchanged
        assert updated_org.description == "Updated description"

    def test_update_organization_is_active(self, test_repo: Repository) -> None:
        """Test deactivating an organization."""
        # Create organization
        org_data = OrganizationData(name="Active Org")
        command = OrganizationCreateCommand(organization_data=org_data)
        created_org = test_repo.organizations.create(command)

        assert created_org.is_active is True

        # Deactivate organization
        update_command = OrganizationUpdateCommand(is_active=False)
        updated_org = test_repo.organizations.update(created_org.id, update_command)

        assert updated_org is not None
        assert updated_org.is_active is False

    def test_update_organization_multiple_fields(self, test_repo: Repository) -> None:
        """Test updating multiple fields at once."""
        # Create organization
        org_data = OrganizationData(name="Original", description="Original description")
        command = OrganizationCreateCommand(organization_data=org_data)
        created_org = test_repo.organizations.create(command)

        # Update multiple fields
        update_command = OrganizationUpdateCommand(
            name="Updated Name",
            description="Updated description",
            is_active=False,
        )
        updated_org = test_repo.organizations.update(created_org.id, update_command)

        assert updated_org is not None
        assert updated_org.name == "Updated Name"
        assert updated_org.description == "Updated description"
        assert updated_org.is_active is False

    def test_update_organization_not_found(self, test_repo: Repository) -> None:
        """Test updating non-existent organization returns None."""
        update_command = OrganizationUpdateCommand(name="New Name")
        updated_org = test_repo.organizations.update("non-existent-id", update_command)

        assert updated_org is None

    def test_update_organization_to_duplicate_name_fails(self, test_repo: Repository) -> None:
        """Test that updating to duplicate name fails."""
        # Create two organizations
        org1_data = OrganizationData(name="Organization 1")
        org2_data = OrganizationData(name="Organization 2")

        test_repo.organizations.create(OrganizationCreateCommand(organization_data=org1_data))
        org2 = test_repo.organizations.create(OrganizationCreateCommand(organization_data=org2_data))

        # Attempt to update org2 to have same name as org1
        update_command = OrganizationUpdateCommand(name="Organization 1")
        with pytest.raises(IntegrityError):
            test_repo.organizations.update(org2.id, update_command)

    def test_delete_organization(self, test_repo: Repository) -> None:
        """Test deleting an organization through repository."""
        # Create organization
        org_data = OrganizationData(name="Delete Me", description="Will be deleted")
        command = OrganizationCreateCommand(organization_data=org_data)
        created_org = test_repo.organizations.create(command)

        # Delete organization
        success = test_repo.organizations.delete(created_org.id)

        assert success is True

        # Verify organization is gone
        retrieved_org = test_repo.organizations.get_by_id(created_org.id)
        assert retrieved_org is None

    def test_delete_organization_not_found(self, test_repo: Repository) -> None:
        """Test deleting non-existent organization returns False."""
        success = test_repo.organizations.delete("non-existent-id")

        assert success is False

    def test_organization_timestamps(self, test_repo: Repository) -> None:
        """Test that organization has proper timestamps."""
        # Create organization
        org_data = OrganizationData(name="Timestamp Test")
        command = OrganizationCreateCommand(organization_data=org_data)
        created_org = test_repo.organizations.create(command)

        assert created_org.created_at is not None
        assert created_org.updated_at is not None
        # Timestamps should be very close (within 1 second)
        time_diff = abs((created_org.updated_at - created_org.created_at).total_seconds())
        assert time_diff < 1.0

    def test_complete_organization_crud_workflow(self, test_repo: Repository) -> None:
        """Test complete CRUD workflow for organizations."""
        # 1. Create
        org_data = OrganizationData(name="CRUD Test Org", description="Testing CRUD")
        create_command = OrganizationCreateCommand(organization_data=org_data)
        created_org = test_repo.organizations.create(create_command)

        assert created_org.id is not None
        assert created_org.name == "CRUD Test Org"

        # 2. Read
        read_org = test_repo.organizations.get_by_id(created_org.id)
        assert read_org is not None
        assert read_org.name == "CRUD Test Org"

        # 3. Update
        update_command = OrganizationUpdateCommand(description="Updated description")
        updated_org = test_repo.organizations.update(created_org.id, update_command)
        assert updated_org is not None
        assert updated_org.description == "Updated description"

        # 4. List
        all_orgs = test_repo.organizations.get_all()
        assert len(all_orgs) == 1
        assert all_orgs[0].id == created_org.id

        # 5. Delete
        delete_success = test_repo.organizations.delete(created_org.id)
        assert delete_success is True

        # 6. Verify deletion
        final_check = test_repo.organizations.get_by_id(created_org.id)
        assert final_check is None
