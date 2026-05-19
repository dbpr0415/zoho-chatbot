import json
from typing import Optional

from app.database import db


class MemoryStore:
    """
    Dual-layer memory system:
    - Short-term: Chat history within a session (e.g., "show tasks for that project")
    - Long-term: Cross-session context (e.g., user's frequently accessed project)
    """

    def __init__(self, user_id: str, session_id: str):
        self.user_id = user_id
        self.session_id = session_id

    # ─── Short-term Memory (Session) ─────────────────────────

    async def add_message(self, role: str, content: str, metadata: dict = None):
        """Add a message to the current session's short-term memory."""
        await db.add_message(self.session_id, role, content, metadata)

    async def get_chat_history(self, limit: int = 20) -> list[dict]:
        """Retrieve recent chat history for the current session."""
        return await db.get_session_messages(self.session_id, limit)

    async def get_formatted_history(self, limit: int = 10) -> str:
        """Get chat history formatted for LLM context injection."""
        messages = await self.get_chat_history(limit)
        if not messages:
            return "(no prior messages in this session)"
        lines = []
        for msg in messages:
            role = "User" if msg["role"] == "user" else "Assistant"
            # Truncate long messages for context window efficiency
            content = msg["content"][:300]
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    # ─── Long-term Memory (Cross-session) ────────────────────

    async def store_preference(self, key: str, value: str):
        """Store a user preference for cross-session memory."""
        await db.store_long_term(self.user_id, "preference", key, value)

    async def store_context(self, key: str, value: str):
        """Store contextual information (e.g., frequently accessed project)."""
        await db.store_long_term(self.user_id, "context", key, value)

    async def store_interaction(self, key: str, value: str):
        """Store an interaction summary for future reference."""
        await db.store_long_term(self.user_id, "interaction", key, value)

    async def get_preferences(self) -> list[dict]:
        """Get all stored user preferences."""
        return await db.get_long_term(self.user_id, "preference")

    async def get_contexts(self) -> list[dict]:
        """Get all stored contextual memories."""
        return await db.get_long_term(self.user_id, "context")

    async def get_all_long_term(self) -> str:
        """Get all long-term memories formatted for LLM context."""
        memories = await db.get_long_term(self.user_id)
        if not memories:
            return "(no long-term memories yet)"
        lines = ["📚 **User Memory:**"]
        for mem in memories[:10]:  # Cap to avoid context overflow
            lines.append(f"- [{mem['memory_type']}] {mem['key']}: {mem['value'][:150]}")
        return "\n".join(lines)

    # ─── Project Context Tracking ────────────────────────────

    async def update_project_context(self, project_id: str, project_name: str):
        """Track which project the user is currently working with."""
        await self.store_context(
            "current_project", json.dumps({"id": project_id, "name": project_name})
        )
        await self.store_context(f"accessed_project_{project_id}", project_name)

    async def get_current_project(self) -> Optional[dict]:
        """Get the project the user is currently focused on."""
        contexts = await self.get_contexts()
        for ctx in contexts:
            if ctx["key"] == "current_project":
                try:
                    return json.loads(ctx["value"])
                except json.JSONDecodeError:
                    return None
        return None

    async def get_memory_summary(self) -> str:
        """Generate a human-readable summary of what the user was doing.
        Used to answer 'what was I talking about?' across sessions.
        """
        memories = await db.get_long_term(self.user_id)
        if not memories:
            return (
                "🧠 I don't have any memory of previous sessions yet.\n\n"
                "Start chatting and I'll remember your projects, tasks, and actions for next time!"
            )

        # Index by key (most recent wins since store_long_term uses INSERT OR REPLACE)
        mem_map = {}
        for m in memories:
            mem_map[m["key"]] = m["value"]

        lines = ["🧠 **Here's what I remember from our last session:**\n"]

        last_topic = mem_map.get("last_topic")
        if last_topic:
            lines.append(f"💬 **Last question you asked:** _{last_topic}_")

        last_proj = mem_map.get("last_project_discussed")
        if last_proj:
            lines.append(f"📁 **Project you were working on:** _{last_proj}_")

        last_tasks = mem_map.get("last_tasks_viewed")
        if last_tasks:
            lines.append(f"📝 **Tasks you were looking at:** _{last_tasks}_")

        last_action = mem_map.get("last_action")
        if last_action:
            lines.append(f"⚡ **Last action taken:** _{last_action[:120]}_")

        last_resp = mem_map.get("last_response_preview")
        if last_resp and not last_topic:
            lines.append(f"💡 **Last response I gave:** _{last_resp[:120]}_")

        # Projects accessed
        proj_contexts = [
            v for k, v in mem_map.items() if k.startswith("accessed_project_")
        ]
        if proj_contexts:
            lines.append(
                f"🗂️ **Projects you've accessed:** _{', '.join(proj_contexts[:3])}_"
            )

        lines.append(
            "\n_I automatically remember your last topic, project, and actions across sessions._"
        )
        return "\n".join(lines)
