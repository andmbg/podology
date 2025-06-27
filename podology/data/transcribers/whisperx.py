"""
The transcriber class that sends audio files to a WhisperX server run probably by us for transcription.
"""

import os
from pathlib import Path
import time
from dotenv import find_dotenv, load_dotenv

from loguru import logger
import requests

from podology.data.transcribers.base import Transcriber

load_dotenv(find_dotenv())
API_TOKEN = os.getenv("API_TOKEN") or ""


class WhisperXTranscriber(Transcriber):
    """
    Transcriber class that sends audio files to a WhisperX server for transcription.
    """

    def __init__(self, server_url: str, endpoint: str):
        self.server_url = server_url
        self.endpoint = endpoint
        self.status_endpoint = f"{self.server_url}/status"
        self.result_endpoint = f"{self.server_url}/result"
        self.api_key = API_TOKEN
        self.headers = (
            {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        )
        logger.debug(
            f"Initialized WhisperXTranscriber with API key: ...-{self.api_key[-4:]}"
        )

    def submit_job(self, audio_path: Path) -> str:
        """
        Submit the audio file for transcription at our external API, and return the job ID.
        """
        logger.debug(
            f"Submitting transcription job to {self.server_url} for file {audio_path}"
        )

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        with open(audio_path, "rb") as audio_file:
            logger.debug(f"Using headers: {self.headers}")

            try:
                response = requests.post(
                    f"{self.server_url}/{self.endpoint}",
                    files={"audiofile": audio_file},
                    headers=self.headers,
                )
            except requests.exceptions.ConnectionError as e:
                raise RuntimeError(f"Connection to API failed: {e}")

        if response.status_code != 200:
            raise RuntimeError(f"Non-200 status upon job submission: {response.text}")

        job_id = response.json().get("job_id")
        time.sleep(3)
        logger.debug(f"Job submitted. Job-ID: {job_id}")

        return job_id

    def get_status(self, job_id: str) -> dict:
        """Get status of the transcription job by polling the external API.

        Args:
            job_id (str): job ID of the transcription job.

        Returns:
            dict: Contains the status of the transcription job, and if it is done,
                a download URL for the transcription result.
        """
        try:
            response = requests.get(
                f"{self.status_endpoint}/{job_id}",
                headers=self.headers,
            )
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Connection error while polling job {job_id}: {e}")

        if response.status_code == 200:
            status_dict = response.json()
            logger.debug(f"Job {job_id} status: {status_dict['status']}")
            return status_dict

        elif response.status_code == 404:
            raise RuntimeError(f"Job {job_id} not found")

        else:
            raise RuntimeError(f"Non-200 status upon job polling: {response.text}")

    def download_transcript(self, download_url: str, dest_path: Path) -> None:
        """Store the transcription result.
        """
        response = requests.get(download_url, headers=self.headers)

        if response.status_code != 200:
            raise RuntimeError(f"Failed to fetch transcript: {response.text}")

        with open(dest_path, "wb") as file:
            file.write(response.content)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}\n" f"url={self.server_url})"
