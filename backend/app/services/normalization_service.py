class NormalizationService:
    """
    Normalizes natural-language variations into backend-supported strict enums
    before Pydantic validation occurs.
    """

    def normalize_priority(self, val: str) -> str:
        if not val:
            return val

        v = str(val).lower().strip()

        # Medium mappings
        if v in ["normal", "medium priority", "moderate", "standard"]:
            return "Medium"
        # High mappings
        if v in ["urgent", "critical", "high priority", "asap", "immediate"]:
            return "High"
        # Low mappings
        if v in ["low priority", "minor", "trivial"]:
            return "Low"

        # Standardize capitalization if it matches exact values loosely
        if v == "low":
            return "Low"
        if v == "medium":
            return "Medium"
        if v == "high":
            return "High"

        return val

    def normalize_status(self, val: str) -> str:
        if not val:
            return val

        v = str(val).lower().strip()

        # Closed mappings
        if v in ["done", "finished", "completed", "resolved"]:
            return "Closed"
        # Open mappings
        if v in ["working", "started", "in progress", "todo", "new"]:
            return "Open"

        if v == "open":
            return "Open"
        if v == "closed":
            return "Closed"

        return val

    def normalize_args(self, raw_args: dict) -> dict:
        """Process all arguments in a dict and normalize known fields."""
        args = raw_args.copy()

        if "priority" in args and args["priority"]:
            args["priority"] = self.normalize_priority(args["priority"])

        if "status" in args and args["status"]:
            args["status"] = self.normalize_status(args["status"])

        return args


normalizer = NormalizationService()
