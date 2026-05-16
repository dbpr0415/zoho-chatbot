import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import { toast } from "./Toast";

const AGENT_CONFIG = {
  query:  { icon: "📖", label: "Query Agent",  cls: "badge-query"  },
  action: { icon: "✏️", label: "Action Agent", cls: "badge-action" },
};

function hasOverdue(text) {
  return /overdue|past due|missed|late/i.test(text);
}
function hasHighPriority(text) {
  return /\bhigh\b.*priority|priority.*\bhigh\b/i.test(text);
}

function formatTs(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function MessageBubble({ msg }) {
  const [copied, setCopied]     = useState(false);
  const [showTime, setShowTime] = useState(false);
  const isUser   = msg.role === "user";
  const agentCfg = msg.agent ? AGENT_CONFIG[msg.agent] : null;

  const handleCopy = () => {
    const plain = msg.content
      .replace(/\*\*/g, "").replace(/\*/g, "")
      .replace(/#{1,6}\s/g, "").replace(/`/g, "").trim();
    navigator.clipboard.writeText(plain).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast("Copied to clipboard!", "success");
    });
  };

  const showOverdue  = !isUser && hasOverdue(msg.content);
  const showHighPrio = !isUser && hasHighPriority(msg.content);

  return (
    <div
      className={`msg-row ${isUser ? "msg-user" : "msg-bot"} msg-animate`}
      onMouseEnter={() => setShowTime(true)}
      onMouseLeave={() => setShowTime(false)}
    >
      {!isUser && <div className="msg-avatar">🤖</div>}

      <div className={`msg-bubble ${isUser ? "bubble-user" : "bubble-bot"}`}>
        {/* Banners */}
        {showOverdue  && <div className="msg-banner banner-overdue">⚠️ Contains overdue tasks</div>}
        {showHighPrio && <div className="msg-banner banner-priority">🔴 High priority items</div>}

        {/* Content */}
        {isUser ? (
          <p>{msg.content}</p>
        ) : (
          <ReactMarkdown>{msg.content}</ReactMarkdown>
        )}

        {/* Footer */}
        <div className="msg-footer">
          {agentCfg && (
            <div className="routing-trace">
              <span className="rt-node rt-supervisor"><span>🧠</span> Supervisor</span>
              <span className="rt-arrow">→</span>
              <span className={`rt-node rt-agent ${agentCfg.cls}`}>
                <span>{agentCfg.icon}</span> {agentCfg.label}
              </span>
            </div>
          )}
          {!agentCfg && <span />}
          {!isUser && (
            <button
              className={`copy-btn ${copied ? "copy-btn-done" : ""}`}
              onClick={handleCopy}
              title="Copy message"
            >
              {copied ? "✓ Copied" : "⎘ Copy"}
            </button>
          )}
        </div>
      </div>

      {/* Hover timestamp */}
      {showTime && msg.ts && (
        <span className={`msg-timestamp ${isUser ? "ts-user" : "ts-bot"}`}>
          {formatTs(msg.ts)}
        </span>
      )}

      {isUser && <div className="msg-avatar user-avatar">👤</div>}
    </div>
  );
}
