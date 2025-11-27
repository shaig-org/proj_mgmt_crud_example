import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import apiClient, { Epic, Ticket } from '../services/api';
import { Navigation } from '../components/Navigation';

export function EpicDetailsPage() {
  const { epicId } = useParams<{ epicId: string }>();
  const [epic, setEpic] = useState<Epic | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('created_at');

  useEffect(() => {
    const fetchEpicAndTickets = async () => {
      if (!epicId) {
        setError('No epic ID provided');
        setIsLoading(false);
        return;
      }

      try {
        const [epicData, ticketsData] = await Promise.all([
          apiClient.getEpic(epicId),
          apiClient.getEpicTickets(epicId),
        ]);
        setEpic(epicData);
        setTickets(ticketsData);
      } catch (err) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('Failed to load epic');
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchEpicAndTickets();
  }, [epicId]);

  if (isLoading) {
    return (
      <>
        <Navigation />
        <div className="epic-details-page">
          <div className="loading">Loading epic...</div>
        </div>
      </>
    );
  }

  if (error || !epic) {
    return (
      <>
        <Navigation />
        <div className="epic-details-page">
          <div className="error-message">{error || 'Epic not found'}</div>
        </div>
      </>
    );
  }

  // Apply filtering
  const filteredTickets = filterStatus
    ? tickets.filter(t => t.status === filterStatus)
    : tickets;

  // Apply sorting
  const sortedTickets = [...filteredTickets].sort((a, b) => {
    switch (sortBy) {
      case 'created_at':
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      case 'priority': {
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
      case 'status':
        return a.status.localeCompare(b.status);
      default:
        return 0;
    }
  });

  // Calculate progress
  const totalTickets = tickets.length;
  const completedTickets = tickets.filter(t => t.status === 'DONE').length;
  const progressPercentage = totalTickets > 0 ? Math.round((completedTickets / totalTickets) * 100) : 0;
  const progressColor = progressPercentage >= 70 ? 'high' : progressPercentage >= 30 ? 'medium' : 'low';

  return (
    <>
      <Navigation />
      <div className="epic-details-page">
        <div className="page-header">
          <div className="header-with-back">
            <Link to="/projects" className="back-link">
              ← Back to Projects
            </Link>
            <h1>{epic.name}</h1>
          </div>
        </div>

        <div className="epic-details-content">
          <div className="details-section">
            <h2>Epic Information</h2>
            <dl className="details-list">
              <dt>Description</dt>
              <dd>{epic.description || 'No description provided'}</dd>

              <dt>Progress</dt>
              <dd>
                <div className="progress-display">
                  <div className="progress-info">
                    <span className="progress-text">
                      {completedTickets} of {totalTickets} tickets completed
                    </span>
                    <span className="progress-percentage">
                      {progressPercentage}%
                    </span>
                  </div>
                  <div className="progress-bar-container">
                    <div
                      className={`progress-bar progress-${progressColor}`}
                      style={{ width: `${progressPercentage}%` }}
                    />
                  </div>
                </div>
              </dd>

              <dt>Created</dt>
              <dd>{new Date(epic.created_at).toLocaleString()}</dd>

              <dt>Last Updated</dt>
              <dd>{new Date(epic.updated_at).toLocaleString()}</dd>
            </dl>
          </div>

          <div className="tickets-section">
            <div className="section-header">
              <h2>Tickets ({sortedTickets.length})</h2>
            </div>

            <div className="filters">
              <div className="filter-group">
                <label htmlFor="status-filter">Status:</label>
                <select
                  id="status-filter"
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
                <label htmlFor="sort-by">Sort By:</label>
                <select
                  id="sort-by"
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                >
                  <option value="created_at">Created Date</option>
                  <option value="priority">Priority</option>
                  <option value="title">Title</option>
                  <option value="status">Status</option>
                </select>
              </div>
            </div>

            {sortedTickets.length === 0 ? (
              <p className="no-tickets">
                {filterStatus
                  ? `No tickets with status ${filterStatus}`
                  : 'No tickets in this epic yet'}
              </p>
            ) : (
              <table className="tickets-table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Status</th>
                    <th>Priority</th>
                    <th>Project</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedTickets.map(ticket => (
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
                      <td>{ticket.project_id}</td>
                      <td>{new Date(ticket.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <style>{`
          .epic-details-page {
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

          .epic-details-content {
            max-width: 1200px;
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

          .progress-display {
            max-width: 400px;
          }

          .progress-info {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
            font-size: 0.875rem;
          }

          .progress-text {
            color: #666;
          }

          .progress-percentage {
            font-weight: 600;
            color: #333;
          }

          .progress-bar-container {
            width: 100%;
            height: 8px;
            background-color: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
          }

          .progress-bar {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
          }

          .progress-bar.progress-low {
            background-color: #ff6b6b;
          }

          .progress-bar.progress-medium {
            background-color: #ffd43b;
          }

          .progress-bar.progress-high {
            background-color: #51cf66;
          }

          .tickets-section {
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
          }

          .section-header {
            margin-bottom: 1.5rem;
          }

          .section-header h2 {
            margin: 0;
            color: #333;
          }

          .filters {
            display: flex;
            gap: 1.5rem;
            margin-bottom: 1.5rem;
            padding: 1rem;
            background: #f5f5f5;
            border-radius: 4px;
          }

          .filter-group {
            display: flex;
            align-items: center;
            gap: 0.5rem;
          }

          .filter-group label {
            font-size: 0.875rem;
            font-weight: 500;
            color: #666;
          }

          .filter-group select {
            padding: 0.5rem;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 0.875rem;
            background: white;
            cursor: pointer;
          }

          .no-tickets {
            text-align: center;
            padding: 2rem;
            color: #666;
            font-style: italic;
          }

          .tickets-table {
            width: 100%;
            border-collapse: collapse;
          }

          .tickets-table th {
            text-align: left;
            padding: 0.75rem;
            background: #f5f5f5;
            border-bottom: 2px solid #ddd;
            font-weight: 600;
            color: #333;
          }

          .tickets-table td {
            padding: 0.75rem;
            border-bottom: 1px solid #eee;
          }

          .tickets-table tbody tr:hover {
            background: #f9f9f9;
          }

          .ticket-link {
            color: #1976d2;
            text-decoration: none;
            font-weight: 500;
          }

          .ticket-link:hover {
            text-decoration: underline;
          }

          .status-badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
          }

          .status-todo {
            background: #e3f2fd;
            color: #1976d2;
          }

          .status-in_progress {
            background: #fff3e0;
            color: #f57c00;
          }

          .status-done {
            background: #e8f5e9;
            color: #388e3c;
          }

          .priority-badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-weight: 500;
            font-size: 0.75rem;
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

          .loading {
            text-align: center;
            padding: 2rem;
            color: #666;
          }

          .error-message {
            background: #ffebee;
            color: #c62828;
            padding: 1rem;
            border-radius: 4px;
            margin: 1rem 0;
          }
        `}</style>
      </div>
    </>
  );
}
