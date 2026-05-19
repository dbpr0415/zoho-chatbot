from typing import Any, Dict, Tuple


class MissingFieldResolver:
    """
    Checks if a tool payload has all conceptually required fields BEFORE
    it ever reaches Pydantic validation. If missing, it generates a natural
    language clarification question for the user.
    """

    REQUIRED_FIELDS = {
        "create_task": ["project_name", "task_name"],
        "update_task": ["project_name", "task_name"],
        "delete_task": ["project_name", "task_name"],
    }

    @staticmethod
    def check_missing_fields(
        tool_name: str, raw_args: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Returns: (has_missing_fields, clarification_question_string)
        """
        required = MissingFieldResolver.REQUIRED_FIELDS.get(tool_name, [])
        missing = []
        for field in required:
            if not raw_args.get(field) or str(raw_args.get(field)).strip() == "":
                missing.append(field)

        if missing:
            if "project_name" in missing and "task_name" in missing:
                return (
                    True,
                    "I need both the project name and the task name. Could you provide them?",
                )
            elif "project_name" in missing:
                return True, "Which project does this task belong to?"
            elif "task_name" in missing:
                return True, "What should the task name be?"

        return False, ""
