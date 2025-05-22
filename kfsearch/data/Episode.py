import json
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from types import NoneType
from typing import Optional

import requests
from loguru import logger

from config import PROJECT_NAME, DB_PATH, AUDIO_DIR, TRANSCRIPT_DIR, WORDCLOUD_DIR
from kfsearch.data.utils import episode_hash
from config import DATA_DIR


class Status(Enum):
    NOT_DONE = "➖️"
    QUEUED = "⏳️"
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

    def to_json(self):
        """
        Convert the TranscriptInfo object to a JSON-compatible dictionary.
        """
        return {
            "path": str(self.path),
            "status": self.status.name,
            "wcpath": str(self.wcpath),
            "wcstatus": self.wcstatus.name,
        }


def transcript_info_from_json(data):
    """
    Create a TranscriptInfo object from a JSON-compatible dictionary.
    """
    return TranscriptInfo(
        path=Path(data["path"]),
        status=Status[data["status"]],
        wcpath=Path(data["wcpath"]),
        wcstatus=Status[data["wcstatus"]],
    )


@dataclass
class AudioInfo:
    path: Path
    status: Status

    def to_json(self):
        """
        Convert the AudioInfo object to a JSON-compatible dictionary.
        """
        return {"path": str(self.path), "status": self.status.name}


def audio_info_from_json(data):
    """
    Create an AudioInfo object from a JSON-compatible dictionary.
    """
    return AudioInfo(path=Path(data["path"]), status=Status[data["status"]])


@dataclass
class Episode:
    url: str
    title: str = ""
    pub_date: str = ""
    description: str = ""
    duration: str = ""
    eid: str = field(init=False)
    transcript: TranscriptInfo = field(init=False)
    audio: AudioInfo = field(init=False)

    def __post_init__(self):
        self.eid = episode_hash(self.url.encode())
        audio_path = AUDIO_DIR / f"{self.eid}.mp3"
        transcript_path = TRANSCRIPT_DIR / f"{self.eid}.json"
        wc_path = WORDCLOUD_DIR / f"{self.eid}.png"

        audio_status = Status.DONE if audio_path.exists() else Status.NOT_DONE
        transcript_status = Status.DONE if transcript_path.exists() else Status.NOT_DONE
        wc_status = Status.DONE if wc_path.exists() else Status.NOT_DONE

        self.audio = AudioInfo(path=audio_path, status=audio_status)
        self.transcript = TranscriptInfo(
            path=transcript_path,
            wcpath=wc_path,
            status=transcript_status,
            wcstatus=wc_status,
        )

    def __repr__(self):
        out = f"Episode (id '{self.eid}')\n"
        out += f"  Title: {self.title or '---'}\n"
        out += f"  Audio: {self.audio.status.value}\n"
        out += f"  TrScr: {self.transcript.status.value}\n"
        out += f"  URL:   {self.url}\n"
        out += f"  Publ:  {self.pub_date or '---'}\n"
        return out
    
    def to_json(self):
        """
        Convert the Episode object to a JSON-compatible dictionary.
        """
        return {
            "eid": self.eid,
            "url": self.url,
            "title": self.title,
            "pub_date": self.pub_date,
            "description": self.description,
            "duration": self.duration,
            "audio": self.audio.to_json(),
            "transcript": self.transcript.to_json(),
        }

def episode_from_json(data):
    """
    Create an Episode object from a JSON-compatible dictionary.
    """
    episode = Episode(
        url=data["url"],
        title=data["title"],
        pub_date=data["pub_date"],
        description=data["description"],
        duration=data["duration"],
    )
    episode.eid = data["eid"]
    episode.audio = audio_info_from_json(data["audio"])
    episode.transcript = transcript_info_from_json(data["transcript"])
    return episode

