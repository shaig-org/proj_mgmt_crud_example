"""Tests for Comment repository operations.

Tests verify complete CRUD functionality for comments through the Repository interface,
including ticket scoping, author tracking, chronological ordering, and edge cases.
"""

from datetime import datetime

from project_management_crud_example.dal.sqlite.repository import Repository
from project_management_crud_example.domain_models import (
    CommentCreateCommand,
    CommentData,
    CommentUpdateCommand,
    TicketCreateCommand,
    TicketData,
    UserRole,
)
from tests.conftest import test_repo  # noqa: F401
from tests.dal.helpers import (
    create_test_org_with_workflow_via_repo,
    create_test_project_via_repo,
    create_test_user_via_repo,
)


class TestCommentRepositoryCreate:
    """Test comment creation through repository."""

    def test_create_comment_with_all_fields(self, test_repo: Repository) -> None:
        """Test creating a comment with content through repository."""
        # Create organization, project, ticket, and author
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id)
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter", role=UserRole.ADMIN)
        author = create_test_user_via_repo(test_repo, org.id, username="author", role=UserRole.WRITE_ACCESS)

        # Create ticket
        ticket_data = TicketData(title="Test ticket")
        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=ticket_data, project_id=project.id),
            reporter_id=reporter.id,
        )

        # Create comment
        comment_data = CommentData(content="This is a test comment")
        command = CommentCreateCommand(
            comment_data=comment_data,
            ticket_id=ticket.id,
        )

        comment = test_repo.comments.create(command, author_id=author.id)

        assert comment.id is not None
        assert comment.ticket_id == ticket.id
        assert comment.author_id == author.id
        assert comment.content == "This is a test comment"
        assert isinstance(comment.created_at, datetime)
        assert isinstance(comment.updated_at, datetime)

    def test_create_comment_with_long_content(self, test_repo: Repository) -> None:
        """Test creating a comment with maximum length content."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id)
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter")
        author = create_test_user_via_repo(test_repo, org.id, username="author")

        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Test"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Create comment with long content (test max length handling)
        long_content = "x" * 5000  # Max length
        command = CommentCreateCommand(
            comment_data=CommentData(content=long_content),
            ticket_id=ticket.id,
        )

        comment = test_repo.comments.create(command, author_id=author.id)

        assert comment.content == long_content
        assert len(comment.content) == 5000

    def test_create_comment_persists_to_database(self, test_repo: Repository) -> None:
        """Test that created comment can be retrieved from database."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id)
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter")
        author = create_test_user_via_repo(test_repo, org.id, username="author")

        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Test"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Create comment
        command = CommentCreateCommand(
            comment_data=CommentData(content="Persistent comment"),
            ticket_id=ticket.id,
        )
        created_comment = test_repo.comments.create(command, author_id=author.id)

        # Retrieve comment
        retrieved_comment = test_repo.comments.get_by_id(created_comment.id)

        assert retrieved_comment is not None
        assert retrieved_comment.id == created_comment.id
        assert retrieved_comment.content == created_comment.content
        assert retrieved_comment.ticket_id == ticket.id


class TestCommentRepositoryGet:
    """Test comment retrieval operations."""

    def test_get_comment_by_id_found(self, test_repo: Repository) -> None:
        """Test retrieving an existing comment by ID."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id)
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter")
        author = create_test_user_via_repo(test_repo, org.id, username="author")

        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Test"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Create comment
        comment = test_repo.comments.create(
            CommentCreateCommand(
                comment_data=CommentData(content="Test comment"),
                ticket_id=ticket.id,
            ),
            author_id=author.id,
        )

        # Retrieve comment
        retrieved = test_repo.comments.get_by_id(comment.id)

        assert retrieved is not None
        assert retrieved.id == comment.id
        assert retrieved.content == "Test comment"

    def test_get_comment_by_id_not_found(self, test_repo: Repository) -> None:
        """Test retrieving a non-existent comment returns None."""
        result = test_repo.comments.get_by_id("non-existent-id")

        assert result is None

    def test_get_comments_by_ticket_id(self, test_repo: Repository) -> None:
        """Test retrieving all comments for a specific ticket."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id)
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter")
        author = create_test_user_via_repo(test_repo, org.id, username="author")

        # Create two tickets
        ticket1 = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Ticket 1"), project_id=project.id),
            reporter_id=reporter.id,
        )
        ticket2 = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Ticket 2"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Create comments for ticket1
        comment1 = test_repo.comments.create(
            CommentCreateCommand(
                comment_data=CommentData(content="First comment"),
                ticket_id=ticket1.id,
            ),
            author_id=author.id,
        )
        comment2 = test_repo.comments.create(
            CommentCreateCommand(
                comment_data=CommentData(content="Second comment"),
                ticket_id=ticket1.id,
            ),
            author_id=author.id,
        )

        # Create comment for ticket2
        test_repo.comments.create(
            CommentCreateCommand(
                comment_data=CommentData(content="Other ticket comment"),
                ticket_id=ticket2.id,
            ),
            author_id=author.id,
        )

        # Retrieve comments for ticket1
        ticket1_comments = test_repo.comments.get_by_ticket_id(ticket1.id)

        assert len(ticket1_comments) == 2
        assert ticket1_comments[0].id == comment1.id
        assert ticket1_comments[1].id == comment2.id

    def test_get_comments_by_ticket_id_ordered_chronologically(self, test_repo: Repository) -> None:
        """Test that comments are returned in chronological order (oldest first)."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id)
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter")
        author = create_test_user_via_repo(test_repo, org.id, username="author")

        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Test"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Create multiple comments
        comment1 = test_repo.comments.create(
            CommentCreateCommand(
                comment_data=CommentData(content="First"),
                ticket_id=ticket.id,
            ),
            author_id=author.id,
        )
        comment2 = test_repo.comments.create(
            CommentCreateCommand(
                comment_data=CommentData(content="Second"),
                ticket_id=ticket.id,
            ),
            author_id=author.id,
        )
        comment3 = test_repo.comments.create(
            CommentCreateCommand(
                comment_data=CommentData(content="Third"),
                ticket_id=ticket.id,
            ),
            author_id=author.id,
        )

        # Retrieve all comments
        comments = test_repo.comments.get_by_ticket_id(ticket.id)

        assert len(comments) == 3
        # Verify chronological order (oldest first)
        assert comments[0].id == comment1.id
        assert comments[1].id == comment2.id
        assert comments[2].id == comment3.id
        assert comments[0].created_at <= comments[1].created_at
        assert comments[1].created_at <= comments[2].created_at

    def test_get_comments_by_ticket_id_empty(self, test_repo: Repository) -> None:
        """Test getting comments for ticket with no comments returns empty list."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id)
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter")

        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Test"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Get comments for ticket with no comments
        comments = test_repo.comments.get_by_ticket_id(ticket.id)

        assert comments == []


class TestCommentRepositoryUpdate:
    """Test comment update operations."""

    def test_update_comment_content(self, test_repo: Repository) -> None:
        """Test updating comment content."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id)
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter")
        author = create_test_user_via_repo(test_repo, org.id, username="author")

        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Test"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Create comment
        comment = test_repo.comments.create(
            CommentCreateCommand(
                comment_data=CommentData(content="Original content"),
                ticket_id=ticket.id,
            ),
            author_id=author.id,
        )

        original_created_at = comment.created_at

        # Update comment
        update_command = CommentUpdateCommand(content="Updated content")
        updated_comment = test_repo.comments.update(comment.id, update_command)

        assert updated_comment is not None
        assert updated_comment.id == comment.id
        assert updated_comment.content == "Updated content"
        assert updated_comment.created_at == original_created_at  # Created at doesn't change
        assert updated_comment.updated_at >= original_created_at  # Updated at is newer

    def test_update_comment_not_found(self, test_repo: Repository) -> None:
        """Test updating non-existent comment returns None."""
        update_command = CommentUpdateCommand(content="New content")
        result = test_repo.comments.update("non-existent-id", update_command)

        assert result is None

    def test_update_comment_persists(self, test_repo: Repository) -> None:
        """Test that comment update persists to database."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id)
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter")
        author = create_test_user_via_repo(test_repo, org.id, username="author")

        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Test"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Create and update comment
        comment = test_repo.comments.create(
            CommentCreateCommand(
                comment_data=CommentData(content="Original"),
                ticket_id=ticket.id,
            ),
            author_id=author.id,
        )

        test_repo.comments.update(comment.id, CommentUpdateCommand(content="Updated"))

        # Retrieve and verify
        retrieved = test_repo.comments.get_by_id(comment.id)

        assert retrieved is not None
        assert retrieved.content == "Updated"


class TestCommentRepositoryDelete:
    """Test comment deletion operations."""

    def test_delete_comment(self, test_repo: Repository) -> None:
        """Test deleting a comment."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id)
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter")
        author = create_test_user_via_repo(test_repo, org.id, username="author")

        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Test"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Create comment
        comment = test_repo.comments.create(
            CommentCreateCommand(
                comment_data=CommentData(content="To be deleted"),
                ticket_id=ticket.id,
            ),
            author_id=author.id,
        )

        # Delete comment
        result = test_repo.comments.delete(comment.id)

        assert result is True

        # Verify deletion
        retrieved = test_repo.comments.get_by_id(comment.id)
        assert retrieved is None

    def test_delete_comment_not_found(self, test_repo: Repository) -> None:
        """Test deleting non-existent comment returns False."""
        result = test_repo.comments.delete("non-existent-id")

        assert result is False

    def test_delete_comment_removes_from_ticket_list(self, test_repo: Repository) -> None:
        """Test that deleted comment no longer appears in ticket's comment list."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id)
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter")
        author = create_test_user_via_repo(test_repo, org.id, username="author")

        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Test"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Create two comments
        comment1 = test_repo.comments.create(
            CommentCreateCommand(
                comment_data=CommentData(content="Comment 1"),
                ticket_id=ticket.id,
            ),
            author_id=author.id,
        )
        comment2 = test_repo.comments.create(
            CommentCreateCommand(
                comment_data=CommentData(content="Comment 2"),
                ticket_id=ticket.id,
            ),
            author_id=author.id,
        )

        # Delete first comment
        test_repo.comments.delete(comment1.id)

        # Verify only second comment remains
        comments = test_repo.comments.get_by_ticket_id(ticket.id)

        assert len(comments) == 1
        assert comments[0].id == comment2.id


class TestCommentRepositoryMultipleAuthors:
    """Test comments with multiple authors."""

    def test_comments_from_different_authors(self, test_repo: Repository) -> None:
        """Test that comments can have different authors on same ticket."""
        # Setup
        org = create_test_org_with_workflow_via_repo(test_repo)
        project = create_test_project_via_repo(test_repo, org.id)
        reporter = create_test_user_via_repo(test_repo, org.id, username="reporter")
        author1 = create_test_user_via_repo(test_repo, org.id, username="author1")
        author2 = create_test_user_via_repo(test_repo, org.id, username="author2")

        ticket = test_repo.tickets.create(
            TicketCreateCommand(ticket_data=TicketData(title="Test"), project_id=project.id),
            reporter_id=reporter.id,
        )

        # Create comments from different authors
        comment1 = test_repo.comments.create(
            CommentCreateCommand(
                comment_data=CommentData(content="From author 1"),
                ticket_id=ticket.id,
            ),
            author_id=author1.id,
        )
        comment2 = test_repo.comments.create(
            CommentCreateCommand(
                comment_data=CommentData(content="From author 2"),
                ticket_id=ticket.id,
            ),
            author_id=author2.id,
        )

        # Verify different authors
        assert comment1.author_id == author1.id
        assert comment2.author_id == author2.id
        assert comment1.author_id != comment2.author_id
