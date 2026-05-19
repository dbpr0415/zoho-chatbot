import json
from typing import Optional, Dict, Any, List
from langchain_core.messages import AIMessage
from app.database import db
from app.services.safe_executor import SafeExecutorService

class HILService:
    @staticmethod
    async def get_pending_action(session_id: str) -> Optional[Dict[str, Any]]:
        return await db.get_pending_action(session_id)

    @staticmethod
    async def resolve_pending_action(action_id: int, status: str):
        await db.resolve_pending_action(action_id, status)

    @staticmethod
    async def validate_and_store_tool_calls(tool_calls: List[Dict], user_id: str, session_id: str) -> Optional[str]:
        """Validates tool calls via SafeExecutorService and stores them as pending actions.
        Returns an error message if validation fails, otherwise None.
        """
        for tc in tool_calls:
            tool_name = tc["name"]
            raw_args = tc["args"]
            
            # Centralized Validation & Formatting
            is_valid, msg, resolved_args, desc = await SafeExecutorService.validate_and_format(
                user_id, tool_name, raw_args
            )
                
            if not is_valid:
                return msg  # Return error message immediately
                
            # Fallback description if formatter fails
            if not desc:
                desc = f"{tool_name}: {json.dumps(resolved_args)}"

            await db.store_pending_action(
                session_id=session_id,
                user_id=user_id,
                action_type=tool_name.replace("_task", ""),
                tool_name=tool_name,
                description=desc,
                parameters=resolved_args,
            )
        return None

    @staticmethod
    def format_hil_message(tool_calls: List[Dict]) -> str:
        parts = []
        for tc in tool_calls:
            action = tc["name"].replace("_", " ").title()
            parts.append(f"🔔 **Action: {action}**\n")
            for k, v in tc["args"].items():
                if v is not None:
                    parts.append(f"- **{k.replace('_', ' ').title()}:** {v}")
            parts.append("\n👉 **Do you want me to proceed? (Yes/No)**")
        return "\n".join(parts)
