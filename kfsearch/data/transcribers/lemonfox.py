import os
import requests
from dataclasses import dataclass
from loguru import logger
from dotenv import load_dotenv, find_dotenv

from kfsearch.data.transcribers.base import Transcriber


load_dotenv(find_dotenv())


@dataclass
class LemonfoxTranscriber(Transcriber):
    """
    Wrapper around the Lemonfox API for audio transcription.
    """
    language: str = "english"

    def __post_init__(self):
        # The API URL - the central bit of information for this class:
        self.location = "https://api.lemonfox.ai/v1/audio/transcriptions"
        self.api_key = os.getenv("STT_API_KEY")
        self._headers = {"Authorization": f"Bearer {self.api_key}"}

    def __repr__(self):
        out = super().__repr__()
        out += "  API key: " + "True\n" if self.api_key else "False\n"

        return out

    def transcribe(
        self,
        episode: "Episode",  # URL in the case of this class
        language: str = "english",
        response_format: str = "verbose_json",
        speaker_labels: bool = True,
        min_speakers: int = 2,
    ) -> dict:
        data = {
            "file": episode.audio_url,
            "language": language,
            "response_format": response_format,
            "speaker_labels": speaker_labels,
            "min_speakers": min_speakers,
        }
        logger.debug(f"Requesting transcription at Lemonfox for audio at URL: {episode.audio_url}")
        response = requests.post(self.location, headers=self._headers, data=data)
        logger.debug(f"Success status: {response.status_code}")

        # Remove the "words" key from the response, probably too verbose:
        response_json = response.json()

        # Remove the single-string text transcript from the response, redundant:
        del response_json["text"]

        # Prepare a list of speakers identified in this episode:
        speakers = list(set([seg["speaker"] for seg in response_json["segments"]]))
        response_json["speakers"] = speakers

        return response_json
