"""
Zoho OAuth 2.0 Authentication module.
Implements Authorization Code Grant flow.
"""

import httpx
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

from app.config import settings
from app.database import db


class ZohoOAuth:
    """Handles Zoho OAuth 2.0 Authorization Code Grant flow."""

    def __init__(self):
        self.client_id = settings.zoho.client_id
        self.client_secret = settings.zoho.client_secret
        self.redirect_uri = settings.zoho.redirect_uri
        self.auth_url = settings.zoho.auth_url
        self.token_url = settings.zoho.token_url

    def get_authorization_url(self, state: str = None) -> str:
        """
        Generate the Zoho OAuth authorization URL.
        The user will be redirected here to grant access.
        """
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "scope": settings.zoho.scopes,
            "redirect_uri": self.redirect_uri,
            "access_type": "offline",  # Required for refresh tokens
            "prompt": "consent",
        }
        if state:
            params["state"] = state

        return f"{self.auth_url}?{urlencode(params)}"

    async def exchange_code_for_tokens(self, authorization_code: str) -> dict:
        """
        Exchange the authorization code for access and refresh tokens.
        Called after user grants permission and is redirected back.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "code": authorization_code,
                }
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                raise ValueError(f"OAuth error: {data['error']}")

            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", ""),
                "expires_in": data.get("expires_in", 3600),
                "token_type": data.get("token_type", "Zoho-oauthtoken"),
            }

    async def get_current_user(self, access_token: str) -> dict:
        """
        Fetch the current authenticated user's profile.
        Tries the accounts API first, falls back to portal users API.
        """
        # Try accounts API (needs AaaServer.profile.READ scope)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://accounts.zoho.in/oauth/user/info",
                    headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
                )
                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass

        # Fallback: get user info from Zoho Projects portal API
        try:
            async with httpx.AsyncClient() as client:
                portal_url = f"{settings.zoho.api_base_url}/portals/"
                response = await client.get(
                    portal_url,
                    headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    portals = data.get("portals", [])
                    if portals:
                        portal = portals[0]
                        return {
                            "ZUID": str(portal.get("id_string", portal.get("id", ""))),
                            "Email": portal.get("login_id", ""),
                            "Display_Name": portal.get("name", ""),
                        }
        except Exception:
            pass

        # Last fallback: generate ID from token
        import hashlib
        user_hash = hashlib.sha256(access_token.encode()).hexdigest()[:16]
        return {"ZUID": f"user_{user_hash}", "Email": "", "Display_Name": "User"}

    async def authenticate_user(self, authorization_code: str) -> dict:
        """
        Complete authentication flow:
        1. Exchange code for tokens
        2. Get user info
        3. Store tokens in database
        """
        # Step 1: Get tokens
        tokens = await self.exchange_code_for_tokens(authorization_code)

        # Step 2: Get user info (with fallbacks)
        user_info = await self.get_current_user(tokens["access_token"])
        user_id = str(user_info.get("ZUID", "unknown"))
        user_email = user_info.get("Email", user_info.get("Display_Name", ""))

        # Step 3: Calculate expiry and store
        expires_at = datetime.utcnow() + timedelta(seconds=tokens["expires_in"])

        await db.store_token(
            user_id=user_id,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_at=expires_at.isoformat(),
            user_email=user_email,
        )

        return {
            "user_id": user_id,
            "user_email": user_email,
            "access_token": tokens["access_token"],
        }


# Global OAuth handler instance
zoho_oauth = ZohoOAuth()
