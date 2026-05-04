import json
import random
from config.settings import Settings
from src.nlp.parser import NLPParser
from src.nlp.responder import RuleBasedResponder
from src.session.transcript import Transcript, Turn


class SessionManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.parser = NLPParser(settings)
        self.responder = RuleBasedResponder(settings)
        self.transcript = Transcript()
        self._active = False
        self._turn_count = 0
        self._initial_question: str = ""

    def start(self, scenario_id: str | None = None) -> None:
        self._active = True
        self.transcript.start()

        if scenario_id:
            scenario = self._load_scenario(scenario_id)
            self._initial_question = scenario["opening"]
            self.responder.set_scenario(scenario)
        else:
            with open(self.settings.QUESTIONS_FILE, encoding="utf-8") as f:
                questions = json.load(f)
            self._initial_question = random.choice(questions)["text"]

    def _load_scenario(self, scenario_id: str) -> dict:
        path = self.settings.SCENARIOS_DIR / f"{scenario_id}.json"
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def is_active(self) -> bool:
        return self._active and self._turn_count < self.settings.MAX_TURNS

    def get_initial_question(self) -> str:
        return self._initial_question

    def record_turn(self, question: str, response: str) -> None:
        self.transcript.add_turn(
            Turn(question=question, response=response, turn_number=self._turn_count)
        )
        self._turn_count += 1

    def generate_follow_up(self, response_text: str) -> str | None:
        parsed = self.parser.parse(response_text)
        return self.responder.generate_follow_up(parsed)

    def end(self) -> Transcript:
        self._active = False
        self.transcript.end()
        return self.transcript
