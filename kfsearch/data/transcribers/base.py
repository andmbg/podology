from abc import ABC, abstractmethod
from pathlib import Path


# @dataclass
class Transcriber(ABC):
    """
    Base class for all STT transcribers. Transcribers are responsible for taking the
    specific type of audio source (chiefly URL, file) and offering a transcribe method
    that returns a transcript to store in the Episode.
    """

    def __repr__(self) -> str:
        out = f"{self.__class__.__name__}\n"
        return out

    @abstractmethod
    def submit_job(self, audio_path: Path) -> str:
        """
        Submit the audio file for transcription and return a job ID.
        This is useful for asynchronous processing.
        """

    @abstractmethod
    def poll_job(
        self, job_id: str, poll_interval: int = 10, timeout: int = 28800
    ) -> dict:
        """
        Poll the server for job completion.
        Returns the transcription payload as a dictionary once completed.
        """
