"""
FastAPI main application — entry point for the Zoho Project Assistant.
Exposes chat, auth, and health endpoints.
"""

import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse

from app.config import settings
from app.models import ChatRequest, ChatResponse, AuthStatus, ConfirmationRequest
from app.database import db
from app.auth.oauth import zoho_oauth
from app.auth.middleware import AuthMiddleware
from app.agents.graph import initialize_graph, get_graph


# ─── App Lifespan ────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    await db.connect()
    initialize_graph()
    print("🚀 Zoho Project Assistant started!")
    print(f"📡 Frontend URL: {settings.app.frontend_url}")

    yield

    # Shutdown
    await db.close()
    print("👋 Zoho Project Assistant stopped.")


# ─── FastAPI App ─────────────────────────────────────────────

app = FastAPI(
    title="Zoho Project Assistant",
    description="AI-Powered Chatbot for Zoho Projects",
    version="1.0.0",
    lifespan=lifespan,
)

# Detect production environment (Railway sets RAILWAY_ENVIRONMENT)
IS_PRODUCTION = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("IS_PRODUCTION"))
COOKIE_SAMESITE  = "none" if IS_PRODUCTION else "lax"
COOKIE_SECURE    = IS_PRODUCTION

# CORS — allow frontend origin
allowed_origins = [settings.app.frontend_url, "http://localhost:5173", "http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware
app.add_middleware(AuthMiddleware)


# ─── Health Check ────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "zoho-project-assistant"}


# ─── Auth Endpoints ──────────────────────────────────────────

@app.get("/auth/login")
async def auth_login():
    """
    Initiates the Zoho OAuth flow.
    Redirects the user to Zoho's authorization page.
    """
    state = str(uuid.uuid4())
    auth_url = zoho_oauth.get_authorization_url(state=state)
    return RedirectResponse(url=auth_url)


@app.get("/auth/callback")
async def auth_callback(code: str = None, error: str = None):
    """
    OAuth callback — Zoho redirects here after user grants permission.
    Exchanges the authorization code for tokens and creates a session.
    """
    if error:
        return RedirectResponse(
            url=f"{settings.app.frontend_url}?error={error}"
        )

    if not code:
        raise HTTPException(status_code=400, detail="Authorization code missing")

    try:
        auth_result = await zoho_oauth.authenticate_user(code)

        # Redirect to frontend with user info
        response = RedirectResponse(
            url=f"{settings.app.frontend_url}?authenticated=true"
        )

        # Set session cookies
        # In production: SameSite=None + Secure for cross-domain (Vercel → Railway)
        response.set_cookie(
            key="user_id",
            value=auth_result["user_id"],
            httponly=True,
            samesite=COOKIE_SAMESITE,
            secure=COOKIE_SECURE,
            max_age=86400 * 7,
            path="/",
        )
        response.set_cookie(
            key="user_email",
            value=auth_result.get("user_email", ""),
            httponly=False,
            samesite=COOKIE_SAMESITE,
            secure=COOKIE_SECURE,
            max_age=86400 * 7,
            path="/",
        )

        return response

    except Exception as e:
        return RedirectResponse(
            url=f"{settings.app.frontend_url}?error={str(e)}"
        )


@app.get("/auth/status")
async def auth_status(request: Request):
    """Check if the current user is authenticated."""
    user_id = request.cookies.get("user_id")

    if not user_id:
        return AuthStatus(authenticated=False)

    token_data = await db.get_token(user_id)
    if not token_data:
        return AuthStatus(authenticated=False)

    return AuthStatus(
        authenticated=True,
        user_email=token_data.get("user_email"),
        portal_name=settings.zoho.portal_name,
    )


@app.get("/auth/logout")
async def auth_logout():
    """Log out the current user by clearing cookies."""
    response = RedirectResponse(url=settings.app.frontend_url)
    response.delete_cookie(
        "user_id", 
        path="/", 
        samesite=COOKIE_SAMESITE, 
        secure=COOKIE_SECURE, 
        httponly=True
    )
    response.delete_cookie(
        "user_email", 
        path="/", 
        samesite=COOKIE_SAMESITE, 
        secure=COOKIE_SECURE
    )
    return response


@app.get("/debug/token")
async def debug_token(request: Request):
    """Debug endpoint to verify token validity against Zoho."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        return {"error": "No user_id cookie"}
        
    token_data = await db.get_token(user_id)
    if not token_data:
        return {"error": "No token in DB"}
        
    access_token = token_data["access_token"]
    
    import httpx
    async with httpx.AsyncClient() as client:
        # Test 1: Accounts API
        r1 = await client.get(
            "https://accounts.zoho.in/oauth/user/info",
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
        )
        
        # Test 2: Projects API
        r2 = await client.get(
            f"{settings.zoho.api_base_url}/portals/",
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
        )
        
        return {
            "token_preview": access_token[:10] + "..." + access_token[-5:],
            "accounts_status": r1.status_code,
            "accounts_resp": r1.text,
            "projects_status": r2.status_code,
            "projects_resp": r2.text,
            "portal_name": settings.zoho.portal_name
        }


# ─── Chat Endpoint ───────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, chat_request: ChatRequest):
    """
    Main chat endpoint.
    Processes user messages through the LangGraph pipeline.
    """
    user_id = request.state.user_id

    try:
        graph = get_graph()
        result = await graph.process_message(
            user_id=user_id,
            session_id=chat_request.session_id,
            message=chat_request.message,
        )

        pending = None
        if result.get("pending_action"):
            from app.models import PendingAction
            pending = PendingAction(**result["pending_action"])

        return ChatResponse(
            message=result["message"],
            agent_used=result.get("agent_used"),
            pending_action=pending,
            session_id=chat_request.session_id,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Chat processing error: {str(e)}")


@app.post("/chat/confirm", response_model=ChatResponse)
async def chat_confirm(request: Request, conf_request: ConfirmationRequest):
    """
    Handles confirmation of a pending action, potentially with edited parameters.
    """
    user_id = request.state.user_id

    try:
        pending = await db.get_pending_action(conf_request.session_id)
        if not pending:
            raise HTTPException(status_code=404, detail="No pending action found for this session.")

        if not conf_request.approved:
            await db.resolve_pending_action(pending["id"], "declined")
            return ChatResponse(
                message="❌ Action cancelled. No changes were made.",
                agent_used="action",
                session_id=conf_request.session_id,
            )

        # Update parameters if provided
        if conf_request.parameters:
            await db.update_pending_parameters(pending["id"], conf_request.parameters)

        # Trigger the action agent via LangGraph with a confirmation message
        graph = get_graph()
        result = await graph.process_message(
            user_id=user_id,
            session_id=conf_request.session_id,
            message="yes",  # Internal trigger to execute the pending action
        )

        return ChatResponse(
            message=result["message"],
            agent_used=result.get("agent_used"),
            session_id=conf_request.session_id,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Confirmation error: {str(e)}")


# ─── Session Management ─────────────────────────────────────

@app.post("/session/new")
async def create_new_session(request: Request):
    """Create a new chat session for the authenticated user."""
    user_id = request.state.user_id
    session_id = str(uuid.uuid4())
    await db.create_session(session_id, user_id)
    return {"session_id": session_id}


@app.get("/session/{session_id}/history")
async def get_session_history(session_id: str, request: Request):
    """Get chat history for a session."""
    messages = await db.get_session_messages(session_id, limit=50)
    return {"messages": messages}


@app.get("/sessions")
async def list_sessions(request: Request):
    """List all sessions for the authenticated user, newest first, with a title preview."""
    user_id = request.state.user_id
    rows = await db.list_user_sessions(user_id)
    return {"sessions": rows}


@app.delete("/session/{session_id}")
async def delete_session(session_id: str, request: Request):
    """Delete a session and its messages."""
    user_id = request.state.user_id
    await db.delete_session(session_id, user_id)
    return {"ok": True}
