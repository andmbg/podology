from enum import Enum
from dataclasses import dataclass
from typing import Optional


class Status(Enum):
    NOT_DONE = "➖️"
    QUEUED = "⏳️"
    QUEUED_VID = "⏳️🎥"
    PROCESSING = "🚀"
    PROCESSING_VID = "🎥"
    DONE = "✅️"
    ERROR = "💥"
    UNKNOWN = "❓️"

    def __bool__(self):
        return self is Status.DONE


@dataclass
class TranscriptInfo:
    status: Status
    wcstatus: Status


@dataclass
class AudioInfo:
    status: Status


@dataclass
class Episode:
    eid: str
    url: str
    audio: AudioInfo
    transcript: TranscriptInfo
    title: str = ""
    pub_date: str = ""
    description: str = ""
    duration: str = ""

    def __repr__(self):
        out = f"Episode (id '{self.eid}')\n"
        out += f"  Title: {self.title or '---'}\n"
        out += f"  Audio: {self.audio.status.value}\n"
        out += f"  TrScr: {self.transcript.status.value}\n"
        out += f"  URL:   {self.url}\n"
        out += f"  Publ:  {self.pub_date or '---'}\n"
        return out
