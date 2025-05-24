"""
The transcriber class that sends audio files to a WhisperX server run probably by us for transcription.
"""

import os
from pathlib import Path
from time import sleep
from dotenv import find_dotenv, load_dotenv

from loguru import logger
import requests

from kfsearch.data.transcribers.base import Transcriber

load_dotenv(find_dotenv())
API_TOKEN = os.getenv("API_TOKEN") or ""


class WhisperXTranscriber(Transcriber):
    """
    Transcriber class that sends audio files to a WhisperX server for transcription.
    """

    def __init__(self, server_url: str):
        self.server_url = server_url
        self.api_key = API_TOKEN
        self.headers = (
            {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        )
        logger.debug(f"Initialized WhisperXTranscriber with API key: {self.api_key}")

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
            response = requests.post(
                f"{self.server_url}/transcribe",
                files={"file": audio_file},
                headers=self.headers,
            )
        if response.status_code != 200:
            logger.error(f"Failed to submit job: {response.text}")
            raise RuntimeError(f"Failed to submit job: {response.text}")

        job_id = response.json().get("job_id")
        logger.debug(f"Job submitted. Job-ID: {job_id}")

        return job_id

    def poll_job(
        self, job_id: str, poll_interval: int = 60, timeout: int = 28800
    ) -> dict:
        """
        Poll the server for job completion. If status is reported as "done",
        call get_result() and return its dict payload.
        """
        elapsed = 0
        while elapsed < timeout:
            response = requests.get(
                f"{self.server_url}/transcribe/status/{job_id}", headers=self.headers
            )
            if response.status_code == 200:
                job_status = response.json().get("status")
                logger.debug(f"Job {job_id} status: {job_status}")
                
                if job_status == "done":
                    return self._get_result(job_id)
                
                elif job_status == "failed":
                    logger.error(f"Transcription failed for job {job_id}")
                    raise RuntimeError(f"Transcription failed for job {job_id}")
            
            elif response.status_code == 404:
                logger.error(f"Job {job_id} not found")
                raise RuntimeError(f"Job {job_id} not found")
            
            # Job still ongoing:
            sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(
            f"Transcription job {job_id} timed out after {timeout} seconds"
        )

    def _get_result(self, job_id: str) -> dict:
        """
        Fetch the transcription result.
        """
        response = requests.get(
            f"{self.server_url}/transcribe/result/{job_id}", headers=self.headers
        )
        if response.status_code == 200:
            logger.info(f"Transcription result fetched for job {job_id}")
            return response.json()
        else:
            logger.error(f"Failed to fetch result for job {job_id}: {response.text}")
            raise RuntimeError(
                f"Failed to fetch result for job {job_id}: {response.text}"
            )

    def __repr__(self) -> str:
        return(
            f"{self.__class__.__name__}\n"
            f"url={self.server_url})"
        )
