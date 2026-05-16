"""
LangGraph Stateful Graph — Core AI Engine.

Architecture:
  ┌─────────┐     ┌─────────────┐     ┌───────────┐
  │  Router  │────▶│ Query Agent │────▶│ Run Tools │──┐
  │(Supervisor)│   └─────────────┘     └───────────┘  │
  └─────────┘     ┌──────────────┐    ┌──────────────┐│
       │          │ Action Agent │────▶│  Run Tools   ││
       └─────────▶│  (with HIL)  │    └──────────────┘│
                  └──────────────┘           │         │
                         ▲                   │         │
                         └───────────────────┘         │
                  ┌──────────────┐                     │
                  │Force Respond │◀── (max 3 rounds) ──┘
                  └──────┬───────┘
                         ▼
                        END

Features:
- 8 tools (5 query + 3 action)
- Short-term memory (within session)
- Long-term memory (across sessions)
- Human-in-the-Loop for write operations
- Max tool round cap (prevents infinite loops)
"""

import json
import re
from typing import TypedDict, Annotated
from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage, ToolMessage, BaseMessage
)
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END

from app.config import settings
from app.agents.supervisor import Supervisor
from app.memory.store import MemoryStore
from app.tools.query_tools import QUERY_TOOLS, set_current_user
from app.tools.action_tools import ACTION_TOOLS, create_task, update_task, delete_task
from app.database import db

ALL_TOOLS = QUERY_TOOLS + ACTION_TOOLS
TOOL_MAP = {t.name: t for t in ALL_TOOLS}


# ─── Graph State ─────────────────────────────────────────────

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


# ─── Tool Executor Node ─────────────────────────────────────

async def run_tools(state: GraphState) -> dict:
    """Execute all tool calls from the last AI message in parallel."""
    import asyncio
    last = state["messages"][-1]
    
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {"messages": [], "tool_rounds": state.get("tool_rounds", 0)}

    async def _invoke_tool(tc):
        fn = TOOL_MAP.get(tc["name"])
        if not fn:
            return ToolMessage(content=f"Unknown tool '{tc['name']}'", tool_call_id=tc["id"], name=tc["name"])
        try:
            out = await fn.ainvoke(tc["args"])
            return ToolMessage(content=str(out), tool_call_id=tc["id"], name=tc["name"])
        except Exception as e:
            return ToolMessage(content=f"Error: {e}", tool_call_id=tc["id"], name=tc["name"])

    # Run all tool calls in parallel
    results = await asyncio.gather(*[_invoke_tool(tc) for tc in last.tool_calls])

    return {"messages": list(results), "tool_rounds": state.get("tool_rounds", 0) + 1}


# ─── Graph Builder ───────────────────────────────────────────

class ChatGraph:
    MAX_TOOL_ROUNDS = 3

    def __init__(self):
        self.llm = ChatGroq(
            model=settings.llm.model_name,
            api_key=settings.llm.api_key,
            temperature=settings.llm.temperature,
        )
        self.supervisor = Supervisor(self.llm)
        self.query_llm = self.llm.bind_tools(QUERY_TOOLS, parallel_tool_calls=False)
        self.action_llm = self.llm.bind_tools(ACTION_TOOLS, parallel_tool_calls=False)
        self.plain_llm = ChatGroq(
            model=settings.llm.model_name,
            api_key=settings.llm.api_key,
            temperature=settings.llm.temperature,
        )
        self.graph = self._build()

    def _build(self):
        g = StateGraph(GraphState)

        # Nodes
        g.add_node("router", self._router)
        g.add_node("query_agent", self._query_agent)
        g.add_node("action_agent", self._action_agent)
        g.add_node("run_tools", run_tools)
        g.add_node("force_respond", self._force_respond)

        # Entry
        g.set_entry_point("router")

        # Router → agent
        g.add_conditional_edges("router", lambda s: s["agent_type"],
                                {"query": "query_agent", "action": "action_agent"})

        # Agent → tools or END
        g.add_conditional_edges("query_agent", self._has_tool_calls,
                                {"tools": "run_tools", "done": END})
        g.add_conditional_edges("action_agent", self._has_tool_calls,
                                {"tools": "run_tools", "done": END})

        # Tools → agent (or force stop if max rounds)
        g.add_conditional_edges("run_tools", self._after_tools,
                                {"query": "query_agent", "action": "action_agent", "stop": "force_respond"})

        g.add_edge("force_respond", END)

        return g.compile()

    # ─── Router Node ─────────────────────────────────────────

    async def _router(self, state: GraphState) -> dict:
        user_msg = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                user_msg = msg.content
                break

        # Pending action = always route to action agent
        pending = await db.get_pending_action(state["session_id"])
        if pending:
            return {"agent_type": "action"}

        memory = MemoryStore(state["user_id"], state["session_id"])
        history = await memory.get_formatted_history(3)
        route = await self.supervisor.route(user_msg, history)
        return {"agent_type": route}

    # ─── Query Agent Node ────────────────────────────────────

    async def _query_agent(self, state: GraphState) -> dict:
        memory = MemoryStore(state["user_id"], state["session_id"])
        history = await memory.get_formatted_history(3)
        long_term = await memory.get_all_long_term()
        project = await memory.get_current_project()
        ctx = f"Current project: {json.dumps(project)}" if project else "No project selected"

        # ── Memory-recall shortcut: answer directly from LTM, skip tool calls ──
        user_msg = next(
            (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), ""
        ).lower()
        MEMORY_TRIGGERS = [
            "what was i talking about", "what did i do last", "what was my last",
            "what were we discussing", "recall my", "remember what",
            "what was i working on", "last session", "previous session",
            "what did i ask", "last time", "history", "remember",
        ]
        if any(t in user_msg for t in MEMORY_TRIGGERS):
            summary = await memory.get_memory_summary()
            return {"messages": [AIMessage(content=summary)]}

        sys = SystemMessage(content=f"""You are a Zoho Projects AI assistant (Query Agent).
You handle READ operations using: list_projects, list_tasks, get_task_details, list_project_members, get_task_utilisation.

CRITICAL RULES:
1. Call EXACTLY ONE tool per response. NEVER call multiple tools at once.
2. TASK IDs and PROJECT IDs are DIFFERENT numbers. Never mix them.
   - Project IDs (from list_projects): 444530000000068834, 444530000000070081, 444530000000070004
   - Task IDs (from list_tasks): 444530000000071003, 444530000000070158 etc.
3. When user says "first task", "go out task", etc. → use the name/reference as task_id (auto-resolved).
4. When user says "get task details" without specifying which task:
   - If CHAT HISTORY has a task list: call get_task_details with project_id and task_id from history
   - Otherwise: call list_tasks first to get the task list
5. STOP after one tool call.
6. For "who has the most tasks?" or "task utilisation" without a specific project → call get_task_utilisation with project_id="all"
7. For "who has the most tasks in interviews?" → call get_task_utilisation with project_id="interviews"
8. NEVER call any tool for questions about memory, past sessions, or history — answer from LONG-TERM MEMORY directly.

CONTEXT: {ctx}

CHAT HISTORY (use this to find task IDs and project IDs):
{history}

LONG-TERM MEMORY:
{long_term}""")

        msgs = [sys] + state["messages"]
        try:
            resp = await self.query_llm.ainvoke(msgs)
        except Exception as e:
            err_str = str(e)
            # Groq sometimes generates tool calls in wrong XML format — parse and execute directly
            result = await self._handle_groq_tool_error(err_str, state["user_id"])
            if result:
                return {"messages": [AIMessage(content=result)]}
            return {"messages": [AIMessage(content="⚠️ I couldn't process that request. Please try rephrasing it.")]}

        return {"messages": [resp]}

    # ─── Action Agent Node ───────────────────────────────────

    async def _action_agent(self, state: GraphState) -> dict:
        memory = MemoryStore(state["user_id"], state["session_id"])
        history = await memory.get_formatted_history(3)
        long_term = await memory.get_all_long_term()
        project = await memory.get_current_project()
        ctx = f"Current project: {json.dumps(project)}" if project else "No project selected"

        # Handle pending HIL confirmation
        pending = await db.get_pending_action(state["session_id"])
        if pending:
            user_msg = ""
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    user_msg = msg.content.strip().lower()
                    break

            if user_msg in ("yes", "y", "confirm", "approve", "sure", "go ahead", "do it", "ok"):
                await db.resolve_pending_action(pending["id"], "approved")
                # ─── DIRECTLY EXECUTE TOOL (bypass LLM to avoid wrong tool calls) ───
                tool_name = pending["tool_name"]
                params = pending["parameters"]
                from app.tools.query_tools import set_current_user
                set_current_user(state["user_id"])
                TOOL_FN_MAP = {
                    "create_task": create_task,
                    "update_task": update_task,
                    "delete_task": delete_task,
                }
                fn = TOOL_FN_MAP.get(tool_name)
                if fn:
                    try:
                        result = await fn.ainvoke(params)
                        return {"messages": [AIMessage(content=result)]}
                    except Exception as e:
                        return {"messages": [AIMessage(content=f"❌ Action failed: {str(e)}")]}
                else:
                    return {"messages": [AIMessage(content=f"❌ Unknown tool: {tool_name}")]}
            else:
                await db.resolve_pending_action(pending["id"], "declined")
                return {"messages": [AIMessage(content="❌ Action cancelled. No changes were made.")]}


        # ─── Normal flow: LLM decides what action to take ────────────
        # Pre-fetch real tasks from the project mentioned by the user
        # This prevents the LLM from hallucinating task IDs
        task_context = ""
        try:
            user_text = next((m.content for m in reversed(state["messages"])
                              if isinstance(m, HumanMessage)), "")
            from app.tools.query_tools import _resolve_project_id as _rp
            from app.zoho.client import ZohoClient
            from app.tools.query_tools import set_current_user
            set_current_user(state["user_id"])
            # Try to find a project name in the user message
            project_names = {"sky secue": "444530000000070004",
                             "interviews": "444530000000068834",
                             "protein": "444530000000070081"}
            found_pid = None
            for pname, pid in project_names.items():
                if pname.lower() in user_text.lower():
                    found_pid = pid
                    break
            if found_pid:
                c = ZohoClient(state["user_id"])
                tasks = await c.list_tasks(found_pid)
                if tasks:
                    task_lines = [
                        f"  - {t.get('name','?')} (ID: {t.get('id_string', t.get('id','?'))}) Status: {t.get('status',{}).get('name','?') if isinstance(t.get('status'), dict) else '?'}"
                        for t in tasks[:10]
                    ]
                    task_context = f"\n\nREAL TASKS in this project (use these EXACT IDs):\n" + "\n".join(task_lines)
        except Exception:
            pass

        sys = SystemMessage(content=f"""You are a Zoho Projects AI assistant (Action Agent).
You handle WRITE operations using: create_task, update_task, delete_task.

CRITICAL RULES:
1. ONLY use task IDs from REAL TASKS listed below. NEVER invent task IDs.
2. If the user says "update task" without specifying which task, ask them to clarify which task.
3. Known project IDs: interviews=444530000000068834, protein=444530000000070081, sky secue=444530000000070004
4. Call the tool with real data — confirmation will be shown to the user.
{task_context}

CONTEXT: {ctx}
CHAT HISTORY: {history}
LONG-TERM MEMORY: {long_term}""")

        msgs = [sys] + state["messages"]
        resp = await self.action_llm.ainvoke(msgs)

        if resp.tool_calls:
            for tc in resp.tool_calls:
                await db.store_pending_action(
                    session_id=state["session_id"],
                    user_id=state["user_id"],
                    action_type=tc["name"].replace("_task", ""),
                    tool_name=tc["name"],
                    description=f"{tc['name']}: {json.dumps(tc['args'])}",
                    parameters=tc["args"],
                )
            return {"messages": [AIMessage(content=self._format_hil(resp.tool_calls))]}

        return {"messages": [resp]}

    # ─── Force Respond Node ──────────────────────────────────

    async def _force_respond(self, state: GraphState) -> dict:
        """Return tool data directly — do NOT re-pass through LLM as it halluccinates."""
        tool_data = [m.content for m in state["messages"] if isinstance(m, ToolMessage) and m.content]

        if tool_data:
            # Return tool results directly — already formatted by the tools
            combined = "\n\n".join(tool_data)
            return {"messages": [AIMessage(content=combined)]}

        # No tool data — use LLM to generate a graceful error message
        user_msg = next((m.content for m in state["messages"] if isinstance(m, HumanMessage)), "")
        resp = await self.plain_llm.ainvoke([
            SystemMessage(content="Tell the user you couldn't retrieve the requested data. Be brief and helpful."),
            HumanMessage(content=user_msg)
        ])
        return {"messages": [resp]}

    # ─── Edge Conditions ─────────────────────────────────────

    def _has_tool_calls(self, state: GraphState) -> str:
        last = state["messages"][-1] if state["messages"] else None
        if last and isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "tools"
        return "done"

    def _after_tools(self, state: GraphState) -> str:
        if state.get("tool_rounds", 0) >= self.MAX_TOOL_ROUNDS:
            return "stop"
        # If ANY tool returned substantial data, go straight to force_respond
        # This prevents the LLM from looping after getting valid results
        for msg in reversed(state["messages"]):
            if isinstance(msg, ToolMessage) and msg.content and len(msg.content) > 100:
                return "stop"
        return state["agent_type"]

    def _format_hil(self, tool_calls: list) -> str:
        parts = []
        for tc in tool_calls:
            action = tc["name"].replace("_", " ").title()
            parts.append(f"🔔 **Action: {action}**\n")
            for k, v in tc["args"].items():
                if v is not None:
                    parts.append(f"- **{k.replace('_', ' ').title()}:** {v}")
            parts.append("\n👉 **Do you want me to proceed? (Yes/No)**")
        return "\n".join(parts)

    # ─── Main Entry Point ────────────────────────────────────

    async def process_message(self, user_id: str, session_id: str, message: str) -> dict:
        """Process a user message through the full LangGraph pipeline."""
        set_current_user(user_id)
        await db.create_session(session_id, user_id)

        # Build initial state
        initial = {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id,
            "session_id": session_id,
            "agent_type": "",
            "tool_rounds": 0,
        }

        # Run the graph
        result = await self.graph.ainvoke(initial, config={"recursion_limit": 30})

        # Extract final response
        final = self._extract_response(result.get("messages", []))

        # Save to short-term memory
        memory = MemoryStore(user_id, session_id)
        await memory.add_message("user", message)
        await memory.add_message("assistant", final, {"agent": result.get("agent_type", "")})

        # Auto-extract long-term memory
        await self._save_long_term(memory, message, final)

        # Check for pending HIL action
        pending = await db.get_pending_action(session_id)
        pending_data = None
        if pending:
            pending_data = {
                "action_type": pending["action_type"],
                "tool_name": pending["tool_name"],
                "description": pending["description"],
                "parameters": pending["parameters"],
            }

        return {
            "message": final,
            "agent_used": result.get("agent_type", "unknown"),
            "pending_action": pending_data,
        }

    def _extract_response(self, messages: list) -> str:
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

    async def _handle_groq_tool_error(self, err_str: str, user_id: str) -> str | None:
        """When Groq generates tool calls in wrong XML format, parse and execute directly.
        Returns the tool result, or None if parsing fails.
        """
        try:
            import re as _re
            # Extract failed_generation from Groq error
            fg_match = _re.search(r"'failed_generation':\s*'([^']+)'", err_str)
            if not fg_match:
                # Try double-quote version
                fg_match = _re.search(r'"failed_generation":\s*"([^"]+)"', err_str)
            if not fg_match:
                return None

            fg = fg_match.group(1)
            # Parse: <function=tool_name>{"arg": "val"}
            fn_match = _re.search(r'<function=(\w+)>(\{.*?\})', fg)
            if not fn_match:
                return None

            tool_name = fn_match.group(1)
            args = json.loads(fn_match.group(2))

            from app.tools.query_tools import set_current_user
            set_current_user(user_id)

            tool_fn = TOOL_MAP.get(tool_name)
            if tool_fn:
                result = await tool_fn.ainvoke(args)
                return result
        except Exception:
            pass
        return None

    async def _save_long_term(self, memory: MemoryStore, user_msg: str, response: str):
        """Auto-extract rich context into long-term memory after every interaction."""
        msg_lower = user_msg.lower()
        resp_lower = response.lower()

        # ── Save the last topic (always — for 'what was I talking about?') ──
        topic = user_msg[:200]
        await memory.store_interaction("last_topic", topic)
        await memory.store_interaction("last_response_preview", response[:200])

        # ── Save project context from project listing ──
        if "Your Projects:" in response or "your projects" in resp_lower:
            pids = re.findall(r'ID:\s*`?(\d+)`?', response)
            pnames = re.findall(r'\*\*([^*]+)\*\*\s*\(ID:', response)
            if pids and pnames:
                await memory.update_project_context(pids[0], pnames[0])
                await memory.store_interaction(
                    "last_viewed_projects",
                    json.dumps([{"id": pid, "name": pn} for pid, pn in zip(pids, pnames)])
                )

        # ── Save project the user was discussing ──
        project_map = {"interviews": "444530000000068834",
                       "protein": "444530000000070081",
                       "sky secue": "444530000000070004"}
        for pname, pid in project_map.items():
            if pname in msg_lower or pname in resp_lower:
                await memory.update_project_context(pid, pname)
                await memory.store_interaction("last_project_discussed", pname)
                break

        # ── Save task listing context ──
        if "tasks" in resp_lower and any(kw in msg_lower for kw in ["list", "show", "tasks", "what"]):
            # Grab first task name from response
            task_names = re.findall(r'\d+\.\s+\*{0,2}([^\n*]+?)\*{0,2}\s*(?:\(|\[|ID|Status)', response)
            if task_names:
                await memory.store_interaction("last_tasks_viewed", ", ".join(task_names[:5]))

        # ── Save write actions ──
        if any(kw in resp_lower for kw in ["task created", "task updated", "task deleted", "successfully"]):
            await memory.store_interaction("last_action", f"{user_msg[:100]} → {response[:150]}")

        # ── Save explicit preferences ──
        if any(w in msg_lower for w in ["always", "prefer", "default", "usually", "i like"]):
            await memory.store_preference("user_preference", user_msg)


# ─── Global Instance ─────────────────────────────────────────

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
