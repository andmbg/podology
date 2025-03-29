import time
import json
from loguru import logger

from dataclasses import dataclass

@dataclass
class DummyTranscriber:
    """
    Dummy transcriber that return a dummy transcript.
    """
    delay: int = 1

    def __post_init__(self):
        pass

    def __repr__(self):
        return f"DummyTranscriber({self.delay}s)"

    def transcribe(self, audiofile_location: str) -> str:

        logger.debug(f"Dummy-Transcribing from {audiofile_location}...")
        time.sleep(self.delay)

        out = {
            "segments": [
                {
                    "id": 1,
                    "start": 0,
                    "end": 10,
                    "speaker": "Speaker 1",
                    "text": "This is a dummy transcription.",
                }
            ],
        }

        return out
