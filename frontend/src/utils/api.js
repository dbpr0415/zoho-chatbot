// In development: VITE_API_URL is empty → Vite proxy handles requests (same origin, no CORS)
// In production:  VITE_API_URL = Railway backend URL → direct cross-domain calls
const API_BASE = import.meta.env.VITE_API_URL || "";

export const LOGIN_URL  = `${API_BASE}/auth/login`;
export const LOGOUT_URL = `${API_BASE}/auth/logout`;

// Helper: on 401 → redirect to login automatically
function handleResponse(res) {
  if (res.status === 401) {
    window.location.href = LOGIN_URL;
    throw new Error("Session expired. Redirecting to login...");
  }
  return res;
}

export async function checkAuthStatus() {
  const res = await fetch(`${API_BASE}/auth/status`, { credentials: "include" });
  return res.json();
}

export async function listSessions() {
  const res = await fetch(`${API_BASE}/sessions`, { credentials: "include" });
  handleResponse(res);
  if (!res.ok) return { sessions: [] };
  return res.json();
}

export async function deleteSession(sessionId) {
  const res = await fetch(`${API_BASE}/session/${sessionId}`, {
    method: "DELETE",
    credentials: "include",
  });
  handleResponse(res);
  return res.ok;
}

export async function sendMessage(message, sessionId) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  handleResponse(res);

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail || "Chat request failed";
    if (detail.toLowerCase().includes("no stored tokens") ||
        detail.toLowerCase().includes("re-authenticate")) {
      window.location.href = LOGIN_URL;
      throw new Error("Session expired. Redirecting to login...");
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function confirmAction(sessionId, approved, parameters = null) {
  const body = { session_id: sessionId, approved, parameters };
  const res = await fetch(`${API_BASE}/chat/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });

  handleResponse(res);

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail || "Confirmation failed";
    if (detail.toLowerCase().includes("no stored tokens") ||
        detail.toLowerCase().includes("re-authenticate")) {
      window.location.href = LOGIN_URL;
      throw new Error("Session expired. Redirecting to login...");
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function createSession() {
  const res = await fetch(`${API_BASE}/session/new`, {
    method: "POST",
    credentials: "include",
  });
  handleResponse(res);
  return res.json();
}

export async function getSessionHistory(sessionId) {
  const res = await fetch(`${API_BASE}/session/${sessionId}/history`, {
    credentials: "include",
  });
  handleResponse(res);
  return res.json();
}
