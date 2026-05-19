from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple


class BaseExecutor(ABC):
    @abstractmethod
    async def validate(
        self, user_id: str, raw_args: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Validate input parameters and resolve entities."""

    @abstractmethod
    async def execute(self, user_id: str, params: Dict[str, Any]) -> str:
        """Execute the actual API mutation."""

    @abstractmethod
    def format_description(self, resolved_args: Dict[str, Any]) -> str:
        """Format the Human-in-the-Loop description string."""
