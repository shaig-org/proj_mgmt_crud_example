import { useState, useEffect, FormEvent } from 'react';
import { useParams, Link } from 'react-router-dom';
import apiClient, { Ticket, User, Comment, Epic } from '../services/api';
import { Navigation } from '../components/Navigation';

export function TicketDetailsPage() {
  const { ticketId } = useParams<{ ticketId: string }>();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [users, setUsers] = useState<User[]>([]);
  const [epics, setEpics] = useState<Epic[]>([]);
  const [ticketEpics, setTicketEpics] = useState<string[]>([]);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [isUpdatingAssignee, setIsUpdatingAssignee] = useState(false);
  const [isUpdatingEpic, setIsUpdatingEpic] = useState(false);
  const [comments, setComments] = useState<Comment[]>([]);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [newCommentContent, setNewCommentContent] = useState('');
  const [isAddingComment, setIsAddingComment] = useState(false);
  const [addCommentError, setAddCommentError] = useState('');

  useEffect(() => {
    const fetchTicket = async () => {
      if (!ticketId) {
        setError('No ticket ID provided');
        setIsLoading(false);
        return;
      }

      try {
        const [ticketData, usersData, epicsData] = await Promise.all([
          apiClient.getTicket(ticketId),
          apiClient.getUsers(),
          apiClient.getEpics(),
        ]);
        setTicket(ticketData);
        setUsers(usersData);
        setEpics(epicsData);

        // Find which epics contain this ticket
        const epicIds: string[] = [];
        for (const epic of epicsData) {
          const epicTickets = await apiClient.getEpicTickets(epic.id);
          if (epicTickets.some(t => t.id === ticketId)) {
            epicIds.push(epic.id);
          }
        }
        setTicketEpics(epicIds);
      } catch (err) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('Failed to load ticket');
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchTicket();
  }, [ticketId]);

  useEffect(() => {
    const fetchComments = async () => {
      if (!ticketId) return;

      setCommentsLoading(true);
      try {
        const data = await apiClient.getComments(ticketId);
        setComments(data);
      } catch (err) {
        console.error('Failed to load comments:', err);
      } finally {
        setCommentsLoading(false);
      }
    };

    fetchComments();
  }, [ticketId]);

  const handleAddComment = async (e: FormEvent) => {
    e.preventDefault();
    if (!ticketId || !newCommentContent.trim()) return;

    setIsAddingComment(true);
    setAddCommentError('');

    try {
      const newComment = await apiClient.createComment(ticketId, newCommentContent.trim());
      setComments([...comments, newComment]);
      setNewCommentContent('');
    } catch (err) {
      setAddCommentError(err instanceof Error ? err.message : 'Failed to add comment');
    } finally {
      setIsAddingComment(false);
    }
  };

  const handleDeleteComment = async (commentId: string) => {
    if (!window.confirm('Are you sure you want to delete this comment?')) return;

    try {
      await apiClient.deleteComment(commentId);
      setComments(comments.filter(c => c.id !== commentId));
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete comment');
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!ticketId) return;

    setIsUpdatingStatus(true);
    try {
      const updatedTicket = await apiClient.updateTicketStatus(ticketId, newStatus);
      setTicket(updatedTicket);
    } catch (err) {
      console.error('Failed to update status:', err);
      alert('Failed to update ticket status');
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  const handleAssigneeChange = async (assigneeId: string) => {
    if (!ticketId) return;

    setIsUpdatingAssignee(true);
    try {
      const updatedTicket = await apiClient.updateTicketAssignee(
        ticketId,
        assigneeId || null
      );
      setTicket(updatedTicket);
    } catch (err) {
      console.error('Failed to update assignee:', err);
      alert('Failed to update ticket assignee');
    } finally {
      setIsUpdatingAssignee(false);
    }
  };

  const handleEpicChange = async (epicId: string) => {
    if (!ticketId) return;

    setIsUpdatingEpic(true);
    try {
      // Get current epic (first one if multiple)
      const currentEpicId = ticketEpics[0];

      // If there's a current epic and it's different, remove from it
      if (currentEpicId && currentEpicId !== epicId) {
        await apiClient.removeTicketFromEpic(currentEpicId, ticketId);
      }

      // If new epic is selected, add to it
      if (epicId) {
        await apiClient.addTicketToEpic(epicId, ticketId);
        setTicketEpics([epicId]);
      } else {
        // No epic selected - remove from current if any
        if (currentEpicId) {
          await apiClient.removeTicketFromEpic(currentEpicId, ticketId);
        }
        setTicketEpics([]);
      }
    } catch (err) {
      console.error('Failed to update epic:', err);
      alert('Failed to update ticket epic');
    } finally {
      setIsUpdatingEpic(false);
    }
  };

  if (isLoading) {
    return (
      <>
        <Navigation />
        <div className="ticket-details-page">
          <div className="loading">Loading ticket...</div>
        </div>
      </>
    );
  }

  if (error || !ticket) {
    return (
      <>
        <Navigation />
        <div className="ticket-details-page">
          <div className="error-message">{error || 'Ticket not found'}</div>
          <Link to={`/projects/${ticket?.project_id || ''}`} className="back-link">
            ← Back to Project
          </Link>
        </div>
      </>
    );
  }

  return (
    <>
      <Navigation />
      <div className="ticket-details-page">
        <div className="page-header">
          <div className="header-with-back">
            <Link to={`/projects/${ticket.project_id}`} className="back-link">
              ← Back to Project
            </Link>
            <h1>{ticket.title}</h1>
          </div>
        </div>

        <div className="ticket-details-content">
          <div className="details-section">
            <h2>Ticket Information</h2>
            <dl className="details-list">
              <dt>Description</dt>
              <dd>{ticket.description || 'No description provided'}</dd>

              <dt>Status</dt>
              <dd>
                <select
                  value={ticket.status}
                  onChange={(e) => handleStatusChange(e.target.value)}
                  disabled={isUpdatingStatus}
                  className="status-select"
                >
                  <option value="TODO">TODO</option>
                  <option value="IN_PROGRESS">IN_PROGRESS</option>
                  <option value="DONE">DONE</option>
                </select>
              </dd>

              <dt>Priority</dt>
              <dd>
                {ticket.priority ? (
                  <span className={`priority-badge priority-${ticket.priority.toLowerCase()}`}>
                    {ticket.priority}
                  </span>
                ) : (
                  'Not set'
                )}
              </dd>

              <dt>Reporter</dt>
              <dd>{users.find(u => u.id === ticket.reporter_id)?.full_name || ticket.reporter_id}</dd>

              <dt>Assignee</dt>
              <dd>
                <select
                  value={ticket.assignee_id || ''}
                  onChange={(e) => handleAssigneeChange(e.target.value)}
                  disabled={isUpdatingAssignee}
                  className="assignee-select"
                >
                  <option value="">Unassigned</option>
                  {users.filter(u => u.is_active).map(user => (
                    <option key={user.id} value={user.id}>
                      {user.full_name} ({user.username})
                    </option>
                  ))}
                </select>
              </dd>

              <dt>Epic</dt>
              <dd>
                <select
                  value={ticketEpics[0] || ''}
                  onChange={(e) => handleEpicChange(e.target.value)}
                  disabled={isUpdatingEpic}
                  className="epic-select"
                >
                  <option value="">No Epic</option>
                  {epics.map(epic => (
                    <option key={epic.id} value={epic.id}>
                      {epic.name}
                    </option>
                  ))}
                </select>
              </dd>

              <dt>Project ID</dt>
              <dd>{ticket.project_id}</dd>

              <dt>Created</dt>
              <dd>{new Date(ticket.created_at).toLocaleString()}</dd>

              <dt>Last Updated</dt>
              <dd>{new Date(ticket.updated_at).toLocaleString()}</dd>
            </dl>
          </div>

          <div className="comments-section">
            <h2>Comments ({comments.length})</h2>

            {commentsLoading ? (
              <p>Loading comments...</p>
            ) : (
              <>
                {comments.length === 0 ? (
                  <p className="no-comments">No comments yet. Be the first to comment!</p>
                ) : (
                  <div className="comments-list">
                    {comments.map(comment => {
                      const author = users.find(u => u.id === comment.author_id);
                      return (
                        <div key={comment.id} className="comment" data-comment-id={comment.id}>
                          <div className="comment-header">
                            <span className="comment-author">
                              {author ? `${author.full_name} (${author.username})` : 'Unknown User'}
                            </span>
                            <span className="comment-timestamp">
                              {new Date(comment.created_at).toLocaleString()}
                            </span>
                          </div>
                          <div className="comment-content">{comment.content}</div>
                          <button
                            onClick={() => handleDeleteComment(comment.id)}
                            className="delete-comment-btn"
                            aria-label={`Delete comment by ${author?.full_name || 'Unknown User'}`}
                          >
                            Delete
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}

                <form onSubmit={handleAddComment} className="add-comment-form">
                  <h3>Add Comment</h3>
                  {addCommentError && <div className="error-message">{addCommentError}</div>}
                  <textarea
                    className="comment-input"
                    value={newCommentContent}
                    onChange={(e) => setNewCommentContent(e.target.value)}
                    placeholder="Write a comment..."
                    rows={4}
                    disabled={isAddingComment}
                    aria-label="New comment content"
                  />
                  <button
                    type="submit"
                    className="submit-comment-btn"
                    disabled={isAddingComment || !newCommentContent.trim()}
                  >
                    {isAddingComment ? 'Adding...' : 'Add Comment'}
                  </button>
                </form>
              </>
            )}
          </div>
        </div>

        <style>{`
          .ticket-details-page {
            padding: 2rem;
          }

          .page-header {
            margin-bottom: 2rem;
          }

          .header-with-back {
            display: flex;
            flex-direction: column;
            gap: 1rem;
          }

          .back-link {
            color: #1976d2;
            text-decoration: none;
            font-size: 0.95rem;
          }

          .back-link:hover {
            text-decoration: underline;
          }

          .ticket-details-content {
            max-width: 900px;
          }

          .details-section {
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            margin-bottom: 2rem;
          }

          .details-section h2 {
            margin-top: 0;
            margin-bottom: 1.5rem;
            color: #333;
          }

          .details-list {
            display: grid;
            grid-template-columns: 150px 1fr;
            gap: 1rem;
          }

          .details-list dt {
            font-weight: 600;
            color: #666;
          }

          .details-list dd {
            margin: 0;
          }

          .status-select,
          .assignee-select,
          .epic-select {
            padding: 0.5rem;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 1rem;
            background: white;
            cursor: pointer;
          }

          .status-select:disabled,
          .assignee-select:disabled,
          .epic-select:disabled {
            opacity: 0.6;
            cursor: not-allowed;
          }

          .priority-badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-weight: 500;
            font-size: 0.875rem;
          }

          .priority-critical {
            background: #ffebee;
            color: #c62828;
          }

          .priority-high {
            background: #fff3e0;
            color: #e65100;
          }

          .priority-medium {
            background: #fff9c4;
            color: #f57f17;
          }

          .priority-low {
            background: #e8f5e9;
            color: #2e7d32;
          }

          .comments-section {
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
          }

          .comments-section h2 {
            margin-top: 0;
            margin-bottom: 1.5rem;
            color: #333;
          }

          .no-comments {
            color: #666;
            font-style: italic;
            margin-bottom: 2rem;
          }

          .comments-list {
            margin-bottom: 2rem;
          }

          .comment {
            background: #f9f9f9;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
            border-left: 3px solid #1976d2;
          }

          .comment-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.5rem;
            font-size: 0.875rem;
          }

          .comment-author {
            font-weight: 600;
            color: #1976d2;
          }

          .comment-timestamp {
            color: #666;
          }

          .comment-content {
            margin-bottom: 0.75rem;
            line-height: 1.6;
            white-space: pre-wrap;
            word-wrap: break-word;
          }

          .delete-comment-btn {
            padding: 0.25rem 0.75rem;
            font-size: 0.875rem;
            color: #d32f2f;
            background: white;
            border: 1px solid #d32f2f;
            border-radius: 4px;
            cursor: pointer;
          }

          .delete-comment-btn:hover {
            background: #ffebee;
          }

          .add-comment-form {
            background: #f5f5f5;
            padding: 1.5rem;
            border-radius: 8px;
          }

          .add-comment-form h3 {
            margin-top: 0;
            margin-bottom: 1rem;
          }

          .comment-input {
            width: 100%;
            padding: 0.75rem;
            border: 1px solid #ccc;
            border-radius: 4px;
            font-family: inherit;
            font-size: 1rem;
            resize: vertical;
            margin-bottom: 1rem;
            box-sizing: border-box;
          }

          .comment-input:disabled {
            background: #f0f0f0;
            cursor: not-allowed;
          }

          .submit-comment-btn {
            padding: 0.75rem 1.5rem;
            background: #1976d2;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 1rem;
            font-weight: 500;
          }

          .submit-comment-btn:hover:not(:disabled) {
            background: #1565c0;
          }

          .submit-comment-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }

          .error-message {
            background: #ffebee;
            color: #c62828;
            padding: 0.75rem;
            border-radius: 4px;
            margin-bottom: 1rem;
          }

          .loading {
            text-align: center;
            padding: 2rem;
            color: #666;
          }
        `}</style>
      </div>
    </>
  );
}
