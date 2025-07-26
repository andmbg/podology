from abc import ABC, abstractmethod
import json
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv, find_dotenv

from loguru import logger
import requests

load_dotenv(find_dotenv(), override=True)


# @dataclass
class Renderer(ABC):
    """
    Base class for all scrollvid renderers. Renderers turn the transcript of an episode
    into a scroll video. How they do it is up to them, but always what goes in is the
    transcript, and what comes out is a .mp4 file stored at the correct location.
    """

    def __init__(self, server_url: str, submit_endpoint: str, frame_step: int = 100):
        self.server_url = server_url
        self.submit_endpoint = submit_endpoint
        self.frame_step = frame_step
        self.status_endpoint = f"{self.server_url}/status"
        self.result_endpoint = f"{self.server_url}/result"
        self.api_key = os.getenv("API_TOKEN") or ""
        self.headers = (
            {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        )
        logger.debug(f"Initialized BlenderTickerRenderer")

    def submit_job(self, naments: List[tuple], job_id: str) -> None:
        """Submit a scroll video rendering job.

        Send the list of named-entity--timestamp tuples to the renderer API,
        add job ID (we use the episode ID).

        """
        logger.debug(f"Submitting scroll video job")

        try:
            response = requests.post(
                f"{self.server_url}/{self.submit_endpoint}",
                json={
                    "naments": json.dumps(naments),
                    "frame_step": self.frame_step,
                    "job_id": job_id,
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
            )

        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Connection to API failed: {e}")

        if response.status_code != 200:
            raise RuntimeError(f"Non-200 status upon job submission: {response.text}")

        logger.debug(f"Render job for {job_id} submitted successfully.")

    def get_status(self, job_id: str) -> dict:
        """Get status of the scrollvid rendering job by polling the external API.

        Args:
            job_id (str): The job ID of the rendering job.

        Returns:
            dict: Contains the status of the rendering job.
        """
        try:
            response = requests.get(
                f"{self.status_endpoint}/{job_id}",
                headers=self.headers,
            )
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Connection to API failed: {e}")

        if response.status_code == 200:
            status_dict = response.json()
            logger.debug(f"Job status for {job_id}: {status_dict['status']}")
            return status_dict

        elif response.status_code == 404:
            raise RuntimeError(f"Job {job_id} not found: {response.text}")

        else:
            raise RuntimeError(f"Non-200 status upon job polling: {response.text}")

    def download_video(self, job_id: str, dest_path: Path) -> None:
        """Store the resulting video from the rendering job

        ...both in the data directory and in the assets directory.

        Args:
            job_id (str): The job ID of the rendering job.
            dest_path (Path): The path where the video should be saved.

        Returns:
            None: The video is saved to the specified path.
        """
        response = requests.get(
            f"{self.result_endpoint}/{job_id}", headers=self.headers
        )

        if response.status_code != 200:
            raise RuntimeError(f"Failed to download video: {response.text}")

        with open(dest_path, "wb") as file:
            file.write(response.content)

        assets_path = Path.cwd() / "podology" / "assets" / "scrollvids"
        assets_path.mkdir(parents=True, exist_ok=True)
        with open(assets_path / dest_path.name, "wb") as file:
            file.write(response.content)

    def __repr__(self):
        return (
            f"{self.__class__.__name__} "
            f"(url={self.server_url}, "
            f"endpoint={self.submit_endpoint}, "
            f"frame_step={self.frame_step})"
        )
