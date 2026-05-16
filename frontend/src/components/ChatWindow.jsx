import React, { useState, useRef, useEffect } from "react";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";
import ConfirmationModal from "./ConfirmationModal";
import CommandPalette from "./CommandPalette";
import { ToastContainer } from "./Toast";

function timeAgo(isoStr) {
  if (!isoStr) return "";
  const diff = (Date.now() - new Date(isoStr + "Z").getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

const SUGGESTIONS = [
  { icon: "📋", text: "What projects do I have?" },
  { icon: "📝", text: "Show tasks for interviews" },
  { icon: "👥", text: "Who has the most tasks in interviews?" },
  { icon: "➕", text: "Create a task called API Integration in interviews" },
  { icon: "🧠", text: "What was I talking about?" },
  { icon: "📊", text: "Show task utilisation across all projects" },
];

export default function ChatWindow({
  messages, loading, routingStep, pendingAction,
  sessions, activeSession,
  onSend, onConfirm, onDecline, onNewSession, onLoadSession, onRemoveSession,
  userEmail, onLogout,
}) {
  const [input, setInput]            = useState("");
  const [search, setSearch]          = useState("");
  const [showPalette, setShowPalette] = useState(false);
  const [hoveredSession, setHovered] = useState(null);
  const inputRef                     = useRef(null);
  const bottomRef                    = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault(); inputRef.current?.focus();
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "n") {
        e.preventDefault(); onNewSession();
        setTimeout(() => inputRef.current?.focus(), 50);
      }
      if (e.key === "Escape") {
        setShowPalette(false);
        if (document.activeElement === inputRef.current) setInput("");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onNewSession]);

  const handleInputChange = (e) => {
    const val = e.target.value;
    setInput(val);
    setShowPalette(val.startsWith("/"));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    setShowPalette(false);
    onSend(input.trim());
    setInput("");
  };

  const handleCommandSelect = (fill) => {
    setInput(fill);
    setShowPalette(false);
    setTimeout(() => inputRef.current?.focus(), 10);
  };

  const hour      = new Date().getHours();
  const greeting  = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const greetEmoji = hour < 12 ? "🌅" : hour < 17 ? "☀️" : "🌙";
  const firstName = userEmail ? userEmail.split("@")[0].split(".")[0] : "there";

  const filteredSessions = search.trim()
    ? sessions.filter((s) => s.title?.toLowerCase().includes(search.toLowerCase()))
    : sessions;

  const grouped = { Today: [], Yesterday: [], "This Week": [], Older: [] };
  filteredSessions.forEach((s) => {
    const diffDays = Math.floor((Date.now() - new Date(s.last_active + "Z")) / 86400000);
    if (diffDays === 0)      grouped["Today"].push(s);
    else if (diffDays === 1) grouped["Yesterday"].push(s);
    else if (diffDays < 7)  grouped["This Week"].push(s);
    else                     grouped["Older"].push(s);
  });

  return (
    <div className="chat-layout">
      <ToastContainer />

      {/* ── Sidebar ─────────────────────────────────────── */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <span className="sidebar-logo">⚡</span>
          <h2>ZohoBot</h2>
        </div>

        <button className="new-chat-btn" onClick={onNewSession} id="new-session-btn">
          + New Conversation <kbd className="kbd-hint">⌘N</kbd>
        </button>

        {sessions.length > 2 && (
          <div className="sidebar-search-wrap">
            <input
              className="sidebar-search"
              placeholder="🔍 Search conversations…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        )}

        <div className="sidebar-history">
          {filteredSessions.length === 0 && (
            <p className="history-empty">
              {search ? "No matches found." : "No conversations yet.\nStart chatting!"}
            </p>
          )}
          {Object.entries(grouped).map(([group, items]) =>
            items.length > 0 ? (
              <div key={group} className="history-group">
                <span className="history-group-label">{group}</span>
                {items.map((s) => (
                  <div
                    key={s.session_id}
                    className={`history-item ${s.session_id === activeSession ? "history-item-active" : ""}`}
                    onClick={() => onLoadSession(s.session_id)}
                    onMouseEnter={() => setHovered(s.session_id)}
                    onMouseLeave={() => setHovered(null)}
                  >
                    <span className="history-icon">💬</span>
                    <div className="history-meta">
                      <span className="history-title">{s.title}</span>
                      <span className="history-time">{timeAgo(s.last_active)}</span>
                    </div>
                    {hoveredSession === s.session_id && (
                      <button
                        className="history-delete-btn"
                        title="Delete conversation"
                        onClick={(e) => { e.stopPropagation(); onRemoveSession(s.session_id); }}
                      >🗑</button>
                    )}
                  </div>
                ))}
              </div>
            ) : null
          )}
        </div>

        <div className="sidebar-user">
          <div className="user-info">
            <span className="user-dot" />
            <span>{userEmail || "User"}</span>
          </div>
          <button className="logout-btn" onClick={onLogout} id="logout-btn">Sign out</button>
        </div>
      </aside>

      {/* ── Main Chat ───────────────────────────────────── */}
      <main className="chat-main">
        <header className="chat-header">
          <h1>Zoho Project Assistant</h1>
          <div className="header-actions">
            <span className="kbd-tip" title="⌘K: focus · ⌘N: new chat · /: commands · Esc: clear">
              ⌨️ shortcuts
            </span>
            <span className="status-badge">● Online</span>
          </div>
        </header>

        <div className="chat-messages" id="chat-messages">
          {messages.length === 0 && (
            <div className="welcome-section">
              <div className="welcome-icon">{greetEmoji}</div>
              <h2>{greeting}, {firstName}!</h2>
              <p>I'm your Zoho Projects AI assistant. Ask me anything, or type <kbd>/</kbd> for commands.</p>
              <div className="keyboard-hint">
                <span>⌨️</span>
                <kbd>⌘K</kbd> focus &nbsp;|&nbsp;
                <kbd>⌘N</kbd> new chat &nbsp;|&nbsp;
                <kbd>/</kbd> commands &nbsp;|&nbsp;
                <kbd>Esc</kbd> clear
              </div>
              <div className="suggestions">
                {SUGGESTIONS.map((s, i) => (
                  <button key={i} className="suggestion-chip" onClick={() => onSend(s.text)}>
                    <span className="chip-icon">{s.icon}</span>
                    {s.text}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} />
          ))}

          {loading && <TypingIndicator step={routingStep} />}
          <div ref={bottomRef} />
        </div>

        <ConfirmationModal action={pendingAction} onConfirm={onConfirm} onDecline={onDecline} />

        {/* Input + Command Palette */}
        <div className="input-wrapper">
          <CommandPalette
            input={input}
            visible={showPalette}
            onSelect={handleCommandSelect}
          />
          <form className="chat-input-bar" onSubmit={handleSubmit}>
            <input
              id="chat-input"
              ref={inputRef}
              type="text"
              placeholder="Ask anything… or type / for commands  (⌘K)"
              value={input}
              onChange={handleInputChange}
              disabled={loading}
              autoFocus
            />
            <button type="submit" className="send-btn" disabled={loading || !input.trim()} id="send-btn">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
