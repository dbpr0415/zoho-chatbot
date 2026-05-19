from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any

class BaseExecutor(ABC):
    @abstractmethod
    async def validate(self, user_id: str, raw_args: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """Validate input parameters and resolve entities."""
        pass

    @abstractmethod
    async def execute(self, user_id: str, params: Dict[str, Any]) -> str:
        """Execute the actual API mutation."""
        pass

    @abstractmethod
    def format_description(self, resolved_args: Dict[str, Any]) -> str:
        """Format the Human-in-the-Loop description string."""
        pass
