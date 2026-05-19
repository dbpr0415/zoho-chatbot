"""
Async SQLite database setup for token storage and memory persistence.
"""

import json
import os
from datetime import datetime
from typing import Optional

import aiosqlite

DB_PATH = os.getenv(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "zoho_assistant.db"),
)


class Database:
    """Async SQLite database manager."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Initialize database connection and create tables."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._create_tables()

    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()

    async def _create_tables(self):
        """Create required tables if they don't exist."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS user_tokens (
                user_id TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                user_email TEXT,
                portal_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_active TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES user_tokens(user_id)
            );

            CREATE TABLE IF NOT EXISTS short_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
            );

            CREATE TABLE IF NOT EXISTS long_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES user_tokens(user_id)
            );

            CREATE TABLE IF NOT EXISTS pending_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                description TEXT NOT NULL,
                parameters TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
            );
        """)
        await self._connection.commit()

    # ─── Token Operations ────────────────────────────────────

    async def store_token(
        self,
        user_id: str,
        access_token: str,
        refresh_token: str,
        expires_at: str,
        user_email: str = None,
        portal_id: str = None,
    ):
        """Store or update user OAuth tokens."""
        await self._connection.execute(
            """
            INSERT INTO user_tokens (user_id, access_token, refresh_token, expires_at, user_email, portal_id, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at = excluded.expires_at,
                user_email = COALESCE(excluded.user_email, user_tokens.user_email),
                portal_id = COALESCE(excluded.portal_id, user_tokens.portal_id),
                updated_at = excluded.updated_at
        """,
            (
                user_id,
                access_token,
                refresh_token,
                expires_at,
                user_email,
                portal_id,
                datetime.utcnow().isoformat(),
            ),
        )
        await self._connection.commit()

    async def get_token(self, user_id: str) -> Optional[dict]:
        """Retrieve stored tokens for a user."""
        cursor = await self._connection.execute(
            "SELECT * FROM user_tokens WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_access_token(
        self, user_id: str, access_token: str, expires_at: str
    ):
        """Update only the access token after a refresh."""
        await self._connection.execute(
            """
            UPDATE user_tokens SET access_token = ?, expires_at = ?, updated_at = ?
            WHERE user_id = ?
        """,
            (access_token, expires_at, datetime.utcnow().isoformat(), user_id),
        )
        await self._connection.commit()

    # ─── Session Operations ──────────────────────────────────

    async def create_session(self, session_id: str, user_id: str):
        """Create a new chat session."""
        await self._connection.execute(
            """
            INSERT OR IGNORE INTO chat_sessions (session_id, user_id) VALUES (?, ?)
        """,
            (session_id, user_id),
        )
        await self._connection.commit()

    async def update_session_activity(self, session_id: str):
        """Update last active timestamp for a session."""
        await self._connection.execute(
            """
            UPDATE chat_sessions SET last_active = ? WHERE session_id = ?
        """,
            (datetime.utcnow().isoformat(), session_id),
        )
        await self._connection.commit()

    async def list_user_sessions(self, user_id: str) -> list[dict]:
        """List all sessions for a user, newest first, with first user message as title."""
        cursor = await self._connection.execute(
            """
            SELECT cs.session_id, cs.created_at, cs.last_active,
                   (SELECT content FROM short_term_memory
                    WHERE session_id = cs.session_id AND role = 'user'
                    ORDER BY created_at ASC LIMIT 1) as title,
                   (SELECT COUNT(*) FROM short_term_memory
                    WHERE session_id = cs.session_id) as message_count
            FROM chat_sessions cs
            WHERE cs.user_id = ?
            ORDER BY cs.last_active DESC
            LIMIT 50
        """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            r = dict(row)
            # Only include sessions that have at least 1 message
            if r.get("message_count", 0) > 0:
                # Truncate title to 45 chars
                title = r.get("title") or "New conversation"
                r["title"] = (title[:45] + "…") if len(title) > 45 else title
                result.append(r)
        return result

    async def delete_session(self, session_id: str, user_id: str):
        """Delete a session and all its messages (only if owned by user)."""
        await self._connection.execute(
            """
            DELETE FROM short_term_memory WHERE session_id = ?
        """,
            (session_id,),
        )
        await self._connection.execute(
            """
            DELETE FROM pending_actions WHERE session_id = ?
        """,
            (session_id,),
        )
        await self._connection.execute(
            """
            DELETE FROM chat_sessions WHERE session_id = ? AND user_id = ?
        """,
            (session_id, user_id),
        )
        await self._connection.commit()

    # ─── Short-term Memory ───────────────────────────────────

    async def add_message(
        self, session_id: str, role: str, content: str, metadata: dict = None
    ):
        """Add a message to short-term memory."""
        await self._connection.execute(
            """
            INSERT INTO short_term_memory (session_id, role, content, metadata)
            VALUES (?, ?, ?, ?)
        """,
            (session_id, role, content, json.dumps(metadata) if metadata else None),
        )
        await self._connection.commit()

    async def get_session_messages(
        self, session_id: str, limit: int = 20
    ) -> list[dict]:
        """Get recent messages from a session."""
        cursor = await self._connection.execute(
            """
            SELECT role, content, metadata, created_at
            FROM short_term_memory
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """,
            (session_id, limit),
        )
        rows = await cursor.fetchall()
        messages = []
        for row in reversed(rows):
            msg = {"role": dict(row)["role"], "content": dict(row)["content"]}
            if dict(row)["metadata"]:
                msg["metadata"] = json.loads(dict(row)["metadata"])
            messages.append(msg)
        return messages

    # ─── Long-term Memory ────────────────────────────────────

    async def store_long_term(
        self, user_id: str, memory_type: str, key: str, value: str
    ):
        """Store a long-term memory entry."""
        await self._connection.execute(
            """
            INSERT INTO long_term_memory (user_id, memory_type, key, value, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
            (user_id, memory_type, key, value, datetime.utcnow().isoformat()),
        )
        await self._connection.commit()

    async def get_long_term(self, user_id: str, memory_type: str = None) -> list[dict]:
        """Retrieve long-term memories for a user."""
        if memory_type:
            cursor = await self._connection.execute(
                """
                SELECT memory_type, key, value, updated_at
                FROM long_term_memory WHERE user_id = ? AND memory_type = ?
                ORDER BY updated_at DESC
            """,
                (user_id, memory_type),
            )
        else:
            cursor = await self._connection.execute(
                """
                SELECT memory_type, key, value, updated_at
                FROM long_term_memory WHERE user_id = ?
                ORDER BY updated_at DESC
            """,
                (user_id,),
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # ─── Pending Actions ─────────────────────────────────────

    async def store_pending_action(
        self,
        session_id: str,
        user_id: str,
        action_type: str,
        tool_name: str,
        description: str,
        parameters: dict,
    ) -> int:
        """Store a pending action awaiting user confirmation."""
        cursor = await self._connection.execute(
            """
            INSERT INTO pending_actions (session_id, user_id, action_type, tool_name, description, parameters)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                session_id,
                user_id,
                action_type,
                tool_name,
                description,
                json.dumps(parameters),
            ),
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_pending_action(self, session_id: str) -> Optional[dict]:
        """Get the latest pending action for a session."""
        cursor = await self._connection.execute(
            """
            SELECT * FROM pending_actions
            WHERE session_id = ? AND status = 'pending'
            ORDER BY created_at DESC LIMIT 1
        """,
            (session_id,),
        )
        row = await cursor.fetchone()
        if row:
            result = dict(row)
            result["parameters"] = json.loads(result["parameters"])
            return result
        return None

    async def resolve_pending_action(self, action_id: int, status: str):
        """Mark a pending action as approved or declined."""
        await self._connection.execute(
            """
            UPDATE pending_actions SET status = ? WHERE id = ?
        """,
            (status, action_id),
        )
        await self._connection.commit()

    async def update_pending_parameters(self, action_id: int, parameters: dict):
        """Update the parameters of a pending action."""
        await self._connection.execute(
            """
            UPDATE pending_actions SET parameters = ? WHERE id = ?
        """,
            (json.dumps(parameters), action_id),
        )
        await self._connection.commit()


# Global database instance
db = Database()
