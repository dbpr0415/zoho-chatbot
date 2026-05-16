import React from "react";

const STEPS = {
  routing: { icon: "🔀", label: "Supervisor routing your request...", color: "#a855f7" },
  query:   { icon: "📖", label: "Query Agent is fetching data...",     color: "#3b82f6" },
  action:  { icon: "✏️", label: "Action Agent is processing...",       color: "#f59e0b" },
  tools:   { icon: "⚙️", label: "Running tools...",                    color: "#10b981" },
};

export default function TypingIndicator({ step = "routing" }) {
  const { icon, label, color } = STEPS[step] || STEPS.routing;

  return (
    <div className="msg-row msg-bot">
      <div className="msg-avatar">🤖</div>
      <div className="msg-bubble bubble-bot typing-bubble-wrap">
        {/* Routing pipeline visualization */}
        <div className="routing-pipeline">
          <div className="pipeline-node pipeline-supervisor active">
            <span className="pnode-icon">🧠</span>
            <span className="pnode-label">Supervisor</span>
          </div>
          <div className={`pipeline-arrow ${step !== "routing" ? "arrow-active" : ""}`}>
            <div className="arrow-line" />
            <div className="arrow-head">▶</div>
          </div>
          <div className={`pipeline-node ${step === "query" || step === "tools" ? "pipeline-query active" : "pipeline-query"}`}>
            <span className="pnode-icon">📖</span>
            <span className="pnode-label">Query Agent</span>
          </div>
          <div className="pipeline-or">|</div>
          <div className={`pipeline-node ${step === "action" ? "pipeline-action active" : "pipeline-action"}`}>
            <span className="pnode-icon">✏️</span>
            <span className="pnode-label">Action Agent</span>
          </div>
        </div>

        {/* Current step label */}
        <div className="routing-status-row" style={{ color }}>
          <span className="step-icon-spin">{icon}</span>
          <span className="step-label">{label}</span>
        </div>

        {/* Typing dots */}
        <div className="typing-dots">
          <span /><span /><span />
        </div>
      </div>
    </div>
  );
}
