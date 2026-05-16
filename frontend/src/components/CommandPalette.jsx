import React, { useState, useRef, useEffect } from "react";

// All slash commands
const COMMANDS = [
  { cmd: "/projects",    label: "List all projects",                   fill: "What projects do I have?",               icon: "📁" },
  { cmd: "/tasks",       label: "Show tasks for a project",            fill: "Show tasks for interviews",              icon: "📝" },
  { cmd: "/details",     label: "Get task details",                    fill: "Get details of go out task",             icon: "🔍" },
  { cmd: "/create",      label: "Create a new task",                   fill: "Create a task called ",                  icon: "➕" },
  { cmd: "/update",      label: "Update a task",                       fill: "Update go out task to closed",           icon: "✏️" },
  { cmd: "/delete",      label: "Delete a task",                       fill: "Delete go out task from interviews",     icon: "🗑️" },
  { cmd: "/members",     label: "List project members",                fill: "List members of interviews project",     icon: "👥" },
  { cmd: "/utilisation", label: "Show task load per member",           fill: "Who has the most tasks?",               icon: "📊" },
  { cmd: "/memory",      label: "Recall what I was doing last time",   fill: "What was I talking about?",             icon: "🧠" },
  { cmd: "/overdue",     label: "Show overdue tasks",                  fill: "Show all overdue tasks across projects", icon: "⚠️" },
];

export default function CommandPalette({ input, onSelect, visible }) {
  if (!visible || !input.startsWith("/")) return null;

  const query   = input.slice(1).toLowerCase();
  const matches = COMMANDS.filter(
    (c) => c.cmd.slice(1).startsWith(query) || c.label.toLowerCase().includes(query)
  );

  if (matches.length === 0) return null;

  return (
    <div className="cmd-palette">
      <div className="cmd-palette-header">Commands</div>
      {matches.map((c) => (
        <button
          key={c.cmd}
          className="cmd-item"
          onMouseDown={(e) => { e.preventDefault(); onSelect(c.fill); }}
        >
          <span className="cmd-icon">{c.icon}</span>
          <div className="cmd-text">
            <span className="cmd-name">{c.cmd}</span>
            <span className="cmd-label">{c.label}</span>
          </div>
          <span className="cmd-arrow">↵</span>
        </button>
      ))}
      <div className="cmd-palette-tip">↑↓ navigate · Enter to select · Esc to dismiss</div>
    </div>
  );
}
