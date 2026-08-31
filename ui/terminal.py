from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich import box

from config.settings import Settings
from src.session.transcript import Transcript


class TerminalUI:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.console = Console()
        self._tts = None
        self._stt = None

    @property
    def tts(self):
        if self._tts is None:
            from src.speech.tts import TextToSpeech
            self._tts = TextToSpeech(self.settings)
        return self._tts

    @property
    def stt(self):
        if self._stt is None:
            from src.speech.stt import SpeechToText
            self._stt = SpeechToText(self.settings)
        return self._stt

    def display_welcome(self) -> None:
        mode_label = "🎤 Speech" if self.settings.INPUT_MODE == "speech" else "⌨️  Text"
        self.console.print(Panel(
            "[bold green]¡Bienvenido![/bold green] Spanish Conversation Practice\n\n"
            f"Input mode: [cyan]{mode_label}[/cyan]\n"
            "Type [bold red]'salir'[/bold red] (or say it) to end the session.\n"
            "A transcript will be saved when you finish.",
            title="[bold]Spanish Practice[/bold]",
            box=box.DOUBLE,
        ))
        self.console.print()

    def choose_scenario(self, scenarios: list[dict]) -> str | None:
        """Offer the scenario list; returns None for free conversation."""
        if not scenarios:
            return None

        self.console.print(Rule("Escenarios"))
        self.console.print("  [bold]0[/bold]  Free conversation")
        for i, scenario in enumerate(scenarios, start=1):
            self.console.print(f"  [bold]{i}[/bold]  {scenario['icon']} {scenario['name']}")
        self.console.print()

        choice = Prompt.ask(
            "[bold green]Choose[/bold green]",
            choices=[str(i) for i in range(len(scenarios) + 1)],
            default="0",
        )
        self.console.print()
        return None if choice == "0" else scenarios[int(choice) - 1]["id"]

    def speak_and_display(self, text: str, speaker: str = "bot") -> None:
        label = "[bold blue]Tutor:[/bold blue]" if speaker == "bot" else "[bold green]You:[/bold green]"
        self.console.print(f"{label} {text}")
        if speaker == "bot" and self.settings.INPUT_MODE == "speech":
            self.tts.speak(text)

    def listen_and_display(self) -> str | None:
        if self.settings.INPUT_MODE == "speech":
            self.console.print("[dim]Listening… (speak now)[/dim]")
            text = self.stt.listen()
            if text:
                self.console.print(f"[bold green]You:[/bold green] {text}")
            return text
        else:
            return Prompt.ask("[bold green]You[/bold green]")

    def display_goodbye(self) -> None:
        self.console.print()
        self.console.print(Rule())
        self.console.print("[bold yellow]¡Hasta luego! Session ended.[/bold yellow]")

    def display_no_followup(self) -> None:
        self.console.print("[dim]No more follow-up questions — great conversation![/dim]")

    def display_session_summary(self, transcript: Transcript) -> None:
        self.console.print()
        self.console.print(Rule("Session Summary"))
        mins, secs = divmod(transcript.duration_seconds(), 60)
        self.console.print(f"  Turns completed : [bold]{len(transcript.turns)}[/bold]")
        self.console.print(f"  Duration        : [bold]{mins}m {secs}s[/bold]")
        self.console.print(f"  Unique words    : [bold]{len(transcript.unique_spanish_words())}[/bold]")

    def display_transcript_info(self, html_path: str) -> None:
        self.console.print()
        self.console.print(f"Transcript saved → [link={html_path}][cyan]{html_path}[/cyan][/link]")
        self.console.print("Open it in your browser to review vocabulary.")
