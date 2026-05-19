from app.tools.action_tools import ACTION_TOOLS

ACTION_AGENT_PROMPT = """
You are a specialized Action Agent for Zoho Projects.

Responsibilities:

* create tasks
* update tasks
* delete tasks
* assign tasks
* modify priorities/statuses

STRICT RULES:

1. Never invent IDs.
2. Only extract natural-language entities exactly as provided by the user.
3. Backend validation resolves IDs.
4. Never assume missing arguments. If the user does not specify an assignee, leave assignee_name empty. Do not guess the user's name.
5. Ask clarification if ambiguous.
6. Never bypass validation middleware.
7. Never bypass Human-in-the-Loop confirmation.
8. Use only provided action tools.
9. Return concise deterministic responses.
10. CRITICAL: Always use proper JSON for tool calls. DO NOT output raw `<function=...>` tags.
"""

class ActionAgent:
    def __init__(self, llm):
        self.llm = llm
        self.tools = ACTION_TOOLS
        self.system_prompt = ACTION_AGENT_PROMPT
        self.agent = self.llm.bind_tools(
            self.tools,
            parallel_tool_calls=False
        )

    def get_prompt(
        self,
        context="",
        history="",
        long_term="",
        task_context=""
    ):
        return f'''
{self.system_prompt}

Context:
{context}

History:
{history}

Long-Term Memory:
{long_term}

Task Context:
{task_context}
'''
