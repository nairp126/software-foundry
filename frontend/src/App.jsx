import { useState, useEffect, useRef } from 'react';
import {
  fetchProjects, fetchProject, fetchArtifacts, createProject, deleteProject,
  fetchApproval, approveProject, rejectProject, connectProjectWebSocket
} from './api';
import './App.css';

/* ─── Status helpers ─── */
function statusClass(status) {
  if (status === 'completed') return 'badge-completed';
  if (status === 'failed') return 'badge-failed';
  if (status === 'created') return 'badge-created';
  return 'badge-running';
}

function statusLabel(status) {
  return status.replace(/_/g, ' ');
}

/* ─── New Project Modal ─── */
function NewProjectModal({ onClose, onCreated }) {
  const [name, setName] = useState('');
  const [requirements, setRequirements] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const project = await createProject({ name, requirements, description });
      onCreated(project);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>🚀 New Project</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Project Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Awesome App"
              required
            />
          </div>
          <div className="form-group">
            <label>Requirements</label>
            <textarea
              value={requirements}
              onChange={(e) => setRequirements(e.target.value)}
              placeholder="Build a REST API with user authentication and a React frontend..."
              required
            />
          </div>
          <div className="form-group">
            <label>Description (optional)</label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Short description of the project"
            />
          </div>
          {error && <p style={{ color: 'var(--danger)', fontSize: '0.85rem' }}>{error}</p>}
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? <span className="spinner" /> : 'Create Project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ─── Project Detail View ─── */
function ProjectDetail({ projectId, onBack }) {
  const [project, setProject] = useState(null);
  const [artifacts, setArtifacts] = useState([]);
  const [approval, setApproval] = useState(null);
  const [loading, setLoading] = useState(true);
  const [approvalComment, setApprovalComment] = useState('');
  const wsRef = useRef(null);

  useEffect(() => {
    async function load() {
      try {
        const [p, a, ap] = await Promise.all([
          fetchProject(projectId),
          fetchArtifacts(projectId),
          fetchApproval(projectId),
        ]);
        setProject(p);
        setArtifacts(a);
        setApproval(ap);
      } catch { /* ignore */ }
      finally { setLoading(false); }
    }
    load();

    // WebSocket for live status
    wsRef.current = connectProjectWebSocket(projectId, (msg) => {
      if (msg.type === 'status_update') {
        setProject((prev) => prev ? { ...prev, status: msg.status } : prev);
      }
    });

    return () => { if (wsRef.current) wsRef.current.close(); };
  }, [projectId]);

  async function handleApprove() {
    try {
      const result = await approveProject(projectId, approvalComment);
      setApproval(result);
    } catch { /* ignore */ }
  }

  async function handleReject() {
    try {
      const result = await rejectProject(projectId, approvalComment);
      setApproval(result);
      setProject((prev) => prev ? { ...prev, status: 'failed' } : prev);
    } catch { /* ignore */ }
  }

  if (loading) return <div className="loading-center"><span className="spinner" /></div>;
  if (!project) return <div className="empty-state"><h3>Project not found</h3></div>;

  return (
    <div>
      <div className="detail-header">
        <button className="btn btn-ghost" onClick={onBack}>← Back</button>
        <h2>{project.name}</h2>
        <span className={`badge ${statusClass(project.status)}`}>{statusLabel(project.status)}</span>
      </div>

      {/* ─── Approval Gate ─── */}
      {approval && approval.status === 'pending' && (
        <div className="detail-section" style={{ border: '1px solid var(--accent)', borderRadius: '0.5rem', padding: '1rem', marginBottom: '1rem' }}>
          <h3>⏸️ Approval Required — {approval.stage}</h3>
          <p style={{ fontSize: '0.9rem', marginBottom: '0.75rem' }}>The pipeline is paused and waiting for your decision.</p>
          <div className="form-group">
            <textarea
              value={approvalComment}
              onChange={(e) => setApprovalComment(e.target.value)}
              placeholder="Optional reviewer comment…"
              rows={2}
              style={{ resize: 'vertical' }}
            />
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn btn-primary" onClick={handleApprove}>✅ Approve</button>
            <button className="btn btn-danger" onClick={handleReject}>❌ Reject</button>
          </div>
        </div>
      )}
      {approval && approval.status !== 'pending' && (
        <div className="detail-section" style={{ marginBottom: '1rem' }}>
          <h3>{approval.status === 'approved' ? '✅' : '❌'} {approval.status.toUpperCase()} — {approval.stage}</h3>
          {approval.reviewer_comment && <p style={{ fontSize: '0.85rem', fontStyle: 'italic' }}>{approval.reviewer_comment}</p>}
        </div>
      )}

      <div className="detail-grid">
        <div className="detail-section">
          <h3>Requirements</h3>
          <p style={{ fontSize: '0.9rem', lineHeight: 1.6 }}>{project.requirements}</p>
        </div>

        {project.prd && (
          <div className="detail-section">
            <h3>📋 PRD</h3>
            <pre>{typeof project.prd === 'string' ? project.prd : JSON.stringify(project.prd, null, 2)}</pre>
          </div>
        )}

        {project.architecture && (
          <div className="detail-section">
            <h3>🏗️ Architecture</h3>
            <pre>{typeof project.architecture === 'string' ? project.architecture : JSON.stringify(project.architecture, null, 2)}</pre>
          </div>
        )}

        {project.code_review && (
          <div className="detail-section">
            <h3>🔍 Code Review</h3>
            <pre>{typeof project.code_review === 'string' ? project.code_review : JSON.stringify(project.code_review, null, 2)}</pre>
          </div>
        )}
      </div>

      {artifacts.length > 0 && (
        <div className="detail-section" style={{ marginTop: '1rem' }}>
          <h3>📁 Generated Artifacts ({artifacts.length})</h3>
          <ul className="artifact-list">
            {artifacts.map((a) => (
              <li key={a.id} className="artifact-item">
                <div className="artifact-icon">📄</div>
                <div>
                  <div style={{ fontWeight: 600 }}>{a.filename}</div>
                  <div className="card-meta">{a.artifact_type}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {project.generated_path && (
        <p className="card-meta" style={{ marginTop: '1rem' }}>
          📂 Output: <code>{project.generated_path}</code>
        </p>
      )}
    </div>
  );
}

/* ─── Main App ─── */
function App() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [selectedProject, setSelectedProject] = useState(null);

  async function loadProjects() {
    try {
      const data = await fetchProjects();
      setProjects(data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProjects();
    const interval = setInterval(loadProjects, 8000);
    return () => clearInterval(interval);
  }, []);

  async function handleDelete(id) {
    if (!confirm('Delete this project?')) return;
    await deleteProject(id);
    setProjects((prev) => prev.filter((p) => p.id !== id));
  }

  if (selectedProject) {
    return (
      <div className="app">
        <header className="header">
          <h1>⚙️ Software Foundry</h1>
        </header>
        <main className="main">
          <ProjectDetail
            projectId={selectedProject}
            onBack={() => setSelectedProject(null)}
          />
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <h1>⚙️ Software Foundry</h1>
        <nav>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            + New Project
          </button>
        </nav>
      </header>

      <main className="main">
        {loading ? (
          <div className="loading-center"><span className="spinner" /></div>
        ) : projects.length === 0 ? (
          <div className="empty-state">
            <h3>No projects yet</h3>
            <p>Create your first project to get started.</p>
            <button
              className="btn btn-primary"
              style={{ marginTop: '1rem' }}
              onClick={() => setShowModal(true)}
            >
              + New Project
            </button>
          </div>
        ) : (
          <div className="project-grid">
            {projects.map((p) => (
              <div
                key={p.id}
                className="card"
                onClick={() => setSelectedProject(p.id)}
                style={{ cursor: 'pointer' }}
              >
                <div className="card-header">
                  <span className="card-title">{p.name}</span>
                  <span className={`badge ${statusClass(p.status)}`}>
                    {statusLabel(p.status)}
                  </span>
                </div>
                <div className="card-meta">
                  Created {new Date(p.created_at).toLocaleDateString()}
                </div>
                <div style={{ marginTop: '0.75rem', textAlign: 'right' }}>
                  <button
                    className="btn btn-danger"
                    onClick={(e) => { e.stopPropagation(); handleDelete(p.id); }}
                    style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {showModal && (
        <NewProjectModal
          onClose={() => setShowModal(false)}
          onCreated={(proj) => {
            setProjects((prev) => [proj, ...prev]);
          }}
        />
      )}
    </div>
  );
}

export default App;
