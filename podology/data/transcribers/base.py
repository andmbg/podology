from abc import ABC, abstractmethod
from pathlib import Path


class Transcriber(ABC):
    """
    Base class for all STT transcribers. Transcribers are responsible for taking the
    specific type of audio source (normally file, but Lemonfox also offers URL for direct
    transcription from an online source) and offering a transcribe method that returns a
    transcript to store in the Episode.
    """

    def __init__(self):
        pass

    def __repr__(self) -> str:
        out = f"{self.__class__.__name__}\n"
        return out

    @abstractmethod
    def submit_job(self, audio_path: Path, job_id: str):
        """
        Submit the audio file for transcription and return a job ID.
        This is useful for asynchronous processing.
        """

    @abstractmethod
    def get_status(self, job_id: str) -> dict:
        """
        Blocking method to poll the transcription job with the external service
        until it is completed. Returns the transcription payload as a dictionary
        once completed.
        """

    @abstractmethod
    def download_transcript(self, eid: str, dest_path: Path):
        pass
