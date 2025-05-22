from abc import ABC, abstractmethod
from pathlib import Path


# @dataclass
class Transcriber(ABC):
    """
    Base class for all STT transcribers. Transcribers are responsible for taking the
    specific type of audio source (chiefly URL, file) and offering a transcribe method
    that returns a transcript to store in the Episode.
    """

    def __repr__(self):
        out = f"{self.__class__.__name__}\n"
        return out

    @abstractmethod
    def transcribe(self, audio_path: Path) -> dict:
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
