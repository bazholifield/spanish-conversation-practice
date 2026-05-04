import asyncio
import base64
import os
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from gtts import gTTS

from config.settings import Settings
from src.session.manager import SessionManager
from ui.transcript_viewer import TranscriptViewer

app = FastAPI()


def _tts_to_b64(text: str, settings: Settings) -> str:
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp = f.name
    try:
        gTTS(text=text, lang=settings.TTS_LANGUAGE, slow=settings.TTS_SLOW).save(tmp)
        return base64.b64encode(Path(tmp).read_bytes()).decode()
    finally:
        os.unlink(tmp)


def _transcribe_wav(wav_bytes: bytes, language: str) -> str | None:
    import speech_recognition as sr
    recognizer = sr.Recognizer()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        tmp = f.name
    try:
        with sr.AudioFile(tmp) as source:
            audio = recognizer.record(source)
        return recognizer.recognize_google(audio, language=language)
    except (sr.UnknownValueError, sr.RequestError):
        return None
    finally:
        os.unlink(tmp)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    settings = Settings()
    loop = asyncio.get_event_loop()
    session = SessionManager(settings)
    viewer = TranscriptViewer(settings)

    try:
        msg = await ws.receive_json()
        if msg.get("type") != "start":
            return

        session.start()
        current_question = session.get_initial_question()

        while session.is_active():
            audio_b64 = await loop.run_in_executor(None, _tts_to_b64, current_question, settings)
            await ws.send_json({"type": "question", "text": current_question, "audio": audio_b64})

            wav_bytes = await ws.receive_bytes()

            # Empty WAV (44 bytes = header only) means STT failed on client side
            if len(wav_bytes) <= 44:
                await ws.send_json({"type": "no_speech"})
                continue

            text = await loop.run_in_executor(None, _transcribe_wav, wav_bytes, settings.STT_LANGUAGE)

            if text is None:
                await ws.send_json({"type": "no_speech"})
                continue

            await ws.send_json({"type": "transcribed", "text": text})

            if text.lower().strip() in settings.EXIT_COMMANDS:
                session.record_turn(current_question, text)
                break

            session.record_turn(current_question, text)
            follow_up = session.generate_follow_up(text)
            if follow_up is None:
                break

            current_question = follow_up

        transcript = session.end()
        html = await loop.run_in_executor(None, viewer.to_html, transcript)
        await ws.send_json({"type": "end", "html": html})

    except WebSocketDisconnect:
        pass


# Serve static files — define websocket route first so it takes priority
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
