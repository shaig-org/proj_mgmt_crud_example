"""Unit tests for ProjectReadCapability, OrgProjectWriteCapability, and BoundProjectWriteCapability."""

from __future__ import annotations

import inspect

import pytest

from project_management_crud_example.capabilities.errors import CapabilityNotFoundError
from project_management_crud_example.capabilities.projects_capability import (
    BoundProjectWriteCapability,
    OrgProjectWriteCapability,
    ProjectReadCapability,
)
from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    ProjectData,
    ProjectUpdateCommand,
    UserRole,
)
from tests.capabilities.helpers import assert_denied, make_user
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import (
    create_test_org_with_workflow_via_repo,
    create_test_project_via_repo,
)

# ---------------------------------------------------------------------------
# ProjectReadCapability
# ---------------------------------------------------------------------------


def test_project_read_get_by_id_allows_member(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")

    cap = ProjectReadCapability(test_repo, admin)
    result = cap.get_by_id(project.id)
    assert result is not None
    assert result.id == project.id


def test_project_read_get_by_id_returns_none_for_missing(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    cap = ProjectReadCapability(test_repo, admin)
    assert cap.get_by_id("missing-id") is None


def test_project_read_get_by_id_denies_cross_org_user(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    cross_user = make_user(test_repo, org_b, UserRole.ADMIN, username="cross_admin")
    project = create_test_project_via_repo(test_repo, org_a.id, name="P")

    cap = ProjectReadCapability(test_repo, cross_user)
    assert_denied(cap.get_by_id, project.id)


def test_project_read_list_projects_scopes_to_user_org(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    admin = make_user(test_repo, org_a, UserRole.ADMIN)
    create_test_project_via_repo(test_repo, org_a.id, name="A-proj")
    create_test_project_via_repo(test_repo, org_b.id, name="B-proj")

    cap = ProjectReadCapability(test_repo, admin)
    projects = cap.list_projects()
    names = {p.name for p in projects}
    assert "A-proj" in names
    assert "B-proj" not in names


def test_project_read_list_projects_super_admin_sees_all(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    sa = make_user(test_repo, org_a, UserRole.SUPER_ADMIN)
    create_test_project_via_repo(test_repo, org_a.id, name="A-proj")
    create_test_project_via_repo(test_repo, org_b.id, name="B-proj")

    cap = ProjectReadCapability(test_repo, sa)
    names = {p.name for p in cap.list_projects()}
    assert {"A-proj", "B-proj"}.issubset(names)


# ---------------------------------------------------------------------------
# OrgProjectWriteCapability — collection-level (build_create_command, create, bind)
# ---------------------------------------------------------------------------


def test_project_write_create_allows_admin(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    cap = OrgProjectWriteCapability(test_repo, admin)
    command = cap.build_create_command(ProjectData(name="New"))
    project = cap.create(command)
    assert project.organization_id == org.id


def test_project_write_create_denies_read_user(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    read_user = make_user(test_repo, org, UserRole.READ_ACCESS)
    cap = OrgProjectWriteCapability(test_repo, read_user)
    assert_denied(cap.build_create_command, ProjectData(name="nope"))


def test_org_create_emits_activity_log(test_repo: Repository) -> None:
    """create() emits an activity-log entry — verb owns the side-effect, not the route."""
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    cap = OrgProjectWriteCapability(test_repo, admin)
    command = cap.build_create_command(ProjectData(name="WithLog"))
    project = cap.create(command)

    logs = test_repo.activity_logs.list(entity_type="project", entity_id=project.id)
    assert len(logs) == 1
    assert logs[0].actor_id == admin.id
    assert logs[0].organization_id == org.id


def test_bind_returns_bound_capability_for_authorized_project(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    cap = OrgProjectWriteCapability(test_repo, admin)

    bound = cap.bind(project.id)
    assert isinstance(bound, BoundProjectWriteCapability)


def test_bind_loaded_project_on_current(test_repo: Repository) -> None:
    """`current` exposes the project that bind() resolved (pre-mutation snapshot)."""
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    cap = OrgProjectWriteCapability(test_repo, admin)

    bound = cap.bind(project.id)
    assert bound.current.id == project.id
    assert bound.current.name == "P"


def test_bind_raises_permission_error_for_wrong_role(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    writer = make_user(test_repo, org, UserRole.WRITE_ACCESS)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    cap = OrgProjectWriteCapability(test_repo, writer)
    assert_denied(cap.bind, project.id)


def test_bind_raises_permission_error_for_cross_org_project(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    cross_admin = make_user(test_repo, org_b, UserRole.ADMIN, username="cross_admin")
    project = create_test_project_via_repo(test_repo, org_a.id, name="P")
    cap = OrgProjectWriteCapability(test_repo, cross_admin)
    assert_denied(cap.bind, project.id)


def test_bind_raises_not_found_error_for_missing_project(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    cap = OrgProjectWriteCapability(test_repo, admin)
    with pytest.raises(CapabilityNotFoundError) as exc_info:
        cap.bind("missing-id")
    assert exc_info.value.detail == "Project not found"


def test_bind_super_admin_crosses_org(test_repo: Repository) -> None:
    org_a = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    org_b = create_test_org_with_workflow_via_repo(test_repo, name="Org B")
    sa = make_user(test_repo, org_b, UserRole.SUPER_ADMIN, username="super_admin")
    project = create_test_project_via_repo(test_repo, org_a.id, name="P")
    cap = OrgProjectWriteCapability(test_repo, sa)

    bound = cap.bind(project.id)
    assert bound.current.id == project.id


# ---------------------------------------------------------------------------
# BoundProjectWriteCapability — bound verbs
# ---------------------------------------------------------------------------


def test_bound_update_modifies_project_for_admin(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")

    bound = OrgProjectWriteCapability(test_repo, admin).bind(project.id)
    updated = bound.update(ProjectUpdateCommand(name="P2"))
    assert updated.name == "P2"


def test_bound_delete_removes_project_for_admin(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")

    bound = OrgProjectWriteCapability(test_repo, admin).bind(project.id)
    bound.delete()
    assert test_repo.projects.get_by_id(project.id) is None


def test_bound_delete_denies_project_manager(test_repo: Repository) -> None:
    """PROJECT_MANAGER can bind() but the bound delete() defensively denies."""
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    pm = make_user(test_repo, org, UserRole.PROJECT_MANAGER)
    project = create_test_project_via_repo(test_repo, org.id, name="P")

    bound = OrgProjectWriteCapability(test_repo, pm).bind(project.id)
    assert_denied(bound.delete)


def test_bound_archive_allows_pm(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    pm = make_user(test_repo, org, UserRole.PROJECT_MANAGER)
    project = create_test_project_via_repo(test_repo, org.id, name="P")

    bound = OrgProjectWriteCapability(test_repo, pm).bind(project.id)
    archived = bound.archive()
    assert archived.archived_at is not None


def test_bound_unarchive_denies_pm(test_repo: Repository) -> None:
    """unarchive requires delete-level role; PM can bind but is denied at the verb."""
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    pm = make_user(test_repo, org, UserRole.PROJECT_MANAGER)
    project = create_test_project_via_repo(test_repo, org.id, name="P")

    bound = OrgProjectWriteCapability(test_repo, pm).bind(project.id)
    assert_denied(bound.unarchive)


def test_bound_unarchive_allows_admin(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    test_repo.projects.archive(project.id)

    bound = OrgProjectWriteCapability(test_repo, admin).bind(project.id)
    unarchived = bound.unarchive()
    assert unarchived.archived_at is None


def test_bound_update_emits_activity_log(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")

    bound = OrgProjectWriteCapability(test_repo, admin).bind(project.id)
    bound.update(ProjectUpdateCommand(name="P2"))

    logs = test_repo.activity_logs.list(entity_type="project", entity_id=project.id)
    assert len(logs) == 1
    assert logs[0].actor_id == admin.id


def test_bound_delete_emits_activity_log(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")

    bound = OrgProjectWriteCapability(test_repo, admin).bind(project.id)
    bound.delete()

    logs = test_repo.activity_logs.list(entity_type="project", entity_id=project.id)
    assert len(logs) == 1
    assert logs[0].actor_id == admin.id


def test_bound_archive_emits_activity_log(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")

    bound = OrgProjectWriteCapability(test_repo, admin).bind(project.id)
    bound.archive()

    logs = test_repo.activity_logs.list(entity_type="project", entity_id=project.id)
    assert len(logs) == 1


def test_bound_unarchive_emits_activity_log(test_repo: Repository) -> None:
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")
    test_repo.projects.archive(project.id)

    bound = OrgProjectWriteCapability(test_repo, admin).bind(project.id)
    bound.unarchive()

    logs = test_repo.activity_logs.list(entity_type="project", entity_id=project.id)
    assert len(logs) == 1


def test_bound_update_raises_not_found_after_external_delete(test_repo: Repository) -> None:
    """Race: project deleted between bind() and update() — verb raises NotFound, not 500."""
    org = create_test_org_with_workflow_via_repo(test_repo, name="Org A")
    admin = make_user(test_repo, org, UserRole.ADMIN)
    project = create_test_project_via_repo(test_repo, org.id, name="P")

    bound = OrgProjectWriteCapability(test_repo, admin).bind(project.id)
    test_repo.projects.delete(project.id)  # simulate concurrent delete

    with pytest.raises(CapabilityNotFoundError) as exc_info:
        bound.update(ProjectUpdateCommand(name="P2"))
    assert exc_info.value.detail == "Project not found"


# ---------------------------------------------------------------------------
# Structural guards (encapsulation invariants)
# ---------------------------------------------------------------------------


def test_bound_write_has_no_project_id_arg() -> None:
    """Scope-in-type invariant: no public bound verb accepts a project_id parameter."""
    for name, member in inspect.getmembers(BoundProjectWriteCapability, inspect.isfunction):
        if name.startswith("_"):
            continue
        params = inspect.signature(member).parameters
        for param_name in params:
            assert "project_id" not in param_name.lower(), f"BoundProjectWriteCapability.{name} accepts `{param_name}`"


def test_bound_write_has_no_repo_accessor() -> None:
    """Encapsulation invariant: bound capability does not expose `repo`."""
    public = {n for n in vars(BoundProjectWriteCapability) if not n.startswith("_")}
    assert "repo" not in public


def test_bound_write_has_no_user_accessor() -> None:
    """Encapsulation invariant: bound capability does not expose `user`."""
    public = {n for n in vars(BoundProjectWriteCapability) if not n.startswith("_")}
    assert "user" not in public


def test_org_project_write_has_no_repo_accessor() -> None:
    """Encapsulation invariant: collection-level capability does not expose `repo`."""
    public = {n for n in vars(OrgProjectWriteCapability) if not n.startswith("_")}
    assert "repo" not in public


def test_org_project_write_has_no_user_accessor() -> None:
    """Encapsulation invariant: collection-level capability does not expose `user`."""
    public = {n for n in vars(OrgProjectWriteCapability) if not n.startswith("_")}
    assert "user" not in public
