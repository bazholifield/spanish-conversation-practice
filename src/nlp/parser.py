import spacy
from dataclasses import dataclass
from config.settings import Settings


@dataclass
class ParsedResponse:
    raw_text: str
    tokens: list[dict]      # {text, lemma, pos, is_stop}
    keywords: list[str]     # content-word lemmas (nouns, verbs, adjectives)
    verbs: list[dict]       # {text, lemma, morph}
    entities: list[dict]    # {text, label}


class NLPParser:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._nlp = None

    @property
    def nlp(self):
        if self._nlp is None:
            self._nlp = spacy.load(self.settings.SPACY_MODEL)
        return self._nlp

    def parse(self, text: str) -> ParsedResponse:
        doc = self.nlp(text.lower())

        tokens = [
            {"text": t.text, "lemma": t.lemma_, "pos": t.pos_, "is_stop": t.is_stop}
            for t in doc
        ]

        keywords = [
            t.lemma_ for t in doc
            if t.pos_ in ("NOUN", "VERB", "ADJ", "PROPN") and not t.is_stop and t.is_alpha
        ]

        verbs = [
            {"text": t.text, "lemma": t.lemma_, "morph": str(t.morph)}
            for t in doc if t.pos_ == "VERB"
        ]

        entities = [
            {"text": ent.text, "label": ent.label_}
            for ent in doc.ents
        ]

        return ParsedResponse(
            raw_text=text,
            tokens=tokens,
            keywords=keywords,
            verbs=verbs,
            entities=entities,
        )
