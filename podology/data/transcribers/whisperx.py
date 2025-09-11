"""
The transcriber class that sends audio files directly to a WhisperX microservice for transcription.
"""

import os
import json
import tempfile
from pathlib import Path
import time
from typing import Dict, Optional
from dotenv import find_dotenv, load_dotenv

from loguru import logger
import requests

from podology.data.transcribers.base import Transcriber
from config import TRANSCRIPT_DIR, TRANSCRIBER_ARGS

load_dotenv(find_dotenv(), override=True)


class WhisperXTranscriber(Transcriber):
    """
    Transcriber class that sends audio files to a WhisperX microservice for transcription.
    """

    def __init__(
        self,
        whisperx_url: str,
        use_gpu: bool = True,
        api_token: Optional[str] = None,
        language: str = "auto",
        model: str = "base",
        min_speakers: int = 2,
        max_speakers: int = 5,
    ):
        self.whisperx_url = whisperx_url.rstrip("/")
        self.use_gpu = use_gpu
        self.api_token = api_token or os.getenv("API_TOKEN")
        self.headers = {}
        if self.api_token:
            self.headers["Authorization"] = f"Bearer {self.api_token}"
        self.language = language
        self.model = model
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers

        logger.debug(
            f"Initialized WhisperXTranscriber (url={self.whisperx_url}, gpu={self.use_gpu})"
        )

        # Test connection on initialization
        self._test_connection()

    def _test_connection(self) -> None:
        """Test if the WhisperX service is reachable"""
        try:
            response = requests.get(f"{self.whisperx_url}/", timeout=10)
            if response.status_code != 200:
                logger.warning(
                    f"WhisperX service returned status {response.status_code}"
                )
        except requests.exceptions.RequestException as e:
            logger.error(f"Cannot reach WhisperX service at {self.whisperx_url}: {e}")
            raise RuntimeError(f"WhisperX service unreachable: {e}")

    def submit_job(self, audio_path: Path, job_id: str) -> None:
        """
        Submit audio file for transcription and wait for completion.
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"{job_id}: Submitting transcription job")

        try:
            result = self._transcribe_audio(audio_path)

            # Store result locally with job_id
            self._store_result(job_id, result)

            logger.info(f"Transcription completed for job {job_id}")

        except Exception as e:
            logger.error(f"Transcription failed for job {job_id}: {e}")
            # Store error status
            raise

    def _transcribe_audio(self, audio_path: Path) -> Dict:
        """Call the WhisperX service for transcription"""

        with open(audio_path, "rb") as audio_file:
            files = {"audio_file": (audio_path.name, audio_file, "audio/mpeg")}

            data = {
                "task": "transcribe",
                "language": self.language,
                "model": self.model,
            }

            params = {
                "output": "json",
                "diarize": True,
                "min_speakers": self.min_speakers,
                "max_speakers": self.max_speakers,
                "align_model": "WAV2VEC2_ASR_LARGE_LV60K_960H",
            }

            logger.debug(f"Calling WhisperX service: POST {self.whisperx_url}/asr")

            try:
                response = requests.post(
                    f"{self.whisperx_url}/asr",
                    files=files,
                    data=data,
                    params=params,
                    headers=self.headers,
                    timeout=1800,  # anything > 30 min. is fishy.
                )
            except requests.exceptions.ConnectionError as e:
                raise RuntimeError(f"Failed to connect to WhisperX service: {e}")
            except requests.exceptions.Timeout as e:
                raise RuntimeError(f"WhisperX service timeout: {e}")

            if response.status_code != 200:
                raise RuntimeError(
                    f"WhisperX service failed with status {response.status_code}: {response.text}"
                )

            result = response.json()
            logger.debug(f"WhisperX service completed successfully")

            # Process and normalize the result
            return self._fix_microservice_format(result)

    def _fix_microservice_format(self, result: Dict) -> Dict:
        """
        Convert WhisperX service response to standardized format
        """
        # Ensure the result has the expected structure
        if "segments" not in result and "text" in result:
            # Simple format conversion if needed
            result = {
                "segments": [
                    {
                        "text": result["text"],
                        "start": 0,
                        "end": 0,
                        "speaker": "SPEAKER_00",
                    }
                ],
                "language": result.get("language", "en"),
            }

        # Ensure all segments have speakers
        for segment in result.get("segments", []):
            if "speaker" not in segment:
                segment["speaker"] = "SPEAKER_00"

        return result

    def _store_result(self, job_id: str, result: Dict) -> None:
        """Store transcription result locally"""
        result_file = TRANSCRIPT_DIR / f"{job_id}.json"

        with open(result_file, "w") as f:
            json.dump(result, f, indent=2)

        logger.debug(f"Stored result for job {job_id} at {result_file}")

    def get_status(self, eid: str) -> Dict:
        """Get status of the transcription job by checking local storage.

        If it does not exist, return not_found. If it exists then if it is a
        dict as returned by _store_error(), return the status. Else assumed to
        be a completed transcription result.
        """
        result_file = TRANSCRIPT_DIR / f"{eid}.json"

        if not result_file.exists():
            return {"status": "not_found", "job_id": eid}

        try:
            with open(result_file, "r") as f:
                result = json.load(f)
                # bit hacky: if "status" key is not present, we assume all OK
                if "status" not in result:
                    return {"status": "done"}

            return {
                "status": result["status"],
                "job_id": eid,
                "timestamp": result.get("timestamp"),
                "error_message": result.get("error"),
            }
        except Exception as e:
            logger.error(f"Error reading result file for job {eid}: {e}")
            return {"status": "failed", "job_id": eid, "error_message": str(e)}

    def download_transcript(self, eid: str, dest_path: Path) -> None:
        """Download the transcription result to specified path"""
        result_file = TRANSCRIPT_DIR / f"{eid}.json"

        if not result_file.exists():
            raise FileNotFoundError(f"No result found for job {eid}")

        try:
            with open(result_file, "r") as f:
                result = json.load(f)

            if result["status"] != "completed":
                raise RuntimeError(
                    f"Job {eid} is not completed (status: {result['status']})"
                )

            # Copy the transcription result to destination
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            with open(dest_path, "w") as f:
                json.dump(result["transcription"], f, indent=2)

            logger.info(f"Downloaded transcript for job {eid} to {dest_path}")

        except Exception as e:
            raise RuntimeError(f"Failed to download transcript for job {eid}: {e}")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(url={self.whisperx_url}, gpu={self.use_gpu})"
