import { NavLink } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

// Simple SVG icons as components
const ProjectsIcon = () => (
  <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
  </svg>
);

const UsersIcon = () => (
  <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);

const OrganizationsIcon = () => (
  <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    <polyline points="9 22 9 12 15 12 15 22" />
  </svg>
);

const LogoutIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <polyline points="16 17 21 12 16 7" />
    <line x1="21" y1="12" x2="9" y2="12" />
  </svg>
);

export function Navigation() {
  const { user, logout } = useAuth();

  if (!user) {
    return null;
  }

  // Determine which navigation items to show based on role
  const showUsers = user.role === 'super_admin' || user.role === 'admin';
  const showOrganizations = user.role === 'super_admin';

  // Get user initials for avatar
  const getInitials = (username: string) => {
    return username.slice(0, 2).toUpperCase();
  };

  // Format role for display
  const formatRole = (role: string) => {
    return role.replace(/_/g, ' ');
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <div className="sidebar-logo">PM</div>
          <h1 className="sidebar-title">Project Hub</h1>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section">
          <div className="nav-section-label">Main Menu</div>

          <NavLink
            to="/projects"
            className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}
          >
            <ProjectsIcon />
            Projects
          </NavLink>

          {showUsers && (
            <NavLink
              to="/users"
              className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}
            >
              <UsersIcon />
              Users
            </NavLink>
          )}

          {showOrganizations && (
            <NavLink
              to="/organizations"
              className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}
            >
              <OrganizationsIcon />
              Organizations
            </NavLink>
          )}
        </div>
      </nav>

      <div className="sidebar-footer">
        <div className="user-menu">
          <div className="user-avatar">
            {getInitials(user.username)}
          </div>
          <div className="user-details">
            <div className="user-name">{user.username}</div>
            <div className="user-role">{formatRole(user.role)}</div>
          </div>
          <button onClick={logout} className="logout-btn" title="Logout">
            <LogoutIcon />
          </button>
        </div>
      </div>
    </aside>
  );
}
