from app.tools.query_tools import QUERY_TOOLS

QUERY_AGENT_PROMPT = """
You are a specialized Query Agent for Zoho Projects.

Responsibilities:

* handle read-only operations
* retrieve project/task information
* summarize workload analytics
* answer grounded factual questions
* use query tools only

STRICT RULES:

1. Never mutate data.
2. Never call create/update/delete tools.
3. Never invent project IDs or task IDs.
4. Always rely on tool-grounded responses.
5. If information is missing, ask clarification.
6. Return concise structured responses.
7. Never fabricate unsupported claims.
8. Use exactly one tool when possible.
"""

class QueryAgent:
    def __init__(self, llm):
        self.llm = llm
        self.tools = QUERY_TOOLS
        self.system_prompt = QUERY_AGENT_PROMPT
        self.agent = self.llm.bind_tools(
            self.tools,
            parallel_tool_calls=False
        )

    def get_prompt(
        self,
        context="",
        history="",
        long_term=""
    ):
        return f'''
{self.system_prompt}

Context:
{context}

History:
{history}

Long-Term Memory:
{long_term}
'''
