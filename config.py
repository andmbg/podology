import os
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
    # resource="https://feeds.libsyn.com/92106/rss"  # Knowledge Fight
    remote_resource="https://decoding-the-gurus.captivate.fm/rssfeed"  # Decoding
)
TRANSCRIBER = LemonfoxTranscriber(LANGUAGE)
# TRANSCRIBER = DummyTranscriber(delay=2)
# TRANSCRIBER = WhisperXTranscriber(server_url="http://127.0.0.1:8001", api_key="loremipsum")

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

