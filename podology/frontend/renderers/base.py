from abc import ABC, abstractmethod
from pathlib import Path
from typing import List


# @dataclass
class Renderer(ABC):
    """
    Base class for all scrollvid renderers. Renderers turn the transcript of an episode
    into a scroll video. How they do it is up to them, but always what goes in is the
    transcript, and what comes out is a .mp4 file stored at the correct location.
    """

    def __repr__(self) -> str:
        out = f"{self.__class__.__name__}\n"
        return out

    @abstractmethod
    def submit_job(self, naments: List[tuple]) -> str:
        """
        Submit the timed named entities to the rendering endpoint.
        Return a job ID for polling the job status.
        """

    @abstractmethod
    def get_status(self, job_id: str) -> dict:
        """
        Blocking method to poll the rendering job with the external service
        until it is completed. Stores the resulting video file at the correct location
        upon completion. So only side effects, no return value folks.
        """

    @abstractmethod
    def download_video(self, download_url: str, dest_path: Path):
        pass
