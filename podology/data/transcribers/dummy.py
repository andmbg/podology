from pathlib import Path
import time
from loguru import logger
from dataclasses import dataclass
import random

import lorem

from ...data.transcribers.base import Transcriber

@dataclass
class DummyTranscriber(Transcriber):
    """
    Dummy transcriber that returns a random lorem ipsum transcript.
    """
    delay: int = 1
    length: int = 20


    def __post_init__(self):
        pass

    def __repr__(self):
        return f"DummyTranscriber({self.delay}s)"

    def transcribe(self, audio_path: Path=Path()) -> dict:
        time.sleep(self.delay)

        num_speakers = random.randint(2, 5)
        speakers = [f"SPEAKER_0{i+1}" for i in range(num_speakers)]

        segments = []
        start = 0

        for i in range(self.length):  # 100 sentences total
            num_sentences = random.randint(1, 20)
            paragraph = lorem.paragraph()
            # Split into sentences and take only the needed number
            sentences = paragraph.split(". ")
            sentences = [s.strip() for s in sentences if s.strip()]
            # If not enough sentences, generate more
            while len(sentences) < num_sentences:
                sentences += lorem.paragraph().split(". ")
                sentences = [s.strip() for s in sentences if s.strip()]
            sentences = sentences[:num_sentences]

            speaker = speakers[i % num_speakers]

            for sent in sentences:
                text = sent
                if not text.endswith("."):
                    text += "."
                words = text.split()
                segment = {
                    "id": len(segments) + 1,
                    "start": start,
                    "end": start + len(words),
                    "speaker": speaker,
                    "text": text,
                    "words": [
                        {
                            "start": start + j,
                            "end": start + j + 1,
                            "word": w,
                            "speaker": speaker,
                            "confidence": 0.9,
                        }
                        for j, w in enumerate(words)
                    ],
                }
                segments.append(segment)
                start += len(words)

        out = {
            "segments": segments,
        }

        return out
