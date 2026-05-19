from typing import Tuple, Dict, Any
from app.executors.base import BaseExecutor
from app.tools.middleware import validate_create_task
from app.zoho.client import ZohoClient

class CreateTaskExecutor(BaseExecutor):
    async def validate(self, user_id: str, raw_args: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        return await validate_create_task(user_id, raw_args)

    async def execute(self, user_id: str, params: Dict[str, Any]) -> str:
        client = ZohoClient(user_id)
        # Pop UI metadata before hitting Zoho
        params.pop("_real_project_name", None)
        await client.create_task(**params)
        return "✅ Task created successfully."

    def format_description(self, resolved_args: Dict[str, Any]) -> str:
        return f"Create Task '{resolved_args.get('name', '')}' in Project '{resolved_args.get('_real_project_name', '')}'"
