"""
Zoho Projects API client.
Handles all REST API interactions with Zoho Projects.
"""

import httpx
from datetime import datetime, timedelta
from typing import Optional
from app.config import settings
from app.database import db


class ZohoClient:
    """
    Async client for Zoho Projects REST API.
    Handles authentication, token refresh, and all API operations.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.base_url = settings.zoho.api_base_url
        self.portal_name = settings.zoho.portal_name
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._portal_resolved: bool = False

    async def _ensure_valid_token(self):
        """Ensure we have a valid access token, refreshing if necessary."""
        if self._access_token and self._token_expires_at and datetime.utcnow() < self._token_expires_at:
            return

        token_data = await db.get_token(self.user_id)
        if not token_data:
            raise ValueError("No stored tokens found. User must re-authenticate.")

        expires_at = datetime.fromisoformat(token_data["expires_at"])

        # Refresh if token expires within 5 minutes
        if datetime.utcnow() >= expires_at - timedelta(minutes=5):
            await self._refresh_token(token_data["refresh_token"])
        else:
            self._access_token = token_data["access_token"]
            self._token_expires_at = expires_at

    async def _refresh_token(self, refresh_token: str):
        """Refresh the access token using the refresh token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.zoho.token_url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.zoho.client_id,
                    "client_secret": settings.zoho.client_secret,
                    "refresh_token": refresh_token,
                }
            )
            response.raise_for_status()
            data = response.json()

            self._access_token = data["access_token"]
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600))

            await db.update_access_token(
                self.user_id,
                self._access_token,
                self._token_expires_at.isoformat()
            )

    async def _resolve_portal(self):
        """Auto-detect the correct portal name from Zoho's /portals/ API."""
        if self._portal_resolved:
            return
        try:
            url = f"{self.base_url}/portals/"
            headers = {"Authorization": f"Zoho-oauthtoken {self._access_token}"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers)
                print(f"DEBUG: Portals URL: {url} -> {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    portals = data.get("portals", [])
                    if portals:
                        self.portal_name = portals[0].get("name", self.portal_name)
                        print(f"DEBUG: Auto-resolved portal name: {self.portal_name}")
                else:
                    print(f"DEBUG: Portal fetch failed: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"DEBUG: Portal auto-detect error: {e}")
        self._portal_resolved = True

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an authenticated request to Zoho Projects API."""
        await self._ensure_valid_token()
        await self._resolve_portal()

        url = f"{self.base_url}/portal/{self.portal_name}/{endpoint}"
        headers = {
            "Authorization": f"Zoho-oauthtoken {self._access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        async with httpx.AsyncClient() as client:
            print(f"DEBUG: Zoho Request: {method} {url}")
            response = await client.request(method, url, headers=headers, **kwargs)
            print(f"DEBUG: Zoho Response Status: {response.status_code}")

            # Handle 204 No Content (Zoho returns this when no data)
            if response.status_code == 204 or not response.text.strip():
                return {}

            if response.status_code >= 400:
                print(f"DEBUG: Zoho Error Body: {response.text}")

            response.raise_for_status()

            try:
                return response.json()
            except Exception:
                return {}

    # ─── Project Operations ──────────────────────────────────

    async def list_projects(self) -> list[dict]:
        """Fetch all projects for the authenticated user."""
        import httpx
        try:
            data = await self._request("GET", "projects/")
            return data.get("projects", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 404):
                print(f"DEBUG: Gracefully catching {e.response.status_code} on list_projects. Assuming empty.")
                return []
            raise

    # ─── Task Operations ─────────────────────────────────────

    async def list_tasks(self, project_id: str, status: str = None,
                         assignee: str = None, due_date: str = None) -> list[dict]:
        """List tasks for a project — returns all tasks (no server-side filters needed)."""
        data = await self._request("GET", f"projects/{project_id}/tasks/")
        print(f"DEBUG: Tasks response keys: {list(data.keys()) if data else 'empty'}")
        print(f"DEBUG: Tasks raw (first 500): {str(data)[:500]}")
        return data.get("tasks", [])

    async def get_task_details(self, project_id: str, task_id: str) -> dict:
        """Fetch full details of a single task."""
        data = await self._request("GET", f"projects/{project_id}/tasks/{task_id}/")
        return data.get("tasks", [{}])[0] if data.get("tasks") else {}

    async def create_task(self, project_id: str, name: str, description: str = None,
                          assignee: str = None, due_date: str = None,
                          priority: str = None) -> dict:
        """Create a new task in a project."""
        # Valid Zoho priority values
        PRIORITY_MAP = {
            "none": "None", "low": "Low", "medium": "Medium", "normal": "Medium",
            "high": "High", "urgent": "High", "critical": "High",
        }

        form_data = {"name": name}
        if description:
            form_data["description"] = description
        # Zoho requires a numeric user ID for person_responsible — skip if a name was given
        if assignee and str(assignee).strip().isdigit():
            form_data["person_responsible"] = assignee
        if due_date:
            # Normalize to MM-DD-YYYY (Zoho's required format)
            form_data["end_date"] = self._normalize_date(due_date)
        if priority:
            zoho_priority = PRIORITY_MAP.get(priority.lower(), "")
            if zoho_priority and zoho_priority != "None":
                form_data["priority"] = zoho_priority

        print(f"DEBUG: create_task form_data: {form_data}")
        data = await self._request("POST", f"projects/{project_id}/tasks/", data=form_data)
        return data.get("tasks", [{}])[0] if data.get("tasks") else {}

    @staticmethod
    def _normalize_date(date_str: str) -> Optional[str]:
        """Normalize various date formats to MM-DD-YYYY (Zoho format).
        Returns None if the string is not a recognizable date."""
        import re
        if not date_str:
            return None
        s = date_str.strip()
        # Skip obvious non-dates
        if s.lower() in ("none", "null", "n/a", "no due date", "no date", "unset", "", "-", "tbd"):
            return None
        # Already MM-DD-YYYY
        if re.match(r'^\d{2}-\d{2}-\d{4}$', s):
            return s
        # YYYY-MM-DD → MM-DD-YYYY
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', s)
        if m:
            return f"{m.group(2)}-{m.group(3)}-{m.group(1)}"
        # MM/DD/YYYY → MM-DD-YYYY
        m = re.match(r'^(\d{2})/(\d{2})/(\d{4})$', s)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        # D Mon YYYY e.g. "15 May 2025"
        try:
            from datetime import datetime
            dt = datetime.strptime(s, "%d %b %Y")
            return dt.strftime("%m-%d-%Y")
        except ValueError:
            pass
        return None  # Unrecognizable — don't send garbage to Zoho

    async def update_task(self, project_id: str, task_id: str,
                          name: str = None, status: str = None,
                          assignee: str = None, due_date: str = None,
                          priority: str = None) -> dict:
        """Update an existing task."""
        STATUS_MAP = {
            "open": "Open", "closed": "Closed", "close": "Closed",
            "done": "Closed", "complete": "Closed", "completed": "Closed",
            "in progress": "In Progress", "inprogress": "In Progress",
        }
        PRIORITY_MAP = {
            "none": None, "low": "Low", "medium": "Medium",
            "normal": "Medium", "high": "High", "urgent": "High",
        }

        form_data = {}
        if name and name.lower() not in ("none", "null", "n/a", ""):
            form_data["name"] = name
        if status:
            form_data["status"] = STATUS_MAP.get(status.lower(), status)
        if assignee and str(assignee).strip().isdigit():
            form_data["person_responsible"] = assignee
        if due_date:
            normalized = self._normalize_date(due_date)
            if normalized:  # Only send if it's a valid date
                form_data["end_date"] = normalized
        if priority:
            zoho_priority = PRIORITY_MAP.get(priority.lower())
            if zoho_priority:  # None means "skip" — don't send to Zoho
                form_data["priority"] = zoho_priority

        print(f"DEBUG: update_task form_data: {form_data}")
        data = await self._request("POST", f"projects/{project_id}/tasks/{task_id}/", data=form_data)
        return data.get("tasks", [{}])[0] if data.get("tasks") else {}

    async def delete_task(self, project_id: str, task_id: str) -> dict:
        """Delete a task from a project."""
        data = await self._request("DELETE", f"projects/{project_id}/tasks/{task_id}/")
        return data

    # ─── Member Operations ───────────────────────────────────

    async def list_project_members(self, project_id: str) -> list[dict]:
        """Get all members of a project with their roles."""
        data = await self._request("GET", f"projects/{project_id}/users/")
        return data.get("users", [])

    async def get_portal_users(self) -> list[dict]:
        """Get all users in the portal."""
        data = await self._request("GET", "users/")
        return data.get("users", [])
