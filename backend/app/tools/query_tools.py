from langchain_core.tools import tool
from typing import Optional

_current_user_id: str = ""


def set_current_user(user_id: str):
    global _current_user_id
    _current_user_id = user_id


from app.utils.matcher import EntityResolver
resolver = EntityResolver(confidence_threshold=75)

async def _resolve_project_id(project_id_or_name: str) -> str:
    """Auto-resolve project name using EntityResolver."""
    if project_id_or_name.isdigit():
        return project_id_or_name
    from app.zoho.client import ZohoClient
    client = ZohoClient(_current_user_id)
    projects = await client.list_projects()
    
    pid, _, _, _ = resolver.resolve_entity(project_id_or_name, projects)
    if pid:
        return pid
    return project_id_or_name  # fallback

async def _resolve_task_id(project_id: str, task_ref: str) -> tuple[str, str]:
    """Resolve a task reference using EntityResolver."""
    if task_ref.isdigit():
        return project_id, task_ref

    from app.zoho.client import ZohoClient
    client = ZohoClient(_current_user_id)
    tasks = await client.list_tasks(project_id)

    if not tasks:
        return project_id, task_ref

    # Index references fallback
    ref = task_ref.lower().strip()
    index_map = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "last": -1}
    for word, idx in index_map.items():
        if word in ref:
            try:
                t = tasks[idx]
                return project_id, t.get("id_string", str(t.get("id", task_ref)))
            except IndexError:
                pass

    tid, _, _, _ = resolver.resolve_entity(task_ref, tasks)
    if tid:
        return project_id, tid

    return project_id, task_ref  # fallback


@tool
async def list_projects() -> str:
    """Fetch all projects for the authenticated user. Returns project names, IDs, status, and task counts."""
    from app.zoho.client import ZohoClient
    client = ZohoClient(_current_user_id)
    projects = await client.list_projects()

    if not projects:
        return "📋 You don't have any projects yet."

    lines = ["📋 **Your Projects:**\n"]
    for i, p in enumerate(projects, 1):
        name = p.get("name", "Unnamed")
        pid = p.get("id_string", p.get("id", "N/A"))
        status = p.get("status", "active")
        tc = p.get("task_count", {})
        open_t = tc.get("open", 0) if isinstance(tc, dict) else 0
        lines.append(f"{i}. **{name}** (ID: `{pid}`)\n   Status: {status} | Open Tasks: {open_t}\n")
    return "\n".join(lines)


@tool
async def list_tasks(project_id: str, status: Optional[str] = None, assignee: Optional[str] = None) -> str:
    """List tasks for a project with optional filters.

    Args:
        project_id: Numeric project ID or project name (auto-resolved)
        status: Optional filter — 'open', 'closed', or 'all'
        assignee: Optional filter — assignee name
    """
    from app.zoho.client import ZohoClient
    pid = await _resolve_project_id(project_id)
    client = ZohoClient(_current_user_id)
    tasks = await client.list_tasks(pid, status=status, assignee=assignee)

    if not tasks:
        return "📝 No tasks found for this project."

    lines = ["📝 **Tasks:**\n"]
    for i, t in enumerate(tasks, 1):
        name = t.get("name", "Unnamed")
        tid = t.get("id_string", t.get("id", "N/A"))
        s = t.get("status", {})
        st = s.get("name", "Unknown") if isinstance(s, dict) else str(s)
        pri = t.get("priority", "None")
        due = t.get("end_date", "No due date")
        det = t.get("details", {})
        owners = det.get("owners", []) if isinstance(det, dict) else []
        own = ", ".join([o.get("name", "?") for o in owners]) if owners else "Unassigned"
        lines.append(f"{i}. **{name}** (ID: `{tid}`)\n   Status: {st} | Priority: {pri} | Assignee: {own} | Due: {due}\n")
    return "\n".join(lines)


@tool
async def get_task_details(project_id: str, task_id: str) -> str:
    """Fetch full details of a single task by its ID or name.

    Args:
        project_id: Numeric project ID or project name (auto-resolved)
        task_id: Task ID (numeric), task name, or index like 'first', '1', 'go out'
    """
    from app.zoho.client import ZohoClient
    pid = await _resolve_project_id(project_id)
    pid, tid = await _resolve_task_id(pid, task_id)
    client = ZohoClient(_current_user_id)
    task = await client.get_task_details(pid, tid)

    if not task:
        return f"❌ Task `{task_id}` not found in project `{project_id}`."

    name = task.get("name", "Unnamed")
    s = task.get("status", {})
    st = s.get("name", "Unknown") if isinstance(s, dict) else "Unknown"
    pri = task.get("priority", "None")
    due = task.get("end_date", "No due date")
    desc = task.get("description", "No description")
    pct = task.get("percent_complete", "0")
    det = task.get("details", {})
    owners = det.get("owners", []) if isinstance(det, dict) else []
    own = ", ".join([o.get("name", "?") for o in owners]) if owners else "Unassigned"

    return (
        f"📌 **Task: {name}**\n\n"
        f"- **ID:** `{task.get('id_string', 'N/A')}`\n"
        f"- **Status:** {st}\n"
        f"- **Priority:** {pri}\n"
        f"- **Assignee:** {own}\n"
        f"- **Due Date:** {due}\n"
        f"- **Progress:** {pct}%\n"
        f"- **Description:** {desc}\n"
    )


@tool
async def list_project_members(project_id: str) -> str:
    """Get all members of a project with their roles.

    Args:
        project_id: Numeric project ID or project name (auto-resolved)
    """
    from app.zoho.client import ZohoClient
    pid = await _resolve_project_id(project_id)
    client = ZohoClient(_current_user_id)
    members = await client.list_project_members(pid)

    if not members:
        return "👥 No members found for this project."

    lines = ["👥 **Project Members:**\n"]
    for i, m in enumerate(members, 1):
        lines.append(f"{i}. **{m.get('name','?')}** — {m.get('role','Member')}\n   Email: {m.get('email','N/A')}\n")
    return "\n".join(lines)


@tool
async def get_task_utilisation(project_id: str) -> str:
    """Summarise task load per member across a project. Shows who has the most tasks.

    Args:
        project_id: Project ID or name ('interviews', 'sky secue', 'protein'). Use 'all' to check across all projects.
    """
    from app.zoho.client import ZohoClient
    client = ZohoClient(_current_user_id)

    # If 'all' or vague, aggregate across all projects
    if project_id.lower() in ("all", "", "any", "every", "projects"):
        projects = await client.list_projects()
        if not projects:
            return "📊 No projects found."
        all_tasks = []
        project_labels = {}
        for p in projects:
            pid = p.get("id_string", str(p.get("id", "")))
            pname = p.get("name", pid)
            project_labels[pid] = pname
            tasks = await client.list_tasks(pid)
            for t in tasks:
                t["_project"] = pname
            all_tasks.extend(tasks)
        tasks_to_analyse = all_tasks
        header = "📊 **Task Utilisation (All Projects):**\n"
    else:
        pid = await _resolve_project_id(project_id)
        tasks_to_analyse = await client.list_tasks(pid)
        header = f"📊 **Task Utilisation — Project `{project_id}`:**\n"

    if not tasks_to_analyse:
        return "📊 No tasks found to analyse."

    stats = {}
    for t in tasks_to_analyse:
        det = t.get("details", {})
        owners = det.get("owners", []) if isinstance(det, dict) else []
        s = t.get("status", {})
        is_done = "closed" in (s.get("name", "") if isinstance(s, dict) else s).lower() or \
                  "completed" in (s.get("name", "") if isinstance(s, dict) else s).lower()
        # Handle unassigned tasks
        if not owners:
            owners = [{"name": "Unassigned"}]
        for o in owners:
            n = o.get("name", "Unassigned")
            if n not in stats:
                stats[n] = {"total": 0, "open": 0, "done": 0}
            stats[n]["total"] += 1
            stats[n]["done" if is_done else "open"] += 1

    ranked = sorted(stats.items(), key=lambda x: x[1]["total"], reverse=True)
    lines = [header, "", "| Member | Total | Open | Done |", "|--------|-------|------|------|"]
    for name, s in ranked:
        lines.append(f"| {name} | {s['total']} | {s['open']} | {s['done']} |")

    if ranked and ranked[0][1]["total"] > 0:
        top = ranked[0]
        lines.append(f"\n🏆 **Most tasks:** {top[0]} with **{top[1]['total']} task(s)** ({top[1]['open']} open, {top[1]['done']} done)")
    return "\n".join(lines)


QUERY_TOOLS = [list_projects, list_tasks, get_task_details, list_project_members, get_task_utilisation]
