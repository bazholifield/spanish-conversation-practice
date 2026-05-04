from pathlib import Path


class Settings:
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / "data"
    TRANSCRIPT_DIR = BASE_DIR / "transcripts"
    QUESTIONS_FILE = DATA_DIR / "questions.json"
    PATTERNS_FILE = DATA_DIR / "patterns.json"
    SCENARIOS_DIR = DATA_DIR / "scenarios"

    # Speech — swap INPUT_MODE to "text" to skip mic during development
    STT_LANGUAGE = "es-ES"
    TTS_LANGUAGE = "es"
    TTS_SLOW = False
    INPUT_MODE = "text"  # "speech" | "text"

    # Session
    EXIT_COMMANDS = {"salir", "terminar", "exit", "quit", "stop", "adios", "adiós"}
    MAX_TURNS = 30
    FALLBACK_RESPONSES_BEFORE_END = 3

    # NLP
    SPACY_MODEL = "es_core_news_sm"
