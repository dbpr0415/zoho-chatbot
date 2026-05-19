"""
Authentication middleware for FastAPI.
Extracts and validates user identity from session cookies.

NOTE: BaseHTTPMiddleware swallows HTTPException and converts it to 500.
We return JSONResponse directly to ensure proper 401 status codes.
"""

from app.database import db
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that attaches user_id to the request state.
    Returns proper 401 JSON responses for unauthenticated requests.
    """

    PUBLIC_ROUTES = {
        "/auth/login",
        "/auth/callback",
        "/auth/status",
        "/auth/logout",
        "/",
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/favicon.ico",
    }

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Always allow CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip auth for public routes and static files
        if path in self.PUBLIC_ROUTES or path.startswith("/static"):
            return await call_next(request)

        # Extract user_id from session cookie
        user_id = request.cookies.get("user_id")
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated. Please login via /auth/login"},
            )

        # Verify token exists in database
        token_data = await db.get_token(user_id)
        if not token_data:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Session expired. Please login again via /auth/login"
                },
            )

        # Attach user info to request state
        request.state.user_id = user_id
        request.state.user_email = token_data.get("user_email", "")

        return await call_next(request)
