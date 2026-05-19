from typing import Tuple, Dict, Any
from app.executors.base import BaseExecutor
from app.tools.middleware import validate_update_task
from app.zoho.client import ZohoClient

class UpdateTaskExecutor(BaseExecutor):
    async def validate(self, user_id: str, raw_args: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        return await validate_update_task(user_id, raw_args)

    async def execute(self, user_id: str, params: Dict[str, Any]) -> str:
        client = ZohoClient(user_id)
        params.pop("_real_project_name", None)
        params.pop("_real_task_name", None)
        await client.update_task(**params)
        return "✅ Task updated successfully."

    def format_description(self, resolved_args: Dict[str, Any]) -> str:
        return f"Update Task '{resolved_args.get('_real_task_name', '')}' in Project '{resolved_args.get('_real_project_name', '')}'"
