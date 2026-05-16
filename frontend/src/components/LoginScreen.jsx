import React from "react";
import { LOGIN_URL } from "../utils/api";

export default function LoginScreen() {
  return (
    <div className="login-screen">
      <div className="login-bg-orbs">
        <div className="orb orb-1" />
        <div className="orb orb-2" />
        <div className="orb orb-3" />
      </div>
      <div className="login-card">
        <div className="login-logo">
          <span className="logo-icon">👋</span>
        </div>
        <h1 className="login-title">Hey there!</h1>
        <p className="login-subtitle">
          I'm your Zoho Projects assistant. Sign in and let's get your tasks sorted — just tell me what you need in plain English.
        </p>
        <a href={LOGIN_URL} className="login-btn" id="login-button">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4M10 17l5-5-5-5M15 12H3" />
          </svg>
          Sign in with Zoho
        </a>
        <div className="login-features">
          <div className="feature"><span>💬</span> Ask in plain English</div>
          <div className="feature"><span>✅</span> Create & manage tasks</div>
          <div className="feature"><span>🧠</span> I remember your preferences</div>
          <div className="feature"><span>🔒</span> Your data stays private</div>
        </div>
      </div>
    </div>
  );
}
