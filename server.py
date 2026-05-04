import asyncio
import base64
import json
import os
import tempfile
from pathlib import Path

import edge_tts
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config.settings import Settings
from src.session.manager import SessionManager
from ui.transcript_viewer import TranscriptViewer

VOICE = "es-ES-AlvaroNeural"

app = FastAPI()


async def _tts_to_b64(text: str) -> str:
    communicate = edge_tts.Communicate(text, VOICE)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return base64.b64encode(audio_data).decode()


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


@app.get("/api/scenarios")
async def list_scenarios():
    settings = Settings()
    scenarios = []
    if settings.SCENARIOS_DIR.exists():
        files = sorted(settings.SCENARIOS_DIR.glob("*.json"),
                       key=lambda f: json.loads(f.read_text(encoding="utf-8")).get("order", 99))
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            scenarios.append({"id": data["id"], "name": data["name"], "icon": data["icon"]})
    return JSONResponse(scenarios)


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

        scenario_id = msg.get("scenario") or None
        session.start(scenario_id=scenario_id)
        current_question = session.get_initial_question()

        while session.is_active():
            audio_b64 = await _tts_to_b64(current_question)
            await ws.send_json({"type": "question", "text": current_question, "audio": audio_b64})

            # Receive either binary audio or a JSON control message (end button)
            data = await ws.receive()
            if data.get("text"):
                ctrl = json.loads(data["text"])
                if ctrl.get("type") == "end_session":
                    break
                continue

            wav_bytes = data.get("bytes") or b""
            if len(wav_bytes) <= 44:
                await ws.send_json({"type": "no_speech"})
                continue

            text = await loop.run_in_executor(None, _transcribe_wav, wav_bytes, settings.STT_LANGUAGE)

            if text is None:
                await ws.send_json({"type": "no_speech"})
                continue

            await ws.send_json({"type": "transcribed", "text": text})

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


app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
