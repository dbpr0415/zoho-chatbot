import json
import re
from typing import Optional
from app.memory.store import MemoryStore
from app.zoho.client import ZohoClient

class MemoryService:
    MEMORY_TRIGGERS = [
        "what was i talking about", "what did i do last", "what was my last",
        "what were we discussing", "recall my", "remember what",
        "what was i working on", "last session", "previous session",
        "what did i ask", "last time", "history", "remember",
    ]

    @staticmethod
    async def get_context(user_id: str, session_id: str):
        memory = MemoryStore(user_id, session_id)
        history = await memory.get_formatted_history(3)
        long_term = await memory.get_all_long_term()
        project = await memory.get_current_project()
        ctx = f"Current project: {json.dumps(project)}" if project else "No project selected"
        return history, long_term, ctx

    @staticmethod
    async def check_memory_trigger(user_msg: str, user_id: str, session_id: str) -> Optional[str]:
        msg_lower = user_msg.lower()
        if any(t in msg_lower for t in MemoryService.MEMORY_TRIGGERS):
            memory = MemoryStore(user_id, session_id)
            summary = await memory.get_memory_summary()
            return summary
        return None

    @staticmethod
    async def save_long_term(user_id: str, session_id: str, user_msg: str, response: str):
        memory = MemoryStore(user_id, session_id)
        msg_lower = user_msg.lower()
        resp_lower = response.lower()

        topic = user_msg[:200]
        await memory.store_interaction("last_topic", topic)
        await memory.store_interaction("last_response_preview", response[:200])

        try:
            c = ZohoClient(user_id)
            projects = await c.list_projects()
            for p in projects:
                pname = p.get("name", "")
                pid = p.get("id_string", str(p.get("id", "")))
                if pname and (pname.lower() in msg_lower or pname.lower() in resp_lower):
                    await memory.update_project_context(pid, pname)
                    await memory.store_interaction("last_project_discussed", pname)
                    break
        except Exception:
            pass

        # Extract and persist contextual task listings
        if "tasks" in resp_lower and any(kw in msg_lower for kw in ["list", "show", "tasks", "what"]):
            task_names = re.findall(r'\d+\.\s+\*{0,2}([^\n*]+?)\*{0,2}\s*(?:\(|\[|ID|Status)', response)
            if task_names:
                await memory.store_interaction("last_tasks_viewed", ", ".join(task_names[:5]))

        if any(kw in resp_lower for kw in ["task created", "task updated", "task deleted", "successfully"]):
            await memory.store_interaction("last_action", f"{user_msg[:100]} → {response[:150]}")

        if any(w in msg_lower for w in ["always", "prefer", "default", "usually", "i like"]):
            await memory.store_preference("user_preference", user_msg)
