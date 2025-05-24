import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

from kfsearch.data.connectors.rss import RSSConnector
from kfsearch.data.transcribers.lemonfox import LemonfoxTranscriber
from kfsearch.data.transcribers.dummy import DummyTranscriber
from kfsearch.data.transcribers.whisperx import WhisperXTranscriber

load_dotenv(find_dotenv())

# PROJECT_NAME = "Knowledge Fight"
PROJECT_NAME = "Decoding"
LANGUAGE = "english"  # see the documentation of your chosen API for language codes
HFAPIKEY = os.getenv("HUGGINGFACE_API_KEY")

# Where does information about the episodes come from?
# Currently, only the RSS connector is implemented.
CONNECTOR = RSSConnector(
    remote_resource="https://decoding-the-gurus.captivate.fm/rssfeed"
    # remote_resource="https://feeds.libsyn.com/92106/rss"
  )

# TRANSCRIBER = LemonfoxTranscriber(LANGUAGE)
# TRANSCRIBER = DummyTranscriber(delay=1)
TRANSCRIBER = WhisperXTranscriber(server_url="http://127.0.0.1:8001")

# Stopwords concern only the identification of named entities. Transcription
# will still include all "uhs" and "ums" and other filler words.
PROJECT_STOPWORDS = [
        # "alex",
        # "jones",
        # "alex jones",
        # "dan",
        # "jordan",
]

ADDITIONAL_STOPWORDS = [
    i.lower() for i in [
        "okay",
        "fair",
        "which",
        "anyway",
        "hello",
        "uh",
        "right",
        "yep",
        "same",
        "wait"
    ] + PROJECT_STOPWORDS
]
# Where the store folder is located; typically just one of them:
DATA_DIR = Path("data")

DB_PATH = DATA_DIR / PROJECT_NAME / f"{PROJECT_NAME}.db"
AUDIO_DIR = DATA_DIR / PROJECT_NAME / "audio"
TRANSCRIPT_DIR = DATA_DIR / PROJECT_NAME / "transcripts"
WORDCLOUD_DIR = DATA_DIR / PROJECT_NAME / "wordclouds"

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
WORDCLOUD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
