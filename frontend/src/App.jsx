import React, { useState, useEffect } from "react";
import LoginScreen from "./components/LoginScreen";
import ChatWindow from "./components/ChatWindow";
import { useChat } from "./hooks/useChat";
import { checkAuthStatus, LOGOUT_URL } from "./utils/api";
import "./index.css";

export default function App() {
  const [auth, setAuth] = useState({ checked: false, authenticated: false, email: "" });
  const {
    messages, loading, routingStep, pendingAction,
    sessions, activeSession,
    send, confirm, decline, newSession, loadSession, removeSession,
  } = useChat();

  useEffect(() => {
    checkAuthStatus()
      .then((data) => setAuth({ checked: true, authenticated: data.authenticated, email: data.user_email || "" }))
      .catch(() => setAuth({ checked: true, authenticated: false, email: "" }));
  }, []);

  if (!auth.checked) {
    return (
      <div className="loading-screen">
        <div className="spinner" />
        <p>Connecting...</p>
      </div>
    );
  }

  if (!auth.authenticated) {
    return <LoginScreen />;
  }

  return (
    <ChatWindow
      messages={messages}
      loading={loading}
      routingStep={routingStep}
      pendingAction={pendingAction}
      sessions={sessions}
      activeSession={activeSession}
      onSend={send}
      onConfirm={confirm}
      onDecline={decline}
      onNewSession={newSession}
      onLoadSession={loadSession}
      onRemoveSession={removeSession}
      userEmail={auth.email}
      onLogout={() => (window.location.href = LOGOUT_URL)}
    />
  );
}
