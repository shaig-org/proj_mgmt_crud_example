import { useState, useEffect, FormEvent } from 'react';
import apiClient, { User, Organization, UserCreateResponse } from '../services/api';
import { Navigation } from '../components/Navigation';

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const [newUserUsername, setNewUserUsername] = useState('');
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserFullName, setNewUserFullName] = useState('');
  const [newUserOrganizationId, setNewUserOrganizationId] = useState('');
  const [newUserRole, setNewUserRole] = useState('read_access');
  const [createdUser, setCreatedUser] = useState<UserCreateResponse | null>(null);

  const fetchUsers = async () => {
    try {
      const data = await apiClient.getUsers();
      setUsers(data);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to load users');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const fetchOrganizations = async () => {
    try {
      const data = await apiClient.getOrganizations();
      setOrganizations(data);
      // Set first organization as default if available
      if (data.length > 0 && !newUserOrganizationId) {
        setNewUserOrganizationId(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load organizations:', err);
    }
  };

  useEffect(() => {
    fetchUsers();
    fetchOrganizations();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleCreateUser = async (e: FormEvent) => {
    e.preventDefault();
    setCreateError('');
    setIsCreating(true);
    setCreatedUser(null);

    try {
      const response = await apiClient.createUser({
        username: newUserUsername,
        email: newUserEmail,
        full_name: newUserFullName,
        organization_id: newUserOrganizationId,
        role: newUserRole,
      });

      // Store the created user response (includes generated password)
      setCreatedUser(response);

      // Refresh users list
      await fetchUsers();
    } catch (err) {
      if (err instanceof Error) {
        setCreateError(err.message);
      } else {
        setCreateError('Failed to create user');
      }
    } finally {
      setIsCreating(false);
    }
  };

  const handleCloseSuccessModal = () => {
    // Reset form and close modal
    setNewUserUsername('');
    setNewUserEmail('');
    setNewUserFullName('');
    setNewUserRole('read_access');
    setCreatedUser(null);
    setShowCreateForm(false);
  };

  return (
    <>
      <Navigation />
      <div className="users-page">
        <header className="page-header">
          <h1>Users</h1>
          <div className="header-actions">
            <button onClick={() => setShowCreateForm(true)} className="primary-button">
              New User
            </button>
          </div>
        </header>

      {isLoading && <div className="loading">Loading users...</div>}

      {error && <div className="error-message">{error}</div>}

      {!isLoading && !error && (
        <div className="users-list">
          {users.length === 0 ? (
            <p>No users found</p>
          ) : (
            <table className="users-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Full Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.username}</td>
                    <td>{user.full_name}</td>
                    <td>{user.email}</td>
                    <td>
                      <span className={`role-badge role-${user.role}`}>{user.role}</span>
                    </td>
                    <td>
                      <span className={`status-badge ${user.is_active ? 'status-active' : 'status-inactive'}`}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Create User Modal */}
      {showCreateForm && !createdUser && (
        <div className="modal-overlay" onClick={() => setShowCreateForm(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create New User</h2>
              <button
                className="close-button"
                onClick={() => setShowCreateForm(false)}
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="user-form">
              <div className="form-group">
                <label htmlFor="user-username">Username *</label>
                <input
                  type="text"
                  id="user-username"
                  name="username"
                  value={newUserUsername}
                  onChange={(e) => setNewUserUsername(e.target.value)}
                  required
                  maxLength={50}
                  disabled={isCreating}
                  placeholder="Enter username"
                />
              </div>

              <div className="form-group">
                <label htmlFor="user-email">Email *</label>
                <input
                  type="email"
                  id="user-email"
                  name="email"
                  value={newUserEmail}
                  onChange={(e) => setNewUserEmail(e.target.value)}
                  required
                  maxLength={255}
                  disabled={isCreating}
                  placeholder="Enter email address"
                />
              </div>

              <div className="form-group">
                <label htmlFor="user-full-name">Full Name *</label>
                <input
                  type="text"
                  id="user-full-name"
                  name="full_name"
                  value={newUserFullName}
                  onChange={(e) => setNewUserFullName(e.target.value)}
                  required
                  maxLength={255}
                  disabled={isCreating}
                  placeholder="Enter full name"
                />
              </div>

              <div className="form-group">
                <label htmlFor="user-organization">Organization *</label>
                <select
                  id="user-organization"
                  name="organization_id"
                  value={newUserOrganizationId}
                  onChange={(e) => setNewUserOrganizationId(e.target.value)}
                  required
                  disabled={isCreating}
                >
                  {organizations.length === 0 && <option value="">No organizations available</option>}
                  {organizations.map((org) => (
                    <option key={org.id} value={org.id}>
                      {org.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="user-role">Role *</label>
                <select
                  id="user-role"
                  name="role"
                  value={newUserRole}
                  onChange={(e) => setNewUserRole(e.target.value)}
                  required
                  disabled={isCreating}
                >
                  <option value="read_access">Read Access</option>
                  <option value="write_access">Write Access</option>
                  <option value="project_manager">Project Manager</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              {createError && <div className="error-message">{createError}</div>}

              <div className="form-actions">
                <button
                  type="button"
                  onClick={() => setShowCreateForm(false)}
                  className="secondary-button"
                  disabled={isCreating}
                >
                  Cancel
                </button>
                <button type="submit" className="primary-button" disabled={isCreating}>
                  {isCreating ? 'Creating...' : 'Create User'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Success Modal with Generated Password */}
      {createdUser && (
        <div className="modal-overlay" onClick={handleCloseSuccessModal}>
          <div className="modal-content success-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>User Created Successfully!</h2>
              <button
                className="close-button"
                onClick={handleCloseSuccessModal}
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <div className="success-content">
              <p>
                User <strong>{createdUser.user.username}</strong> has been created successfully.
              </p>

              <div className="password-display">
                <h3>Generated Password</h3>
                <div className="password-box">
                  <code>{createdUser.generated_password}</code>
                </div>
                <p className="password-warning">
                  ⚠️ <strong>Important:</strong> Save this password now. It cannot be retrieved later.
                </p>
              </div>

              <div className="user-details">
                <h3>User Details</h3>
                <dl>
                  <dt>Username:</dt>
                  <dd>{createdUser.user.username}</dd>
                  <dt>Email:</dt>
                  <dd>{createdUser.user.email}</dd>
                  <dt>Full Name:</dt>
                  <dd>{createdUser.user.full_name}</dd>
                  <dt>Role:</dt>
                  <dd>{createdUser.user.role}</dd>
                </dl>
              </div>

              <div className="form-actions">
                <button onClick={handleCloseSuccessModal} className="primary-button">
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      </div>
    </>
  );
}
