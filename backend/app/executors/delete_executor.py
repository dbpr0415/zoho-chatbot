from typing import Any, Dict, Tuple

from app.executors.base import BaseExecutor
from app.tools.middleware import validate_delete_task
from app.zoho.client import ZohoClient


class DeleteTaskExecutor(BaseExecutor):
    async def validate(
        self, user_id: str, raw_args: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        return await validate_delete_task(user_id, raw_args)

    async def execute(self, user_id: str, params: Dict[str, Any]) -> str:
        client = ZohoClient(user_id)
        params.pop("_real_project_name", None)
        params.pop("_real_task_name", None)
        await client.delete_task(**params)
        return "🗑️ Task deleted successfully."

    def format_description(self, resolved_args: Dict[str, Any]) -> str:
        return f"Delete Task '{resolved_args.get('_real_task_name', '')}' from Project '{resolved_args.get('_real_project_name', '')}'"
