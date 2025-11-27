import { useState, useEffect, FormEvent, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import apiClient, { Project, Epic, Ticket, TicketPriority, User } from '../services/api';
import { Navigation } from '../components/Navigation';

export function ProjectDetailsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [epics, setEpics] = useState<Epic[]>([]);
  const [epicsLoading, setEpicsLoading] = useState(false);
  const [epicProgress, setEpicProgress] = useState<Record<string, { total: number; completed: number; percentage: number }>>({});
  const [showCreateEpicForm, setShowCreateEpicForm] = useState(false);
  const [isCreatingEpic, setIsCreatingEpic] = useState(false);
  const [createEpicError, setCreateEpicError] = useState('');
  const [newEpicName, setNewEpicName] = useState('');
  const [newEpicDescription, setNewEpicDescription] = useState('');
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [ticketsLoading, setTicketsLoading] = useState(false);
  const [showCreateTicketForm, setShowCreateTicketForm] = useState(false);
  const [isCreatingTicket, setIsCreatingTicket] = useState(false);
  const [createTicketError, setCreateTicketError] = useState('');
  const [newTicketTitle, setNewTicketTitle] = useState('');
  const [newTicketDescription, setNewTicketDescription] = useState('');
  const [newTicketPriority, setNewTicketPriority] = useState<TicketPriority | ''>('');
  const [newTicketAssignee, setNewTicketAssignee] = useState<string>('');
  const [newTicketEpic, setNewTicketEpic] = useState<string>('');
  const [users, setUsers] = useState<User[]>([]);
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterPriority, setFilterPriority] = useState<string>('');
  const [filterAssignee, setFilterAssignee] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('created_at');

  const fetchEpics = async () => {
    setEpicsLoading(true);
    try {
      const data = await apiClient.getEpics();
      setEpics(data);

      // Calculate progress for each epic in parallel
      const progressData: Record<string, { total: number; completed: number; percentage: number }> = {};

      const progressPromises = data.map(async (epic) => {
        const epicTickets = await apiClient.getEpicTickets(epic.id);
        const total = epicTickets.length;
        const completed = epicTickets.filter(t => t.status === 'DONE').length;
        const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;

        progressData[epic.id] = { total, completed, percentage };
      });

      await Promise.all(progressPromises);

      setEpicProgress(progressData);
    } catch (err) {
      console.error('Failed to load epics:', err);
    } finally {
      setEpicsLoading(false);
    }
  };

  const fetchUsers = async () => {
    try {
      const data = await apiClient.getUsers();
      setUsers(data);
    } catch (err) {
      console.error('Failed to load users:', err);
    }
  };

  const fetchTickets = useCallback(async () => {
    if (!projectId) return;

    setTicketsLoading(true);
    try {
      const data = await apiClient.getTickets(
        projectId,
        filterStatus || undefined,
        filterAssignee || undefined
      );

      // Apply client-side filtering for priority
      let filteredTickets = data;
      if (filterPriority) {
        filteredTickets = data.filter(t => t.priority === filterPriority);
      }

      // Apply client-side sorting
      const sortedTickets = [...filteredTickets].sort((a, b) => {
        switch (sortBy) {
          case 'created_at':
            return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
          case 'priority': {
            // Sort by priority: CRITICAL first, then HIGH, MEDIUM, LOW, unassigned last
            const priorityOrder: Record<string, number> = {
              CRITICAL: 0,
              HIGH: 1,
              MEDIUM: 2,
              LOW: 3
            };
            const aPriority = a.priority ? (priorityOrder[a.priority] ?? 4) : 4;
            const bPriority = b.priority ? (priorityOrder[b.priority] ?? 4) : 4;
            return aPriority - bPriority;
          }
          case 'title':
            return a.title.localeCompare(b.title);
          default:
            return 0;
        }
      });

      setTickets(sortedTickets);
    } catch (err) {
      console.error('Failed to load tickets:', err);
    } finally {
      setTicketsLoading(false);
    }
  }, [projectId, filterStatus, filterPriority, filterAssignee, sortBy]);

  useEffect(() => {
    const fetchProject = async () => {
      if (!projectId) {
        setError('No project ID provided');
        setIsLoading(false);
        return;
      }

      try {
        const data = await apiClient.getProject(projectId);
        setProject(data);
        // Fetch users, epics, and tickets after project loads successfully
        await fetchUsers();
        await fetchEpics();
        await fetchTickets();
      } catch (err) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('Failed to load project');
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchProject();
  }, [projectId, fetchTickets]);

  const handleCreateEpic = async (e: FormEvent) => {
    e.preventDefault();
    setCreateEpicError('');
    setIsCreatingEpic(true);

    try {
      await apiClient.createEpic({
        name: newEpicName,
        description: newEpicDescription || undefined,
      });

      // Reset form and close modal
      setNewEpicName('');
      setNewEpicDescription('');
      setShowCreateEpicForm(false);

      // Refresh epics list
      await fetchEpics();
    } catch (err) {
      if (err instanceof Error) {
        setCreateEpicError(err.message);
      } else {
        setCreateEpicError('Failed to create epic');
      }
    } finally {
      setIsCreatingEpic(false);
    }
  };

  const handleCreateTicket = async (e: FormEvent) => {
    e.preventDefault();
    if (!projectId) return;

    setCreateTicketError('');
    setIsCreatingTicket(true);

    try {
      const ticket = await apiClient.createTicket({
        title: newTicketTitle,
        description: newTicketDescription || undefined,
        priority: newTicketPriority || undefined,
        projectId,
        assigneeId: newTicketAssignee || undefined,
      });

      // If epic is selected, link the ticket to the epic
      if (newTicketEpic) {
        await apiClient.addTicketToEpic(newTicketEpic, ticket.id);
      }

      // Reset form and close modal
      setNewTicketTitle('');
      setNewTicketDescription('');
      setNewTicketPriority('');
      setNewTicketAssignee('');
      setNewTicketEpic('');
      setShowCreateTicketForm(false);

      // Refresh tickets list
      await fetchTickets();
    } catch (err) {
      if (err instanceof Error) {
        setCreateTicketError(err.message);
      } else {
        setCreateTicketError('Failed to create ticket');
      }
    } finally {
      setIsCreatingTicket(false);
    }
  };

  if (isLoading) {
    return (
      <>
        <Navigation />
        <div className="project-details-page">
          <div className="loading">Loading project...</div>
        </div>
      </>
    );
  }

  if (error || !project) {
    return (
      <>
        <Navigation />
        <div className="project-details-page">
          <div className="error-message">{error || 'Project not found'}</div>
          <Link to="/projects" className="back-link">
            ← Back to Projects
          </Link>
        </div>
      </>
    );
  }

  return (
    <>
      <Navigation />
      <div className="project-details-page">
        <div className="page-header">
          <div className="header-with-back">
            <Link to="/projects" className="back-link">
              ← Back to Projects
            </Link>
            <h1>{project.name}</h1>
          </div>
        </div>

        <div className="project-details-content">
          <div className="details-section">
            <h2>Project Information</h2>
            <dl className="details-list">
              <dt>Description</dt>
              <dd>{project.description || 'No description provided'}</dd>

              <dt>Status</dt>
              <dd>
                <span className={`status-badge status-${project.status}`}>
                  {project.status}
                </span>
              </dd>

              <dt>Organization ID</dt>
              <dd>{project.organization_id}</dd>

              <dt>Created</dt>
              <dd>{new Date(project.created_at).toLocaleString()}</dd>

              <dt>Last Updated</dt>
              <dd>{new Date(project.updated_at).toLocaleString()}</dd>

              <dt>Archived</dt>
              <dd>{project.is_archived ? 'Yes' : 'No'}</dd>
            </dl>
          </div>

          <div className="details-section">
            <div className="section-header">
              <h2>Epics</h2>
              <button
                onClick={() => setShowCreateEpicForm(true)}
                className="primary-button"
              >
                New Epic
              </button>
            </div>

            {epicsLoading && <div className="loading">Loading epics...</div>}

            {!epicsLoading && epics.length === 0 && (
              <p className="placeholder-text">No epics yet. Create one to get started.</p>
            )}

            {!epicsLoading && epics.length > 0 && (
              <table className="epics-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Description</th>
                    <th>Progress</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {epics.map((epic) => {
                    const progress = epicProgress[epic.id] || { total: 0, completed: 0, percentage: 0 };
                    return (
                      <tr key={epic.id}>
                        <td className="epic-name">
                          <Link to={`/epics/${epic.id}`} className="epic-link">
                            {epic.name}
                          </Link>
                        </td>
                        <td>{epic.description || '—'}</td>
                        <td className="epic-progress-cell">
                          <div className="progress-info">
                            <span className="progress-text">
                              {progress.completed} of {progress.total} tickets
                            </span>
                            <span className="progress-percentage">
                              {progress.percentage}%
                            </span>
                          </div>
                          <div className="progress-bar-container">
                            <div
                              className={`progress-bar progress-${
                                progress.percentage >= 70 ? 'high' :
                                progress.percentage >= 30 ? 'medium' : 'low'
                              }`}
                              style={{ width: `${progress.percentage}%` }}
                            />
                          </div>
                        </td>
                        <td>{new Date(epic.created_at).toLocaleDateString()}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          <div className="details-section">
            <div className="section-header">
              <h2>Tickets</h2>
              <button
                onClick={() => setShowCreateTicketForm(true)}
                className="primary-button"
              >
                New Ticket
              </button>
            </div>

            {/* Ticket Filters and Sorting */}
            <div className="ticket-filters">
              <div className="filter-group">
                <label htmlFor="filter-status">Status:</label>
                <select
                  id="filter-status"
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                >
                  <option value="">All</option>
                  <option value="TODO">TODO</option>
                  <option value="IN_PROGRESS">IN_PROGRESS</option>
                  <option value="DONE">DONE</option>
                </select>
              </div>

              <div className="filter-group">
                <label htmlFor="filter-priority">Priority:</label>
                <select
                  id="filter-priority"
                  value={filterPriority}
                  onChange={(e) => setFilterPriority(e.target.value)}
                >
                  <option value="">All</option>
                  <option value="CRITICAL">Critical</option>
                  <option value="HIGH">High</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="LOW">Low</option>
                </select>
              </div>

              <div className="filter-group">
                <label htmlFor="filter-assignee">Assignee:</label>
                <select
                  id="filter-assignee"
                  value={filterAssignee}
                  onChange={(e) => setFilterAssignee(e.target.value)}
                >
                  <option value="">All</option>
                  {users.filter(u => u.is_active).map(user => (
                    <option key={user.id} value={user.id}>
                      {user.full_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="filter-group">
                <label htmlFor="sort-by">Sort By:</label>
                <select
                  id="sort-by"
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                >
                  <option value="created_at">Created Date</option>
                  <option value="priority">Priority</option>
                  <option value="title">Title</option>
                </select>
              </div>
            </div>

            {ticketsLoading && <div className="loading">Loading tickets...</div>}

            {!ticketsLoading && tickets.length === 0 && (
              <p className="placeholder-text">No tickets yet. Create one to get started.</p>
            )}

            {!ticketsLoading && tickets.length > 0 && (
              <table className="tickets-table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Status</th>
                    <th>Priority</th>
                    <th>Assignee</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {tickets.map((ticket) => {
                    const assignee = users.find(u => u.id === ticket.assignee_id);
                    return (
                      <tr key={ticket.id}>
                        <td>
                          <Link to={`/tickets/${ticket.id}`} className="ticket-link">
                            {ticket.title}
                          </Link>
                        </td>
                        <td>
                          <span className={`status-badge status-${ticket.status.toLowerCase()}`}>
                            {ticket.status}
                          </span>
                        </td>
                        <td>
                          {ticket.priority ? (
                            <span className={`priority-badge priority-${ticket.priority.toLowerCase()}`}>
                              {ticket.priority}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td>{assignee ? assignee.full_name : 'Unassigned'}</td>
                        <td>{new Date(ticket.created_at).toLocaleDateString()}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Create Epic Modal */}
        {showCreateEpicForm && (
          <div className="modal-overlay" onClick={() => setShowCreateEpicForm(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h2>Create New Epic</h2>
                <button
                  className="close-button"
                  onClick={() => setShowCreateEpicForm(false)}
                  aria-label="Close"
                >
                  ×
                </button>
              </div>

              <form onSubmit={handleCreateEpic} className="epic-form">
                <div className="form-group">
                  <label htmlFor="epic-name">Epic Name *</label>
                  <input
                    type="text"
                    id="epic-name"
                    name="name"
                    value={newEpicName}
                    onChange={(e) => setNewEpicName(e.target.value)}
                    required
                    maxLength={255}
                    disabled={isCreatingEpic}
                    placeholder="Enter epic name"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="epic-description">Description</label>
                  <textarea
                    id="epic-description"
                    name="description"
                    value={newEpicDescription}
                    onChange={(e) => setNewEpicDescription(e.target.value)}
                    maxLength={1000}
                    disabled={isCreatingEpic}
                    placeholder="Enter epic description (optional)"
                    rows={4}
                  />
                </div>

                {createEpicError && <div className="error-message">{createEpicError}</div>}

                <div className="form-actions">
                  <button
                    type="button"
                    onClick={() => setShowCreateEpicForm(false)}
                    className="secondary-button"
                    disabled={isCreatingEpic}
                  >
                    Cancel
                  </button>
                  <button type="submit" className="primary-button" disabled={isCreatingEpic}>
                    {isCreatingEpic ? 'Creating...' : 'Create Epic'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Create Ticket Modal */}
        {showCreateTicketForm && (
          <div className="modal-overlay" onClick={() => setShowCreateTicketForm(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h2>Create New Ticket</h2>
                <button
                  className="close-button"
                  onClick={() => setShowCreateTicketForm(false)}
                  aria-label="Close"
                >
                  ×
                </button>
              </div>

              <form onSubmit={handleCreateTicket} className="ticket-form">
                <div className="form-group">
                  <label htmlFor="ticket-title">Title *</label>
                  <input
                    type="text"
                    id="ticket-title"
                    name="title"
                    value={newTicketTitle}
                    onChange={(e) => setNewTicketTitle(e.target.value)}
                    required
                    maxLength={500}
                    disabled={isCreatingTicket}
                    placeholder="Enter ticket title"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="ticket-description">Description</label>
                  <textarea
                    id="ticket-description"
                    name="description"
                    value={newTicketDescription}
                    onChange={(e) => setNewTicketDescription(e.target.value)}
                    maxLength={2000}
                    disabled={isCreatingTicket}
                    placeholder="Enter ticket description (optional)"
                    rows={4}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="ticket-priority">Priority</label>
                  <select
                    id="ticket-priority"
                    name="priority"
                    value={newTicketPriority}
                    onChange={(e) => setNewTicketPriority(e.target.value as TicketPriority | '')}
                    disabled={isCreatingTicket}
                  >
                    <option value="">None</option>
                    <option value={TicketPriority.LOW}>Low</option>
                    <option value={TicketPriority.MEDIUM}>Medium</option>
                    <option value={TicketPriority.HIGH}>High</option>
                    <option value={TicketPriority.CRITICAL}>Critical</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="ticket-assignee">Assign To</label>
                  <select
                    id="ticket-assignee"
                    name="assignee"
                    value={newTicketAssignee}
                    onChange={(e) => setNewTicketAssignee(e.target.value)}
                    disabled={isCreatingTicket}
                  >
                    <option value="">Unassigned</option>
                    {users.filter(u => u.is_active).map(user => (
                      <option key={user.id} value={user.id}>
                        {user.full_name} ({user.username})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="ticket-epic">Epic</label>
                  <select
                    id="ticket-epic"
                    name="epic"
                    value={newTicketEpic}
                    onChange={(e) => setNewTicketEpic(e.target.value)}
                    disabled={isCreatingTicket}
                  >
                    <option value="">No Epic</option>
                    {epics.map(epic => (
                      <option key={epic.id} value={epic.id}>
                        {epic.name}
                      </option>
                    ))}
                  </select>
                </div>

                {createTicketError && <div className="error-message">{createTicketError}</div>}

                <div className="form-actions">
                  <button
                    type="button"
                    onClick={() => setShowCreateTicketForm(false)}
                    className="secondary-button"
                    disabled={isCreatingTicket}
                  >
                    Cancel
                  </button>
                  <button type="submit" className="primary-button" disabled={isCreatingTicket}>
                    {isCreatingTicket ? 'Creating...' : 'Create Ticket'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
