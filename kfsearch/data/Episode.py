import json
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from types import NoneType
from typing import Optional

import requests
from loguru import logger

from kfsearch.data.utils import episode_hash
from kfsearch.config import EPISODE_STORE_PATH


class Status(Enum):
    NOT_DONE = "➖️"
    WAITING = "⏳️"
    PROCESSING = "🚀"
    DONE = "✅️"
    ERROR = "💥"
    UNKNOWN = "❓️"

    def __bool__(self):
        return self is Status.DONE


@dataclass
class TranscriptInfo:
    path: Path
    status: Status
    wcpath: Path
    wcstatus: Status


@dataclass
class AudioInfo:
    path: Path
    status: Status


@dataclass
class Episode:
    """
    Represent an episode of a podcast with a URL to the audio file.
    """
    url: str
    store_path: Path
    audio: AudioInfo = field(init=False)
    transcript: TranscriptInfo = field(init=False)
    eid: str = field(init=False)
    title: str = ""
    pub_date: str = ""
    description: str = ""
    duration: str = ""

    def __post_init__(self):
        # Generate a 5-character alphanumeric hash from the URL
        self.eid = episode_hash(self.url.encode())
        audio_path = self.store_path / "audio" / f"{self.eid}.mp3"
        transcript_path = self.store_path / "transcripts" / f"{self.eid}.json"
        wc_path = self.store_path / "stats" / "wordclouds" / f"{self.eid}.png"

        audio_status = Status.DONE if audio_path.exists() else Status.NOT_DONE
        transcript_status = Status.DONE if transcript_path.exists() else Status.NOT_DONE
        wc_status = Status.DONE if wc_path.exists() else Status.NOT_DONE

        self.audio = AudioInfo(
            path=audio_path,
            status=audio_status
        )
        self.transcript = TranscriptInfo(
            path=transcript_path,
            wcpath=wc_path,
            status=transcript_status,
            wcstatus=wc_status
        )

    def __repr__(self):
        out = f"Episode (id '{self.eid}')\n"
        out += f"  Title: {self.title or '---'}\n"
        out += f"  Audio: {self.audio.status.value}\n"
        out += f"  TrScr: {self.transcript.status.value}\n"
        out += f"  URL:   {self.url}\n"
        out += f"  Publ:  {self.pub_date or '---'}\n"
        return out

    def get_transcription(self):
        """
        - Check if a transcript exists and abort if so.
        - Let the transcriber use either the audio URL or the local audio file,
          depending on the transcriber type.
        """
        if self.transcript.path and self.transcript.path.exists():
            logger.debug(f"Transcript for episode '{self.eid}' already exists.")
            return

        if not self.store.transcriber:
            logger.error("No Transcriber attached to this EpisodeStore.")
            return

        script_filename = self.store.transcripts_dir() / f"{self.eid}.json"

        # Get dict of the transcript from the transcriber:
        transcript: dict = self.store.transcriber.transcribe(self)

        with open(script_filename, "w") as file:
            json.dump(transcript, file, indent=4, ensure_ascii=False)

        self.transcript_path = script_filename

    def download_audio(self):
        """
        Download the audio file from the URL and save it to the audio directory of
        the containing EpisodeStore. Set self.audio.status to Status.DONE and
        self.audio.path to the audio filename.
        """
        if self.audio.path and self.audio.path.exists():
            logger.debug(f"Audio for episode '{self.eid}' already exists.")
            return
        else:
            response = requests.get(self.url, timeout=60)

            with open(self.audio.path, "wb") as file:
                file.write(response.content)
            
            self.audio.status = Status.DONE
            logger.debug(f"Audio for episode '{self.eid}' downloaded.")
