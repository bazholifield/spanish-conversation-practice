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
        self._consecutive_fallbacks = 0

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
        keywords = set(parsed.keywords)

        # 1. Scenario-specific keyword match (highest priority)
        for pattern in self._scenario_patterns:
            if set(pattern["triggers"]["keywords"]) & keywords:
                candidate = self._pick(pattern["follow_ups"])
                if candidate:
                    self._consecutive_fallbacks = 0
                    return candidate

        # 2. General keyword match
        for pattern in self.patterns["patterns"]:
            if set(pattern["triggers"]["keywords"]) & keywords:
                candidate = self._pick(pattern["follow_ups"])
                if candidate:
                    self._consecutive_fallbacks = 0
                    return candidate

        # 3. Nothing matched, probe with a fallback, but wrap up if the
        #    conversation has drifted off-script too many turns in a row.
        self._consecutive_fallbacks += 1
        if self._consecutive_fallbacks >= self.settings.FALLBACK_RESPONSES_BEFORE_END:
            return None

        return self._pick(self._scenario_fallbacks) or self._pick(self.patterns["fallbacks"])

    def _pick(self, options: list[str]) -> str | None:
        available = [o for o in options if o not in self._used]
        if not available:
            return None
        chosen = random.choice(available)
        self._used.add(chosen)
        return chosen
