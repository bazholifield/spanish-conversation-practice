import asyncio
import os
import tempfile

import edge_tts
import pygame

from config.settings import Settings

VOICE = "es-ES-AlvaroNeural"


class TextToSpeech:
    def __init__(self, settings: Settings):
        self.settings = settings
        pygame.mixer.init()

    def speak(self, text: str) -> None:
        rate = "-20%" if self.settings.TTS_SLOW else "+0%"
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name
        try:
            asyncio.run(self._synthesize(text, rate, tmp_path))
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        finally:
            pygame.mixer.music.unload()
            os.unlink(tmp_path)

    @staticmethod
    async def _synthesize(text: str, rate: str, path: str) -> None:
        communicate = edge_tts.Communicate(text, VOICE, rate=rate)
        await communicate.save(path)
