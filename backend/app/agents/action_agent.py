"""
Action Agent — handles all write operations with Human-in-the-Loop.
"""

from app.tools.action_tools import ACTION_TOOLS


class ActionAgent:
    """Agent responsible for all write/mutation operations on Zoho Projects."""

    def __init__(self, llm):
        self.llm = llm
        self.tools = ACTION_TOOLS
        self.agent = self.llm.bind_tools(self.tools)
