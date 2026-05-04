import json
import random
from config.settings import Settings
from src.nlp.parser import ParsedResponse


class RuleBasedResponder:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._patterns = None
        self._used: set[str] = set()
        self._scenario_patterns: list[dict] = []
        self._scenario_fallbacks: list[str] = []

    @property
    def patterns(self) -> dict:
        if self._patterns is None:
            with open(self.settings.PATTERNS_FILE, encoding="utf-8") as f:
                self._patterns = json.load(f)
        return self._patterns

    def set_scenario(self, scenario: dict) -> None:
        self._scenario_patterns = scenario.get("patterns", [])
        self._scenario_fallbacks = scenario.get("fallbacks", [])

    def generate_follow_up(self, parsed: ParsedResponse) -> str | None:
        # 1. Scenario-specific keyword match (highest priority)
        for pattern in self._scenario_patterns:
            triggers = set(pattern["triggers"]["keywords"])
            if triggers & set(parsed.keywords):
                candidate = self._pick(pattern["follow_ups"])
                if candidate:
                    return candidate

        # 2. General keyword match
        for pattern in self.patterns["patterns"]:
            triggers = set(pattern["triggers"]["keywords"])
            if triggers & set(parsed.keywords):
                candidate = self._pick(pattern["follow_ups"])
                if candidate:
                    return candidate

        # 3. General topic-label match
        for pattern in self.patterns["patterns"]:
            if pattern["id"] in parsed.topics:
                candidate = self._pick(pattern["follow_ups"])
                if candidate:
                    return candidate

        # 4. Scenario fallbacks
        candidate = self._pick(self._scenario_fallbacks)
        if candidate:
            return candidate

        # 5. General fallbacks — keep probing until exhausted
        return self._pick(self.patterns["fallbacks"])

    def _pick(self, options: list[str]) -> str | None:
        available = [o for o in options if o not in self._used]
        if not available:
            return None
        chosen = random.choice(available)
        self._used.add(chosen)
        return chosen
