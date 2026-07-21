/**
 * src/services/api.js
 *
 * Thin wrapper around fetch() that always hits the FastAPI backend.
 * Base URL is read from window.electronAPI at call time so it can be
 * changed at runtime without re-importing.
 */

async function base() {
  if (window.electronAPI) {
    return await window.electronAPI.getBackendUrl();
  }
  return "http://localhost:8000";
}

async function get(path) {
  const url = `${await base()}${path}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

async function post(path, body) {
  const url = `${await base()}${path}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`POST ${path} → ${res.status}: ${err}`);
  }
  return res.json();
}

export const api = {
  // Health
  health: () => get("/health"),

  // Meetings
  listMeetings: () => get("/api/meetings"),
  upcomingMeetings: () => get("/api/meetings/upcoming"),
  recentMeetings: () => get("/api/meetings/recent"),
  getMeeting: (id) => get(`/api/meetings/${id}`),
  getTranscript: (id, q = "") =>
    get(
      `/api/meetings/${id}/transcript${q ? `?q=${encodeURIComponent(q)}` : ""}`,
    ),
  getMeetingStatus: (id) => get(`/api/meetings/${id}/status`),

  joinBot: (id) => post(`/api/meetings/${id}/join-bot`, {}),
  setAutoJoin: (id, enabled) =>
    post(`/api/meetings/${id}/auto-join`, { enabled }),
  finalizeMeeting: (id) => post(`/api/meetings/${id}/finalize`, {}),

  // Tasks
  getTask: (id) => get(`/api/tasks/${id}`),

  // Approvals
  listApprovals: () => get("/api/approvals/queue"),
  decideApproval: (taskId, payload) =>
    post(`/api/approvals/${taskId}/decision`, payload),
};
