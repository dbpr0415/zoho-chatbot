"""
Supervisor/Router — classifies user intent and routes to the correct agent.
Uses LLM to decide: query (read) or action (write).
"""

from langchain_core.messages import SystemMessage


from app.agents.prompts import SUPERVISOR_PROMPT


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
