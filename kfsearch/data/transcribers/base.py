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
        if self.store:
            out += f"  store: {self.store.name}\n"
        else:
            out += "  store: None\n"

        return out

    @abstractmethod
    def transcribe(self, episode: "Episode", **kwargs) -> dict:
        """
        Needs to return a dictionary with the transcript of the episode, at least
        containing the following keys:
        {
            "segments": [
                {
                    "id":      <int>,
                    "start":   <float>,
                    "end":     <float>,
                    "speaker": <str>,
                    "text":    <str>,
                }
            ],
        }
        """
