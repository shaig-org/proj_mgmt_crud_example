import { useState, useEffect } from 'react';
import apiClient, { Organization } from '../services/api';
import { Navigation } from '../components/Navigation';

export function OrganizationsPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formData, setFormData] = useState({ name: '', description: '' });
  const [formError, setFormError] = useState('');

  useEffect(() => {
    fetchOrganizations();
  }, []);

  const fetchOrganizations = async () => {
    try {
      const data = await apiClient.getOrganizations();
      setOrganizations(data);
      setError('');
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to load organizations');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');

    if (!formData.name.trim()) {
      setFormError('Organization name is required');
      return;
    }

    try {
      await apiClient.createOrganization(formData);
      setFormData({ name: '', description: '' });
      setShowCreateForm(false);
      await fetchOrganizations();
    } catch (err) {
      if (err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError('Failed to create organization');
      }
    }
  };

  return (
    <>
      <Navigation />
      <div className="organizations-page">
        <header className="page-header">
          <h1>Organizations</h1>
          <button
            onClick={() => setShowCreateForm(true)}
            className="primary-button"
          >
            New Organization
          </button>
        </header>

        {isLoading && <div className="loading">Loading organizations...</div>}

        {error && <div className="error-message">{error}</div>}

        {!isLoading && !error && organizations.length === 0 && (
          <p className="placeholder-text">No organizations found</p>
        )}

        {!isLoading && !error && organizations.length > 0 && (
          <table className="organizations-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {organizations.map((org) => (
                <tr key={org.id}>
                  <td className="org-name">{org.name}</td>
                  <td>{org.description || '—'}</td>
                  <td>{new Date(org.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {showCreateForm && (
          <div className="modal-overlay" onClick={() => setShowCreateForm(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h2>Create New Organization</h2>
                <button
                  onClick={() => setShowCreateForm(false)}
                  className="close-button"
                >
                  ×
                </button>
              </div>

              <form onSubmit={handleSubmit} className="modal-form">
                <div className="form-field">
                  <label htmlFor="org-name">Organization Name *</label>
                  <input
                    id="org-name"
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="Enter organization name"
                    required
                  />
                </div>

                <div className="form-field">
                  <label htmlFor="org-description">Description</label>
                  <textarea
                    id="org-description"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Enter organization description (optional)"
                    rows={3}
                  />
                </div>

                {formError && <div className="form-error">{formError}</div>}

                <div className="form-actions">
                  <button
                    type="button"
                    onClick={() => setShowCreateForm(false)}
                    className="secondary-button"
                  >
                    Cancel
                  </button>
                  <button type="submit" className="primary-button">
                    Create Organization
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        <style>{`
          .organizations-page {
            padding: 2rem;
          }

          .page-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
          }

          .page-header h1 {
            margin: 0;
          }

          .loading, .placeholder-text {
            text-align: center;
            padding: 2rem;
            color: #666;
          }

          .error-message {
            background: #ffebee;
            color: #c62828;
            padding: 1rem;
            border-radius: 4px;
            margin-bottom: 1rem;
          }

          .organizations-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            border-radius: 8px;
            overflow: hidden;
          }

          .organizations-table th {
            text-align: left;
            padding: 1rem;
            background: #f5f5f5;
            border-bottom: 2px solid #ddd;
            font-weight: 600;
            color: #333;
          }

          .organizations-table td {
            padding: 1rem;
            border-bottom: 1px solid #eee;
          }

          .organizations-table tbody tr:hover {
            background: #f9f9f9;
          }

          .org-name {
            font-weight: 500;
            color: #1976d2;
          }
        `}</style>
      </div>
    </>
  );
}
