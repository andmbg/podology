import json
import os
import time
from typing import List
from dotenv import find_dotenv, load_dotenv
from loguru import logger
import requests

load_dotenv(find_dotenv())


class BlenderTickerRenderer:

    def __init__(self, server_url: str, endpoint: str, frame_step: int):
        self.server_url = server_url
        self.endpoint = endpoint
        self.frame_step = frame_step
        self.status_endpoint = f"{self.server_url}/status"
        self.result_endpoint = f"{self.server_url}/result"
        self.api_key = os.getenv("API_TOKEN") or ""
        self.headers = (
            {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        )
        logger.debug(f"Initialized BlenderTickerRenderer")

    def submit_job(self, naments: List[tuple]) -> str:
        """Submit a scroll video rendering job for the given episode ID."""
        logger.debug(f"Submitting scroll video job")

        try:
            response = requests.post(
                f"{self.server_url}/{self.endpoint}",
                json={"naments": json.dumps(naments), "frame_step": self.frame_step},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )

        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Connection to API failed: {e}")

        if response.status_code != 200:
            raise RuntimeError(f"Non-200 status upon job submission: {response.text}")

        job_id = response.json().get("job_id")
        logger.debug(f"Job submitted. Job-ID: {job_id}")

        return job_id

    def get_status(self, job_id: str) -> dict:
        """Get status of the scrollvid rendering job by polling the external API.

        Args:
            job_id (str): The job ID of the rendering job.

        Returns:
            dict: Contains the status of the rendering job, and if it is done,
                a download URL for the resulting video.
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

    def download_video(self, download_url: str, dest_path: str) -> None:
        """Store the result of the rendering job."""
        response = requests.get(download_url, headers=self.headers)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to download video: {response.text}")

        with open(dest_path, "wb") as file:
            file.write(response.content)

    def __repr__(self):
        return (
            f"{self.__class__.__name__} "
            f"(url={self.server_url}, "
            f"endpoint={self.endpoint}, "
            f"frame_step={self.frame_step})"
        )
