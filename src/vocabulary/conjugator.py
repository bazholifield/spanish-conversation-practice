import mlconjug3


PRONOUNS = ["yo", "tú", "él/ella", "nosotros", "vosotros", "ellos/ellas"]

TENSES_TO_SHOW = [
    ("Presente",    "Indicativo presente"),
    ("Pretérito",   "Indicativo pretérito perfecto simple"),
    ("Imperfecto",  "Indicativo pretérito imperfecto"),
    ("Futuro",      "Indicativo futuro"),
]

INFINITIVE_ENDINGS = ("ar", "er", "ir", "arse", "erse", "irse")


class SpanishConjugator:
    def __init__(self):
        self._conjugator = mlconjug3.Conjugator(language="es")

    def conjugate(self, infinitive: str) -> dict | None:
        try:
            verb = self._conjugator.conjugate(infinitive)
            if verb is None:
                return None
            return self._format(verb)
        except Exception:
            return None

    def looks_like_infinitive(self, word: str) -> bool:
        return word.endswith(INFINITIVE_ENDINGS)

    def _format(self, verb) -> dict | None:
        info = getattr(verb, "conjug_info", None)
        if not isinstance(info, dict):
            return None

        result = {}
        for display_name, tense_key in TENSES_TO_SHOW:
            forms = self._find_tense(info, tense_key)
            if forms:
                result[display_name] = dict(zip(PRONOUNS, forms.values()))
        return result or None

    @staticmethod
    def _find_tense(info: dict, tense_key: str) -> dict | None:
        """mlconjug3 nests tenses under their mood and ships each one twice,
        distinguished only by the capitalisation of the tense name. The
        lowercase spelling holds the real paradigm; the capitalised twin holds
        corrupt output ('Indicativo Futuro' -> {'': 'quiremos'}, 'Indicativo
        Pretérito imperfecto' -> {'1s': 'qu-'}). So match the name
        case-insensitively, then take the variant whose tense is lowercase.
        """
        wanted = tense_key.lower()
        fallback = None
        for tenses in info.values():
            if not isinstance(tenses, dict):
                continue
            for name, forms in tenses.items():
                if name.lower() != wanted or not isinstance(forms, dict):
                    continue
                usable = {p: f for p, f in forms.items() if p and f}
                if not usable:
                    continue
                _, _, tense = name.partition(" ")
                if tense and tense.islower():
                    return usable
                fallback = fallback or usable
        return fallback
