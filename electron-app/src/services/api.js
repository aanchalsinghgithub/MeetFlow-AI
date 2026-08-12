/**
 * Thin wrapper around fetch() that always hits the FastAPI backend.
 * Base URL and JWT are read from Electron at call time so both can change
 * without re-importing this module.
 */

async function base() {
  if (window.electronAPI) {
    return await window.electronAPI.getBackendUrl();
  }

  return "https://meetflow-backend-moit.onrender.com";
}

async function authHeaders() {
  const token = await window.electronAPI?.getAuthToken?.();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Registered once by App.jsx so an expired/invalid token anywhere
// (not just on the screen that happened to make the failing call)
// immediately clears the stored token and drops back to Login,
// instead of leaving the dashboard sitting there showing raw 401s.
let unauthorizedHandler = null;
export function onUnauthorized(handler) {
  unauthorizedHandler = handler;
}

async function get(path) {
  const url = `${await base()}${path}`;
  const res = await fetch(url, { headers: await authHeaders() });
  if (!res.ok) {
    if (res.status === 401) unauthorizedHandler?.();
    throw new Error(`GET ${path} -> ${res.status}`);
  }
  return res.json();
}

async function post(path, body) {
  const url = `${await base()}${path}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    if (res.status === 401) unauthorizedHandler?.();
    const err = await res.text();
    throw new Error(`POST ${path} -> ${res.status}: ${err}`);
  }
  return res.json();
}

async function patch(path, body) {
  const url = `${await base()}${path}`;
  const res = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    if (res.status === 401) unauthorizedHandler?.();
    const err = await res.text();
    throw new Error(`PATCH ${path} -> ${res.status}: ${err}`);
  }
  return res.json();
}

export const api = {
  login: (payload) => post("/api/auth/login", payload),
  register: (payload) => post("/api/auth/register", payload),

  health: () => get("/health"),

  listMeetings: () => get("/api/meetings"),
  upcomingMeetings: () => get("/api/meetings/upcoming"),
  recentMeetings: () => get("/api/meetings/recent"),
  getMeeting: (id) => get(`/api/meetings/${id}`),
  getTranscript: (id, q = "") =>
    get(
      `/api/meetings/${id}/transcript${q ? `?q=${encodeURIComponent(q)}` : ""}`,
    ),
  getMeetingStatus: (id) => get(`/api/meetings/${id}/status`),

  finalizeMeeting: (id) => post(`/api/meetings/${id}/finalize`, {}),

  getTask: (id) => get(`/api/tasks/${id}`),

  listApprovals: () => get("/api/approvals/queue"),
  decideApproval: (taskId, payload) =>
    post(`/api/approvals/${taskId}/decision`, payload),
  // NEW: manually (re)send the meeting summary to a chosen recipient list -
  // defaults to participant_emails on the backend if recipients is [].
  sendMeetingSummary: (meetingId, recipients) =>
    post(`/api/meetings/${meetingId}/send-summary`, { recipients }),
  // NEW: edit/delete the summary text, discussion points, decisions,
  // risks, and blockers - works before or after the summary mail has
  // already been sent (editing and sending are independent actions).
  updateMeetingSummary: (meetingId, payload) =>
    patch(`/api/meetings/${meetingId}/summary`, payload),
};
