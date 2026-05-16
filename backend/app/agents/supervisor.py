"""
Supervisor/Router — classifies user intent and routes to the correct agent.
Uses LLM to decide: query (read) or action (write).
"""

from langchain_core.messages import SystemMessage


SUPERVISOR_PROMPT = """You are the Supervisor/Router for a Zoho Projects assistant chatbot.
Your job is to analyze the user's message and decide which agent should handle it.

You MUST respond with EXACTLY one word — either "query" or "action":
- "query" — for READ operations (listing, viewing, fetching, searching, summarising data)
- "action" — for WRITE operations (creating, updating, deleting, assigning tasks)

ROUTING RULES:
- "What projects do I have?" → query
- "Show me tasks" → query
- "Who has the most tasks?" → query
- "List members" → query
- "Get task details" → query
- "Create a task" → action
- "Update task status" → action
- "Delete task" → action
- "Assign task to..." → action
- "Change priority..." → action
- "Mark as complete" → action

If the user is CONFIRMING or DECLINING a previous action (saying "yes", "confirm", "no", "cancel"):
→ respond with "action"

If unclear, default to "query".

CHAT HISTORY:
{chat_history}

USER MESSAGE: {message}

Respond with only "query" or "action"."""


class Supervisor:
    """Routes incoming messages to the appropriate agent using LLM intent classification."""

    def __init__(self, llm):
        self.llm = llm

    async def route(self, message: str, chat_history: str = "") -> str:
        """Classify intent as 'query' or 'action'."""
        prompt = SUPERVISOR_PROMPT.format(message=message, chat_history=chat_history)
        response = await self.llm.ainvoke([SystemMessage(content=prompt)])
        decision = response.content.strip().lower()
        if "action" in decision:
            return "action"
        return "query"
