const API_BASE = '/api';

export async function fetchProjects(skip = 0, limit = 20) {
    const res = await fetch(`${API_BASE}/projects?skip=${skip}&limit=${limit}`);
    if (!res.ok) throw new Error('Failed to fetch projects');
    return res.json();
}

export async function fetchProject(id) {
    const res = await fetch(`${API_BASE}/projects/${id}`);
    if (!res.ok) throw new Error('Failed to fetch project');
    return res.json();
}

export async function fetchArtifacts(projectId) {
    const res = await fetch(`${API_BASE}/projects/${projectId}/artifacts`);
    if (!res.ok) throw new Error('Failed to fetch artifacts');
    return res.json();
}

export async function createProject({ name, requirements, description }) {
    const res = await fetch(`${API_BASE}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, requirements, description }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to create project');
    }
    return res.json();
}

export async function deleteProject(id) {
    const res = await fetch(`${API_BASE}/projects/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete project');
}

// ---- Approval Workflow ---- //

export async function fetchApproval(projectId) {
    const res = await fetch(`${API_BASE}/projects/${projectId}/approval`);
    if (!res.ok) return null;
    const data = await res.json();
    return data; // may be null if no approval exists
}

export async function approveProject(projectId, comment = '') {
    const res = await fetch(`${API_BASE}/projects/${projectId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment }),
    });
    if (!res.ok) throw new Error('Failed to approve project');
    return res.json();
}

export async function rejectProject(projectId, comment = '') {
    const res = await fetch(`${API_BASE}/projects/${projectId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment }),
    });
    if (!res.ok) throw new Error('Failed to reject project');
    return res.json();
}

// ---- WebSocket ---- //

export function connectProjectWebSocket(projectId, onMessage) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/projects/${projectId}`);
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            onMessage(data);
        } catch { /* ignore parse errors */ }
    };
    ws.onerror = () => { /* silent reconnect handled by caller */ };
    return ws;
}
