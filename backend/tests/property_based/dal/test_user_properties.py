"""Stateless property-based tests for User repository."""

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import UserCreateCommand, UserData, UserRole
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import create_test_org_via_repo

# Strategy for generating valid usernames
USERNAME_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"


@st.composite
def usernames(draw: st.DrawFn) -> str:
    """Generate valid usernames."""
    return draw(st.text(min_size=3, max_size=20, alphabet=USERNAME_CHARS))


@st.composite
def emails(draw: st.DrawFn) -> str:
    """Generate valid email addresses."""
    local = draw(st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz0123456789"))
    domain = draw(st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"))
    return f"{local}@{domain}.com"


@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=5,  # Run only 5 examples for this minimal test
)
@given(
    username=usernames(),
    email=emails(),
    full_name=st.text(min_size=1, max_size=50),
    role=st.sampled_from([UserRole.ADMIN, UserRole.PROJECT_MANAGER, UserRole.WRITE_ACCESS, UserRole.READ_ACCESS]),
)
def test_user_create_get_roundtrip(
    test_repo: Repository,
    username: str,
    email: str,
    full_name: str,
    role: UserRole,
) -> None:
    """Property: Any valid user data survives create-get roundtrip.

    This tests that:
    1. Creating a user with valid data succeeds
    2. Retrieving the user returns the same data
    3. All fields are preserved correctly
    """
    import uuid

    # Create organization (required for user) with unique name
    org_name = f"Test Org {uuid.uuid4().hex[:8]}"
    org = create_test_org_via_repo(test_repo, name=org_name)

    # Make username and email unique by adding UUID suffix to avoid collisions across hypothesis examples
    unique_username = f"{username}{uuid.uuid4().hex[:6]}"
    # For email, add UUID before @ to keep it valid
    email_local, email_domain = email.split("@", 1)
    unique_email = f"{email_local}{uuid.uuid4().hex[:6]}@{email_domain}"

    # Create user using domain command
    user_data = UserData(
        username=unique_username,
        email=unique_email,
        full_name=full_name,
    )
    command = UserCreateCommand(
        user_data=user_data,
        password="test_password",
        organization_id=org.id,
        role=role,
    )
    created_user = test_repo.users.create(command)

    # Retrieve user
    retrieved_user = test_repo.users.get_by_id(created_user.id)

    # Verify roundtrip - all fields preserved
    assert retrieved_user is not None
    assert retrieved_user.id == created_user.id
    assert retrieved_user.username == unique_username
    assert retrieved_user.email == unique_email
    assert retrieved_user.full_name == full_name
    assert retrieved_user.role == role
    assert retrieved_user.organization_id == org.id
