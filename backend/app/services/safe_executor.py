import logging
from typing import Any, Dict, Tuple

from app.executors.create_executor import CreateTaskExecutor
from app.executors.delete_executor import DeleteTaskExecutor
from app.executors.update_executor import UpdateTaskExecutor
from app.services.missing_field_resolver import MissingFieldResolver

logger = logging.getLogger("execution_layer")

EXECUTOR_MAP = {
    "create_task": CreateTaskExecutor(),
    "update_task": UpdateTaskExecutor(),
    "delete_task": DeleteTaskExecutor(),
}


class SafeExecutorService:
    @staticmethod
    def get_executor(tool_name: str):
        return EXECUTOR_MAP.get(tool_name)

    @staticmethod
    async def validate_and_format(
        user_id: str, tool_name: str, raw_args: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any], str]:
        """
        Orchestrates validation and formats the HIL description.
        Returns: (is_valid, error_msg, resolved_args, hil_description)
        """
        # 1. Conversational Clarification Layer (Check for missing fields)
        has_missing, clarification_msg = MissingFieldResolver.check_missing_fields(
            tool_name, raw_args
        )
        if has_missing:
            return False, clarification_msg, {}, ""

        # 2. Execution and Pydantic validation layer
        executor = SafeExecutorService.get_executor(tool_name)
        if not executor:
            return False, f"❌ Unknown tool: {tool_name}", {}, ""

        is_valid, msg, resolved_args = await executor.validate(user_id, raw_args)
        if not is_valid:
            logger.warning(f"Validation failed for {tool_name}: {msg}")
            return False, msg, {}, ""

        desc = executor.format_description(resolved_args)
        return True, "", resolved_args, desc

    @staticmethod
    async def execute_tool(user_id: str, tool_name: str, params: Dict[str, Any]) -> str:
        """
        Orchestrates the actual execution of the mutation, with centralized error handling.
        """
        executor = SafeExecutorService.get_executor(tool_name)
        if not executor:
            raise ValueError(f"Unknown tool: {tool_name}")

        try:
            result = await executor.execute(user_id, params)

            logger.info(f"Successfully executed {tool_name} for user {user_id}")
            return result
        except Exception as e:
            logger.error(f"Execution failed for {tool_name}: {str(e)}")
            raise Exception(f"Action failed during execution: {str(e)}")
