# kfsearch/data/connectors/base.py
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Transcriber(ABC):
    """
    Base class for all STT transcribers. Transcribers are responsible for taking the
    specific type of audio source (chiefly URL, file) and offering a transcribe method
    that returns a transcript to store in the Episode.
    """
    store: "EpisodeStore" = field(default=None, init=False)
    location: str = field(default=None, init=False)

    def __repr__(self):
        out = f"{self.__class__.__name__}\n  resource={self.location}\n"
        location: field(default=None, init=False)  # URL for APIs, file path for local transcribers
        if self.store:
            out += f"  store: {self.store.name}\n"
        else:
            out += f"  store: None\n"

        return out

    @abstractmethod
    def transcribe(self, audiofile_location: str, **kwargs) -> str:
        pass
