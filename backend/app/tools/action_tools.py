"""
Action tools — 3 write tools for the Action Agent.
Tools: create_task, update_task, delete_task
All require Human-in-the-Loop (HIL) confirmation before execution.

IMPORTANT: Never import _current_user_id directly — always access via
app.tools.query_tools._current_user_id to get the live value.
"""

from langchain_core.tools import tool
from typing import Optional
from app.tools.query_tools import _resolve_project_id, _resolve_task_id


def _get_user_id() -> str:
    """Always reads the live _current_user_id from the query_tools module."""
    import app.tools.query_tools as qt
    return qt._current_user_id


# ─── Tool 4: create_task ────────────────────────────────────

@tool
async def create_task(project_id: str, name: str, description: Optional[str] = None,
                      assignee: Optional[str] = None, due_date: Optional[str] = None,
                      priority: Optional[str] = None) -> str:
    """Create a new task in a given project.

    Args:
        project_id: Project ID (numeric) or name like 'interviews', 'sky secue', 'protein'
        name: Name/title of the new task
        description: Optional task description
        assignee: Optional — only pass if you have a numeric user ID
        due_date: Optional due date in MM-DD-YYYY format
        priority: Optional priority — Low, Medium, High
    """
    from app.zoho.client import ZohoClient
    pid = await _resolve_project_id(project_id)
    client = ZohoClient(_get_user_id())
    result = await client.create_task(
        project_id=pid, name=name, description=description,
        assignee=assignee, due_date=due_date, priority=priority,
    )
    tid = result.get("id_string", result.get("id", "N/A"))
    tname = result.get("name", name)
    return (
        f"✅ **Task Created Successfully!**\n"
        f"- **Name:** {tname}\n"
        f"- **ID:** `{tid}`\n"
        f"- **Project:** `{pid}`"
    )


# ─── Tool 5: update_task ────────────────────────────────────

@tool
async def update_task(project_id: str, task_id: str, name: Optional[str] = None,
                      status: Optional[str] = None, assignee: Optional[str] = None,
                      due_date: Optional[str] = None, priority: Optional[str] = None) -> str:
    """Update an existing task's properties (status, name, priority, due date).

    Args:
        project_id: Project ID (numeric) or name like 'interviews', 'sky secue', 'protein'
        task_id: Task ID (numeric), task name like 'go out', or index like 'first', '1'
        name: Optional new name for the task
        status: New status — 'open' or 'closed'
        assignee: New assignee (numeric user ID only)
        due_date: New due date in MM-DD-YYYY format
        priority: New priority — Low, Medium, High
    """
    from app.zoho.client import ZohoClient
    user_id = _get_user_id()
    pid = await _resolve_project_id(project_id)
    # Auto-resolve task name/index → actual task ID from the correct project
    pid, tid = await _resolve_task_id(pid, task_id)
    client = ZohoClient(user_id)
    await client.update_task(
        project_id=pid, task_id=tid, name=name,
        status=status, assignee=assignee, due_date=due_date, priority=priority,
    )
    changes = [
        f"**{k.replace('_', ' ').title()}:** {v}"
        for k, v in {"name": name, "status": status, "assignee": assignee,
                     "due_date": due_date, "priority": priority}.items()
        if v
    ]
    return (
        f"✅ **Task Updated Successfully!**\n"
        f"- **Task ID:** `{tid}`\n"
        f"- **Project:** `{pid}`\n- "
        + "\n- ".join(changes)
    )


# ─── Tool 6: delete_task ────────────────────────────────────

@tool
async def delete_task(project_id: str, task_id: str) -> str:
    """Delete a task from a project. This action is IRREVERSIBLE.

    Args:
        project_id: Project ID (numeric) or name like 'interviews', 'sky secue', 'protein'
        task_id: Task ID (numeric), task name like 'go out', or index like 'first', '1'
    """
    from app.zoho.client import ZohoClient
    user_id = _get_user_id()
    pid = await _resolve_project_id(project_id)
    # Auto-resolve task name/index → actual task ID from the correct project
    pid, tid = await _resolve_task_id(pid, task_id)
    client = ZohoClient(user_id)
    await client.delete_task(project_id=pid, task_id=tid)
    return f"🗑️ **Task Deleted!** Task `{tid}` has been permanently removed from project `{pid}`."


# ─── Export ──────────────────────────────────────────────────
ACTION_TOOLS = [create_task, update_task, delete_task]
