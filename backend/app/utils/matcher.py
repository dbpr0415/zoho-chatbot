import time
from thefuzz import process, fuzz
from typing import List, Dict, Optional, Tuple, Any

class EntityResolutionService:
    def __init__(self):
        self.auto_resolve_threshold = 90
        self.clarify_threshold = 75
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes TTL

    def _get_cache(self, cache_key: str) -> Optional[Any]:
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return data
        return None

    def _set_cache(self, cache_key: str, data: Any):
        self._cache[cache_key] = (data, time.time())

    def resolve_entity(self, query: str, entities: List[Dict], name_key: str = "name", id_key: str = "id_string") -> Tuple[Optional[str], Optional[str], int, str]:
        """
        Dynamically resolves an entity using exact, normalized, and fuzzy matching.
        Returns: (resolved_id, resolved_name, confidence_score, status_message)
        """
        if not query or not entities:
            return None, None, 0, "Empty query or entity list."

        query_lower = query.lower().strip()
        
        # 1. Exact Match
        for entity in entities:
            name = entity.get(name_key, "")
            if name == query:
                r_id = entity.get(id_key, str(entity.get("id", "")))
                return r_id, name, 100, "exact"

        # 2. Lowercase Normalized Match
        for entity in entities:
            name = entity.get(name_key, "")
            if name.lower().strip() == query_lower:
                r_id = entity.get(id_key, str(entity.get("id", "")))
                return r_id, name, 100, "normalized"

        # 3. Fuzzy Match
        entity_map = {e.get(name_key, ""): e for e in entities if e.get(name_key)}
        choices = list(entity_map.keys())
        
        if not choices:
            return None, None, 0, "No valid names to match against."

        match = process.extractOne(query_lower, choices, scorer=fuzz.token_sort_ratio)
        
        if not match:
            return None, None, 0, "rejected"

        matched_name, score = match[0], match[1]
        matched_entity = entity_map[matched_name]
        r_id = matched_entity.get(id_key, str(matched_entity.get("id", "")))

        if score >= self.auto_resolve_threshold:
            return r_id, matched_name, score, "auto_resolved"
        elif score >= self.clarify_threshold:
            return None, matched_name, score, "clarification_needed"
        else:
            return None, None, score, "rejected"

resolver = EntityResolutionService()
