"""
LangGraph Orchestration Layer.

Delegates execution and business logic to modular services in app/services.
"""

import asyncio
from typing import Annotated, TypedDict

from app.agents.action_agent import ActionAgent
from app.agents.prompts import get_fallback_prompt
from app.agents.query_agent import QueryAgent
from app.agents.supervisor import Supervisor
from app.config import settings
from app.database import db
from app.formatters.response_formatter import ResponseFormatter
from app.services.hil_service import HILService
from app.services.memory_service import MemoryService
from app.services.tool_executor import ToolExecutionService
from app.tools.query_tools import set_current_user
from app.zoho.client import ZohoClient
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph


def _merge_messages(left: list, right: list) -> list:
    return left + right


def _pick_max(left: int, right: int) -> int:
    return max(left, right)


class GraphState(TypedDict):
    messages: Annotated[list[BaseMessage], _merge_messages]
    user_id: str
    session_id: str
    agent_type: str  # "query" or "action"
    tool_rounds: Annotated[int, _pick_max]


async def run_tools(state: GraphState) -> dict:
    last = state["messages"][-1]

    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {"messages": [], "tool_rounds": state.get("tool_rounds", 0)}

    results = await asyncio.gather(
        *[ToolExecutionService.invoke_tool(tc) for tc in last.tool_calls]
    )
    return {"messages": list(results), "tool_rounds": state.get("tool_rounds", 0) + 1}


class ChatGraph:
    MAX_TOOL_ROUNDS = 3

    def __init__(self):
        self.llm = ChatGroq(
            model=settings.llm.model_name,
            api_key=settings.llm.api_key,
            temperature=settings.llm.temperature,
        )
        self.supervisor = Supervisor(self.llm)
        self.query_agent = QueryAgent(self.llm)
        self.action_agent = ActionAgent(self.llm)
        self.plain_llm = ChatGroq(
            model=settings.llm.model_name,
            api_key=settings.llm.api_key,
            temperature=settings.llm.temperature,
        )
        self.graph = self._build()

    def _build(self):
        g = StateGraph(GraphState)

        g.add_node("router", self._router)
        g.add_node("query_agent", self._query_agent)
        g.add_node("action_agent", self._action_agent)
        g.add_node("run_tools", run_tools)
        g.add_node("force_respond", self._force_respond)

        g.set_entry_point("router")

        g.add_conditional_edges(
            "router",
            lambda s: s["agent_type"],
            {"query": "query_agent", "action": "action_agent"},
        )

        g.add_conditional_edges(
            "query_agent", self._has_tool_calls, {"tools": "run_tools", "done": END}
        )
        g.add_conditional_edges(
            "action_agent", self._has_tool_calls, {"tools": "run_tools", "done": END}
        )

        g.add_conditional_edges(
            "run_tools",
            self._after_tools,
            {"query": "query_agent", "action": "action_agent", "stop": "force_respond"},
        )

        g.add_edge("force_respond", END)

        return g.compile()

    async def _router(self, state: GraphState) -> dict:
        user_msg = next(
            (
                m.content
                for m in reversed(state["messages"])
                if isinstance(m, HumanMessage)
            ),
            "",
        )

        pending = await HILService.get_pending_action(state["session_id"])
        if pending:
            return {"agent_type": "action"}

        history, _, _ = await MemoryService.get_context(
            state["user_id"], state["session_id"]
        )
        route = await self.supervisor.route(user_msg, history)
        return {"agent_type": route}

    async def _query_agent(self, state: GraphState) -> dict:
        user_id = state["user_id"]
        session_id = state["session_id"]
        user_msg = next(
            (
                m.content
                for m in reversed(state["messages"])
                if isinstance(m, HumanMessage)
            ),
            "",
        )

        memory_summary = await MemoryService.check_memory_trigger(
            user_msg, user_id, session_id
        )
        if memory_summary:
            return {"messages": [AIMessage(content=memory_summary)]}

        history, long_term, ctx = await MemoryService.get_context(user_id, session_id)

        sys = SystemMessage(
            content=self.query_agent.get_prompt(ctx, history, long_term)
        )

        msgs = [sys] + state["messages"]
        try:
            resp = await self.query_agent.agent.ainvoke(msgs)
        except Exception as e:
            return {
                "messages": [
                    AIMessage(
                        content="⚠️ I couldn't process that request. Please try rephrasing it."
                    )
                ]
            }

        return {"messages": [resp]}

    async def _action_agent(self, state: GraphState) -> dict:
        user_id = state["user_id"]
        session_id = state["session_id"]
        user_msg = next(
            (
                m.content
                for m in reversed(state["messages"])
                if isinstance(m, HumanMessage)
            ),
            "",
        )

        pending = await HILService.get_pending_action(session_id)
        if pending:
            user_msg_lower = user_msg.strip().lower()
            if user_msg_lower in (
                "yes",
                "y",
                "confirm",
                "approve",
                "sure",
                "go ahead",
                "do it",
                "ok",
            ):
                await HILService.resolve_pending_action(pending["id"], "approved")
                try:
                    result = await ToolExecutionService.execute_pending_action(
                        user_id, pending["tool_name"], pending["parameters"]
                    )
                    return {"messages": [AIMessage(content=result)]}
                except Exception as e:
                    return {
                        "messages": [AIMessage(content=f"❌ Action failed: {str(e)}")]
                    }
            else:
                await HILService.resolve_pending_action(pending["id"], "declined")
                return {
                    "messages": [
                        AIMessage(content="❌ Action cancelled. No changes were made.")
                    ]
                }

        history, long_term, ctx = await MemoryService.get_context(user_id, session_id)

        task_context = ""
        try:
            c = ZohoClient(user_id)
            projects = await c.list_projects()
            found_pid = next(
                (
                    p.get("id_string", str(p.get("id", "")))
                    for p in projects
                    if p.get("name", "") and p["name"].lower() in user_msg.lower()
                ),
                None,
            )

            if found_pid:
                tasks = await c.list_tasks(found_pid)
                if tasks:
                    task_lines = [
                        f"  - {t.get('name','?')} (ID: {t.get('id_string', t.get('id','?'))}) Status: {t.get('status',{}).get('name','?') if isinstance(t.get('status'), dict) else '?'}"
                        for t in tasks[:10]
                    ]
                    task_context = (
                        f"\n\nREAL TASKS in the discussed project:\n"
                        + "\n".join(task_lines)
                    )
        except Exception:
            pass

        sys = SystemMessage(
            content=self.action_agent.get_prompt(ctx, history, long_term, task_context)
        )

        msgs = [sys] + state["messages"]
        resp = await self.action_agent.agent.ainvoke(msgs)

        if resp.tool_calls:
            error_msg = await HILService.validate_and_store_tool_calls(
                resp.tool_calls, user_id, session_id
            )
            if error_msg:
                return {"messages": [AIMessage(content=error_msg)]}

            return {
                "messages": [
                    AIMessage(content=HILService.format_hil_message(resp.tool_calls))
                ]
            }

        return {"messages": [resp]}

    async def _force_respond(self, state: GraphState) -> dict:
        tool_data = [
            m.content
            for m in state["messages"]
            if isinstance(m, ToolMessage) and m.content
        ]
        if tool_data:
            return {"messages": [AIMessage(content="\n\n".join(tool_data))]}

        user_msg = next(
            (m.content for m in state["messages"] if isinstance(m, HumanMessage)), ""
        )
        resp = await self.plain_llm.ainvoke(
            [
                SystemMessage(content=get_fallback_prompt()),
                HumanMessage(content=user_msg),
            ]
        )
        return {"messages": [resp]}

    def _has_tool_calls(self, state: GraphState) -> str:
        last = state["messages"][-1] if state["messages"] else None
        if last and isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "tools"
        return "done"

    def _after_tools(self, state: GraphState) -> str:
        if state.get("tool_rounds", 0) >= self.MAX_TOOL_ROUNDS:
            return "stop"
        for msg in reversed(state["messages"]):
            if isinstance(msg, ToolMessage) and msg.content and len(msg.content) > 100:
                return "stop"
        return state["agent_type"]

    async def process_message(
        self, user_id: str, session_id: str, message: str
    ) -> dict:
        set_current_user(user_id)
        await db.create_session(session_id, user_id)

        initial = {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id,
            "session_id": session_id,
            "agent_type": "",
            "tool_rounds": 0,
        }

        result = await self.graph.ainvoke(initial, config={"recursion_limit": 30})

        final = ResponseFormatter.extract_response(result.get("messages", []))

        from app.memory.store import MemoryStore

        memory = MemoryStore(user_id, session_id)
        await memory.add_message("user", message)
        await memory.add_message(
            "assistant", final, {"agent": result.get("agent_type", "")}
        )

        await MemoryService.save_long_term(user_id, session_id, message, final)

        pending = await HILService.get_pending_action(session_id)
        pending_data = (
            {
                "action_type": pending["action_type"],
                "tool_name": pending["tool_name"],
                "description": pending["description"],
                "parameters": pending["parameters"],
            }
            if pending
            else None
        )

        return {
            "message": final,
            "agent_used": result.get("agent_type", "unknown"),
            "pending_action": pending_data,
        }


_graph: ChatGraph = None


def initialize_graph():
    global _graph
    _graph = ChatGraph()
    return _graph


def get_graph() -> ChatGraph:
    global _graph
    if _graph is None:
        _graph = initialize_graph()
    return _graph
