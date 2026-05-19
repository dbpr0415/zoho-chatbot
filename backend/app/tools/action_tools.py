"""
Action tools — 3 write tools for the Action Agent.
Now uses Entity-Extraction-Only schemas.
"""

from langchain_core.tools import tool
from typing import Optional

def _get_user_id() -> str:
    """Always reads the live _current_user_id from the query_tools module."""
    import app.tools.query_tools as qt
    return qt._current_user_id


@tool
async def create_task(project_name: str, task_name: str, description: Optional[str] = None,
                      assignee_name: Optional[str] = None, due_date: Optional[str] = None,
                      priority: Optional[str] = None) -> str:
    """Create a new task in a given project.

    Args:
        project_name: Natural language name of the project (e.g. 'interviews', 'sky secure')
        task_name: Name/title of the new task
        description: Optional task description
        assignee_name: Optional natural language name of the team member to assign
        due_date: Optional due date in MM-DD-YYYY format
        priority: Optional priority — Low, Medium, High
    """
    # SafeExecutorService intercepts this mutation.
    return ""


@tool
async def update_task(project_name: str, task_name: str, new_name: Optional[str] = None,
                      status: Optional[str] = None, assignee_name: Optional[str] = None,
                      due_date: Optional[str] = None, priority: Optional[str] = None) -> str:
    """Update an existing task's properties.

    Args:
        project_name: Natural language name of the project
        task_name: Natural language name of the task
        new_name: Optional new name for the task
        status: New status — 'Open' or 'Closed'
        assignee_name: New assignee name
        due_date: New due date in MM-DD-YYYY format
        priority: New priority — Low, Medium, High
    """
    # SafeExecutorService intercepts this mutation.
    return ""


@tool
async def delete_task(project_name: str, task_name: str) -> str:
    """Delete a task from a project. This action is IRREVERSIBLE.

    Args:
        project_name: Natural language name of the project
        task_name: Natural language name of the task
    """
    # SafeExecutorService intercepts this mutation.
    return ""


ACTION_TOOLS = [create_task, update_task, delete_task]
