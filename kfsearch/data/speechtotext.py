from abc import ABC, abstractmethod
import os
import requests
import json
from loguru import logger
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


class Transcriber(ABC):
    """
    Abstract base class for transcribers.
    """

    @abstractmethod
    def transcribe(self, url: str, **kwargs) -> json:
        pass


class LemonfoxTranscriber(Transcriber):
    """
    Wrapper around the Lemonfox API for audio transcription.
    """

    def __init__(self):
        self.api_url = "https://api.lemonfox.ai/v1/audio/transcriptions"
        self.api_key = os.getenv("LEMONFOX_API_KEY")
        self._headers = {"Authorization": f"Bearer {self.api_key}"}

    def transcribe(
        self,
        url: str,
        language: str = "english",
        response_format: str = "verbose_json",
        speaker_labels: bool = True,
        min_speakers: int = 2,
    ) -> str:
        data = {
            "file": url,
            "language": language,
            "response_format": response_format,
            "speaker_labels": speaker_labels,
            "min_speakers": min_speakers,
        }
        logger.debug(f"Requesting transcription at Lemonfox for audio at URL: {url}")
        response = requests.post(self.api_url, headers=self._headers, data=data)
        logger.debug(f"Success status: {response.status_code}")

        # Remove the "words" key from the response, probably too verbose:
        response_json = response.json()

        # Remove the single-string text transcript from the response, redundant:
        del response_json["text"]

        # Prepare a list of speakers identified in this episode:
        speakers = list(set([seg["speaker"] for seg in response_json["segments"]]))
        response_json["speakers"] = speakers

        return response_json
