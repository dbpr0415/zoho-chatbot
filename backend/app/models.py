"""
Pydantic models for API request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


# ─── Chat Models ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Incoming chat message from the user."""
    message: str = Field(..., min_length=1, max_length=2000, description="User's chat message")
    session_id: str = Field(..., description="Unique session identifier")
    confirm_action: Optional[bool] = Field(None, description="User's confirmation for pending action (True=approve, False=decline)")


class ConfirmationRequest(BaseModel):
    """Payload for confirming/executing a pending action with potentially edited parameters."""
    session_id: str
    approved: bool
    parameters: Optional[dict] = None


class PendingAction(BaseModel):
    """Details of a write action awaiting user confirmation."""
    action_type: str = Field(..., description="Type of action: create, update, delete")
    tool_name: str = Field(..., description="Tool to be executed")
    description: str = Field(..., description="Human-readable description of what will happen")
    parameters: dict = Field(default_factory=dict, description="Parameters for the action")


class ChatResponse(BaseModel):
    """Response sent back to the user."""
    message: str = Field(..., description="Bot's response message")
    agent_used: Optional[str] = Field(None, description="Which agent handled the request (query/action)")
    pending_action: Optional[PendingAction] = Field(None, description="Action awaiting confirmation, if any")
    session_id: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─── Auth Models ─────────────────────────────────────────────

class AuthStatus(BaseModel):
    """Current authentication status."""
    authenticated: bool
    user_email: Optional[str] = None
    portal_name: Optional[str] = None


class TokenData(BaseModel):
    """Stored OAuth token data."""
    access_token: str
    refresh_token: str
    expires_at: datetime
    user_id: str
    user_email: Optional[str] = None


# ─── Zoho Data Models ────────────────────────────────────────

class ZohoProject(BaseModel):
    """Zoho Project representation."""
    id: str
    name: str
    status: Optional[str] = None
    description: Optional[str] = None
    owner_name: Optional[str] = None
    task_count: Optional[dict] = None


class ZohoTask(BaseModel):
    """Zoho Task representation."""
    id: str
    name: str
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    description: Optional[str] = None
    created_time: Optional[str] = None


class ZohoMember(BaseModel):
    """Zoho Project member."""
    id: str
    name: str
    email: Optional[str] = None
    role: Optional[str] = None


class TaskUtilisation(BaseModel):
    """Task utilisation summary per member."""
    member_name: str
    total_tasks: int
    open_tasks: int
    completed_tasks: int
    overdue_tasks: int
