from config.settings import Settings
from src.session.manager import SessionManager, load_scenario_index
from ui.terminal import TerminalUI
from ui.transcript_viewer import TranscriptViewer


def main():
    settings = Settings()
    ui = TerminalUI(settings)
    session = SessionManager(settings)

    ui.display_welcome()
    scenario_id = ui.choose_scenario(load_scenario_index(settings))
    session.start(scenario_id=scenario_id)
    current_question = session.get_initial_question()

    while session.is_active():
        ui.speak_and_display(current_question, speaker="bot")

        raw_response = ui.listen_and_display()

        if raw_response is None or raw_response.strip().lower() in settings.EXIT_COMMANDS:
            ui.display_goodbye()
            break

        session.record_turn(question=current_question, response=raw_response)

        follow_up = session.generate_follow_up(raw_response)
        if follow_up is None:
            ui.display_no_followup()
            break

        current_question = follow_up

    transcript = session.end()
    ui.display_session_summary(transcript)

    viewer = TranscriptViewer(settings, parser=session.parser)
    html_path = viewer.generate(transcript)
    ui.display_transcript_info(html_path)


if __name__ == "__main__":
    main()
