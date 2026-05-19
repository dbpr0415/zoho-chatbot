from typing import Any, Dict

from app.services.safe_executor import SafeExecutorService
from app.tools.action_tools import ACTION_TOOLS
from app.tools.query_tools import QUERY_TOOLS
from langchain_core.messages import ToolMessage

ALL_TOOLS = QUERY_TOOLS + ACTION_TOOLS
TOOL_MAP = {t.name: t for t in ALL_TOOLS}


class ToolExecutionService:
    @staticmethod
    async def execute_pending_action(
        user_id: str, tool_name: str, params: Dict[str, Any]
    ) -> str:
        """Delegates pre-validated pending actions to the centralized SafeExecutorService."""
        return await SafeExecutorService.execute_tool(user_id, tool_name, params)

    @staticmethod
    async def invoke_tool(tc: Dict[str, Any]) -> ToolMessage:
        """Invokes a Langchain tool for the Query Agent."""
        fn = TOOL_MAP.get(tc["name"])
        if not fn:
            return ToolMessage(
                content=f"Unknown tool '{tc['name']}'",
                tool_call_id=tc["id"],
                name=tc["name"],
            )
        try:
            out = await fn.ainvoke(tc["args"])
            return ToolMessage(content=str(out), tool_call_id=tc["id"], name=tc["name"])
        except Exception as e:
            return ToolMessage(
                content=f"Error: {e}", tool_call_id=tc["id"], name=tc["name"]
            )
