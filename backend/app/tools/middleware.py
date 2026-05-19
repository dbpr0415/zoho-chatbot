import logging
from typing import Optional, Tuple, Dict, Any
from app.utils.matcher import resolver
from app.zoho.client import ZohoClient
from app.schemas.validation import CreateTaskArgs, UpdateTaskArgs, DeleteTaskArgs
from pydantic import ValidationError

logger = logging.getLogger("validation_layer")

async def _resolve_project(client: ZohoClient, project_name: str) -> Tuple[Optional[str], Optional[str], str]:
    projects = await client.list_projects()
    r_id, name, score, status = resolver.resolve_entity(project_name, projects)
    return r_id, name, status

async def _resolve_task(client: ZohoClient, project_id: str, task_name: str) -> Tuple[Optional[str], Optional[str], str]:
    tasks = await client.list_tasks(project_id)
    r_id, name, score, status = resolver.resolve_entity(task_name, tasks)
    return r_id, name, status

async def _resolve_assignee(client: ZohoClient, project_id: str, assignee_name: str) -> Tuple[Optional[str], Optional[str], str]:
    members = await client.list_project_members(project_id)
    r_id, name, score, status = resolver.resolve_entity(assignee_name, members, name_key="name", id_key="id")
    return r_id, name, status

def _handle_resolution_error(entity_type: str, raw_name: str, status: str, matched_name: Optional[str]) -> str:
    if status == "clarification_needed":
        return f"🤔 Did you mean '{matched_name}' for the {entity_type}? Please clarify as I'm only partially confident."
    return f"❌ I couldn't find a {entity_type} matching '{raw_name}'."

async def validate_create_task(user_id: str, raw_args: dict) -> Tuple[bool, str, Dict[str, Any]]:
    try:
        args = CreateTaskArgs(**raw_args)
    except ValidationError as e:
        logger.warning(f"Schema Validation Failed: {e.errors()}")
        return False, f"❌ Validation failed: {e.errors()[0]['msg']}", {}

    client = ZohoClient(user_id)
    
    project_id, real_project_name, p_status = await _resolve_project(client, args.project_name)
    if not project_id:
        return False, _handle_resolution_error("project", args.project_name, p_status, real_project_name), {}
        
    assignee_id = None
    if args.assignee_name:
        assignee_id, a_name, a_status = await _resolve_assignee(client, project_id, args.assignee_name)
        if not assignee_id:
            return False, _handle_resolution_error("team member", args.assignee_name, a_status, a_name), {}

    resolved_args = {
        "project_id": project_id,
        "name": args.task_name,
        "description": args.description,
        "assignee": assignee_id,
        "due_date": args.due_date,
        "priority": args.priority.value if args.priority else None,
        "_real_project_name": real_project_name
    }
    return True, "", resolved_args

async def validate_update_task(user_id: str, raw_args: dict) -> Tuple[bool, str, Dict[str, Any]]:
    try:
        args = UpdateTaskArgs(**raw_args)
    except ValidationError as e:
        return False, f"❌ Validation failed: {e.errors()[0]['msg']}", {}

    client = ZohoClient(user_id)
    
    project_id, real_project_name, p_status = await _resolve_project(client, args.project_name)
    if not project_id:
        return False, _handle_resolution_error("project", args.project_name, p_status, real_project_name), {}

    task_id, real_task_name, t_status = await _resolve_task(client, project_id, args.task_name)
    if not task_id:
        return False, _handle_resolution_error("task", args.task_name, t_status, real_task_name), {}

    assignee_id = None
    if args.assignee_name:
        assignee_id, a_name, a_status = await _resolve_assignee(client, project_id, args.assignee_name)
        if not assignee_id:
            return False, _handle_resolution_error("team member", args.assignee_name, a_status, a_name), {}

    resolved_args = {
        "project_id": project_id,
        "task_id": task_id,
        "name": args.new_name,
        "status": args.status.value if args.status else None,
        "assignee": assignee_id,
        "due_date": args.due_date,
        "priority": args.priority.value if args.priority else None,
        "_real_project_name": real_project_name,
        "_real_task_name": real_task_name
    }
    return True, "", resolved_args

async def validate_delete_task(user_id: str, raw_args: dict) -> Tuple[bool, str, Dict[str, Any]]:
    try:
        args = DeleteTaskArgs(**raw_args)
    except ValidationError as e:
        return False, f"❌ Validation failed: {e.errors()[0]['msg']}", {}

    client = ZohoClient(user_id)
    project_id, real_project_name, p_status = await _resolve_project(client, args.project_name)
    if not project_id:
        return False, _handle_resolution_error("project", args.project_name, p_status, real_project_name), {}

    task_id, real_task_name, t_status = await _resolve_task(client, project_id, args.task_name)
    if not task_id:
        return False, _handle_resolution_error("task", args.task_name, t_status, real_task_name), {}

    resolved_args = {
        "project_id": project_id,
        "task_id": task_id,
        "_real_project_name": real_project_name,
        "_real_task_name": real_task_name
    }
    return True, "", resolved_args
