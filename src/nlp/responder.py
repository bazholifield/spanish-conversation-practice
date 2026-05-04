import json
import random
from config.settings import Settings
from src.nlp.parser import ParsedResponse


class RuleBasedResponder:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._patterns = None
        self._used: set[str] = set()

    @property
    def patterns(self) -> dict:
        if self._patterns is None:
            with open(self.settings.PATTERNS_FILE, encoding="utf-8") as f:
                self._patterns = json.load(f)
        return self._patterns

    def generate_follow_up(self, parsed: ParsedResponse) -> str | None:
        # 1. Keyword match against pattern triggers
        for pattern in self.patterns["patterns"]:
            triggers = set(pattern["triggers"]["keywords"])
            if triggers & set(parsed.keywords):
                candidate = self._pick(pattern["follow_ups"])
                if candidate:
                    return candidate

        # 2. Topic-label match (broader, catches lemma-matched topics)
        for pattern in self.patterns["patterns"]:
            if pattern["id"] in parsed.topics:
                candidate = self._pick(pattern["follow_ups"])
                if candidate:
                    return candidate

        # 3. Keep probing with open-ended questions until keywords emerge
        return self._pick(self.patterns["fallbacks"])

    def _pick(self, options: list[str]) -> str | None:
        available = [o for o in options if o not in self._used]
        if not available:
            return None
        chosen = random.choice(available)
        self._used.add(chosen)
        return chosen
