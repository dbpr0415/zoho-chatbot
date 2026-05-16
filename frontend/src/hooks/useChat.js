import { useState, useCallback, useEffect } from "react";
import { sendMessage, confirmAction as confirmApi, listSessions, deleteSession, getSessionHistory } from "../utils/api";
import { v4 as uuidv4 } from "uuid";

function guessAgent(text) {
  return /\b(create|make|add|update|change|modify|delete|remove|assign|close|open|edit)\b/i.test(text)
    ? "action"
    : "query";
}

function makeSessionId() {
  return uuidv4();
}

export function useChat() {
  const [messages, setMessages]         = useState([]);
  const [loading, setLoading]           = useState(false);
  const [routingStep, setRoutingStep]   = useState("routing");
  const [sessionId, setSessionId]       = useState(() => makeSessionId());
  const [pendingAction, setPendingAction] = useState(null);
  const [sessions, setSessions]         = useState([]);          // sidebar list
  const [activeSession, setActiveSession] = useState(null);      // highlighted session

  // ─── Load sidebar list ───────────────────────────────────
  const refreshSessions = useCallback(async () => {
    try {
      const data = await listSessions();
      setSessions(data.sessions || []);
    } catch { /* silently fail */ }
  }, []);

  useEffect(() => {
    refreshSessions();
  }, []);

  // ─── Send message ────────────────────────────────────────
  const send = useCallback(async (text) => {
    if (!text.trim()) return;
    const userMsg = { id: uuidv4(), role: "user", content: text, ts: Date.now() };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setRoutingStep("routing");

    const guessed = guessAgent(text);
    const t1 = setTimeout(() => setRoutingStep(guessed), 700);
    const t2 = setTimeout(() => setRoutingStep("tools"), 1400);

    try {
      const data = await sendMessage(text, sessionId);
      clearTimeout(t1); clearTimeout(t2);
      const botMsg = {
        id: uuidv4(), role: "assistant",
        content: data.message, agent: data.agent_used, ts: Date.now(),
      };
      setMessages((prev) => [...prev, botMsg]);
      setPendingAction(data.pending_action || null);
      // Refresh sidebar after every send so new session appears
      setTimeout(refreshSessions, 500);
    } catch (err) {
      clearTimeout(t1); clearTimeout(t2);
      setMessages((prev) => [...prev,
        { id: uuidv4(), role: "assistant", content: `⚠️ Error: ${err.message}`, ts: Date.now() }]);
    } finally {
      setLoading(false);
      setRoutingStep("routing");
    }
  }, [sessionId, refreshSessions]);

  // ─── Confirm HIL action ─────────────────────────────────
  const confirm = useCallback(async (editedParams = null) => {
    setLoading(true);
    setRoutingStep("action");
    setPendingAction(null);
    try {
      const data = await confirmApi(sessionId, true, editedParams);
      setMessages((prev) => [...prev,
        { id: uuidv4(), role: "assistant", content: data.message, agent: data.agent_used || "action", ts: Date.now() }]);
    } catch (err) {
      setMessages((prev) => [...prev,
        { id: uuidv4(), role: "assistant", content: `⚠️ Error: ${err.message}`, ts: Date.now() }]);
    } finally {
      setLoading(false);
      setRoutingStep("routing");
      setTimeout(refreshSessions, 500);
    }
  }, [sessionId, refreshSessions]);

  const decline = useCallback(async () => {
    setLoading(true);
    setPendingAction(null);
    try {
      const data = await confirmApi(sessionId, false);
      setMessages((prev) => [...prev,
        { id: uuidv4(), role: "assistant", content: data.message, agent: data.agent_used || "action", ts: Date.now() }]);
    } catch (err) {
      setMessages((prev) => [...prev,
        { id: uuidv4(), role: "assistant", content: `⚠️ Error: ${err.message}`, ts: Date.now() }]);
    } finally {
      setLoading(false);
      setRoutingStep("routing");
    }
  }, [sessionId]);

  // ─── New conversation ────────────────────────────────────
  const newSession = useCallback(() => {
    const id = makeSessionId();
    setSessionId(id);
    setMessages([]);
    setPendingAction(null);
    setActiveSession(null);
  }, []);

  // ─── Load a previous session ─────────────────────────────
  const loadSession = useCallback(async (sid) => {
    try {
      const data = await getSessionHistory(sid);
      const msgs = (data.messages || []).map((m) => ({
        id: uuidv4(),
        role: m.role,
        content: m.content,
        agent: m.metadata?.agent || null,
        ts: Date.now(),
      }));
      setMessages(msgs);
      setSessionId(sid);
      setActiveSession(sid);
      setPendingAction(null);
    } catch (err) {
      console.error("Failed to load session:", err);
    }
  }, []);

  // ─── Delete a session from history ──────────────────────
  const removeSession = useCallback(async (sid) => {
    await deleteSession(sid);
    setSessions((prev) => prev.filter((s) => s.session_id !== sid));
    // If deleting the active session, clear chat
    if (sid === sessionId) {
      newSession();
    }
  }, [sessionId, newSession]);

  return {
    messages, loading, routingStep, pendingAction,
    sessions, activeSession,
    send, confirm, decline, newSession, loadSession, removeSession, refreshSessions,
  };
}
