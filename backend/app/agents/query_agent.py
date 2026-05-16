"""
Query Agent — handles all read-only operations.
"""

from app.tools.query_tools import QUERY_TOOLS


class QueryAgent:
    """Agent responsible for all read/query operations on Zoho Projects."""

    def __init__(self, llm):
        self.llm = llm
        self.tools = QUERY_TOOLS
        self.agent = self.llm.bind_tools(self.tools)
