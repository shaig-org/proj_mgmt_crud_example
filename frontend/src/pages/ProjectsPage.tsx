import { useState, useEffect, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import apiClient, { Project } from '../services/api';
import { Navigation } from '../components/Navigation';

export function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDescription, setNewProjectDescription] = useState('');

  const fetchProjects = async () => {
    try {
      const data = await apiClient.getProjects();
      setProjects(data);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to load projects');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleCreateProject = async (e: FormEvent) => {
    e.preventDefault();
    setCreateError('');
    setIsCreating(true);

    try {
      await apiClient.createProject({
        name: newProjectName,
        description: newProjectDescription || undefined,
      });

      // Reset form and close modal
      setNewProjectName('');
      setNewProjectDescription('');
      setShowCreateForm(false);

      // Refresh projects list
      await fetchProjects();
    } catch (err) {
      if (err instanceof Error) {
        setCreateError(err.message);
      } else {
        setCreateError('Failed to create project');
      }
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <>
      <Navigation />
      <div className="projects-page">
        <header className="page-header">
          <h1>Projects</h1>
          <div className="header-actions">
            <button onClick={() => setShowCreateForm(true)} className="primary-button">
              New Project
            </button>
          </div>
        </header>

      {isLoading && <div className="loading">Loading projects...</div>}

      {error && <div className="error-message">{error}</div>}

      {!isLoading && !error && (
        <div className="projects-list">
          {projects.length === 0 ? (
            <p>No projects found</p>
          ) : (
            <table className="projects-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Description</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((project) => (
                  <tr key={project.id}>
                    <td>
                      <Link to={`/projects/${project.id}`} className="project-link">
                        {project.name}
                      </Link>
                    </td>
                    <td>{project.description}</td>
                    <td>
                      <span className={`status-badge status-${project.status}`}>
                        {project.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Create Project Modal */}
      {showCreateForm && (
        <div className="modal-overlay" onClick={() => setShowCreateForm(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create New Project</h2>
              <button
                className="close-button"
                onClick={() => setShowCreateForm(false)}
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreateProject} className="project-form">
              <div className="form-group">
                <label htmlFor="project-name">Project Name *</label>
                <input
                  type="text"
                  id="project-name"
                  name="name"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  required
                  maxLength={255}
                  disabled={isCreating}
                  placeholder="Enter project name"
                />
              </div>

              <div className="form-group">
                <label htmlFor="project-description">Description</label>
                <textarea
                  id="project-description"
                  name="description"
                  value={newProjectDescription}
                  onChange={(e) => setNewProjectDescription(e.target.value)}
                  maxLength={1000}
                  disabled={isCreating}
                  placeholder="Enter project description (optional)"
                  rows={4}
                />
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
                  {isCreating ? 'Creating...' : 'Create Project'}
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
