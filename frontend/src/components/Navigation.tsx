import { NavLink } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export function Navigation() {
  const { user, logout } = useAuth();

  if (!user) {
    return null;
  }

  // Determine which navigation items to show based on role
  const showUsers = user.role === 'super_admin' || user.role === 'admin';
  const showOrganizations = user.role === 'super_admin';

  return (
    <nav className="main-navigation">
      <div className="nav-container">
        <div className="nav-brand">
          <h1>Project Management</h1>
        </div>

        <div className="nav-links">
          <NavLink to="/projects" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            Projects
          </NavLink>

          {showUsers && (
            <NavLink to="/users" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Users
            </NavLink>
          )}

          {showOrganizations && (
            <NavLink to="/organizations" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Organizations
            </NavLink>
          )}
        </div>

        <div className="nav-user">
          <span className="user-info">
            {user.username} ({user.role})
          </span>
          <button onClick={logout} className="logout-button">
            Logout
          </button>
        </div>
      </div>
    </nav>
  );
}
