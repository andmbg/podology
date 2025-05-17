"""
The transcriber class that sends audio files to a WhisperX server run probably by us for transcription.
"""
from pathlib import Path

from loguru import logger
import requests

from kfsearch.data.transcribers.base import Transcriber

class WhisperXTranscriber(Transcriber):
    """
    Transcriber class that sends audio files to a WhisperX server for transcription.
    """
    def __init__(self, server_url: str, api_key: str = None):
        self.server_url = server_url
        self.api_key = api_key

    def transcribe(self, episode: "Episode") -> dict:
        """
        Send the audio file to the WhisperX server for transcription.
        """
        logger.debug(f"Requesting transcription from {self.server_url} for file {episode.audio_path}")

        audio_path = Path(episode.audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Send audio file to the server
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        with open(audio_path, "rb") as audio_file:
            response = requests.post(
                f"{self.server_url}/transcribe",
                files={"file": audio_file},
                headers=headers,
                timeout=60,
            )

        if response.status_code != 200:
            logger.error(response.text)
            raise RuntimeError(f"Transcription failed: {response.text}")

        # Return the transcription result
        logger.info(f"Transcription successful for {audio_path}")

        return response.json()
