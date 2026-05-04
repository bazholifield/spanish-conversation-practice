from deep_translator import GoogleTranslator
from config.settings import Settings


class VocabularyLookup:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._cache: dict[str, dict] = {}
        self._translator = GoogleTranslator(source="es", target="en")

    def lookup(self, word: str) -> dict:
        if word in self._cache:
            return self._cache[word]
        result = {"word": word, "translation": self._translate(word), "conjugation": None}
        self._cache[word] = result
        return result

    def lookup_batch(self, words: list[str]) -> dict[str, dict]:
        if not words:
            return {}

        cached = {w: self._cache[w] for w in words if w and w in self._cache}
        to_fetch = [w for w in words if w and w not in self._cache]

        if to_fetch:
            try:
                translations = self._translator.translate_batch(to_fetch)
            except Exception:
                translations = [""] * len(to_fetch)

            for word, trans in zip(to_fetch, translations):
                data = {"word": word, "translation": trans or "", "conjugation": None}
                self._cache[word] = data
                cached[word] = data

        return cached

    def _translate(self, word: str) -> str:
        try:
            return self._translator.translate(word) or ""
        except Exception:
            return ""
