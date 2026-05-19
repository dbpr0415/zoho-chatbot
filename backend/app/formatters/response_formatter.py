from langchain_core.messages import AIMessage, ToolMessage
from typing import List

class ResponseFormatter:
    @staticmethod
    def extract_response(messages: List) -> str:
        """Smart response extraction: prefer substantial AI message, fallback to tool data."""
        last_ai = ""
        last_tool = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content and not last_ai:
                last_ai = msg.content
            if isinstance(msg, ToolMessage) and msg.content and not last_tool:
                last_tool = msg.content

        # Substantial AI response (>80 chars) — use it directly
        if last_ai and len(last_ai) > 80:
            return last_ai
        # Brief AI + tool data — combine
        if last_ai and last_tool:
            return f"{last_ai}\n\n{last_tool}"
        # Only tool data
        if last_tool:
            return last_tool
        # Brief AI only
        if last_ai:
            return last_ai
        return "I couldn't process that request. Please try again."
