import os
import sys
import importlib
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from loguru import logger


load_dotenv(find_dotenv())

logger.remove()
logger.add(
    sink=sys.stdout,
    level=os.getenv("LOG_LEVEL", "INFO"),
)

PROJECT_NAME = "Knowledge Fight"
SOURCE = "http://feeds.libsyn.com/92106/rss"  # your RSS feed
# If READONLY is True, no new jobs can be started from the dashboard and the
# 1 Hz polling for download/transcription status is turned off:
READONLY = True

# PROJECT_NAME = "Decoding"
# SOURCE = "https://feeds.captivate.fm/decoding-the-gurus/"  # your RSS feed

# -----------------------------------------------------------------------------


# If developing, use the Test project:
test = os.getenv("TEST", "False") == "True"
if test:
    PROJECT_NAME = "Test"
    SOURCE = "./tests/Test_RSS.rss"  # your RSS feed

# Make the app prefix-aware:
BASE_PATH = os.getenv("DASH_URL_PREFIX", "/")
if not BASE_PATH.endswith("/"):
    BASE_PATH += "/"

#
# Settings about the transcription and rendering APIs
#

# Connector:
CONNECTOR_CLASS = "podology.data.connectors.rss.RSSConnector"
CONNECTOR_ARGS = {"remote_resource": SOURCE}

# Transcriber:
# Dummy audio is for testing: no audio files are downloaded. If True and using
# the WhisperX transcriber API, its endpoint should be set to "dummytranscribe" below.
DUMMY_AUDIO = False
TRANSCRIBER_CLASS = "podology.data.transcribers.whisperx.WhisperXTranscriber"
TRANSCRIBER_ARGS = {
    "whisperx_url": os.getenv("TRANSCRIBER_URL_PORT"),
    "api_token": os.getenv("API_TOKEN"),
    "use_gpu": True,
    "language": "en",
    "model": "distil-large-v3",
    "min_speakers": 2,
    "max_speakers": 5,
}

#
# Settings about sentence embeddings and vector search
#
# A word on chunk size:
# Chunks are made by concatenating transcription segments. Segments are added until the
# next segment would exceed the maximum chunk size. If leaving this segment away would
# however yield < min_words, it is included nevertheless. So min_words is a hard limit,
# max_words a soft limit.
EMBEDDER_ARGS = {
    "url": os.getenv("TRANSCRIBER_URL_PORT"),
    "model": os.getenv("EMBEDDER_MODEL", "multi-qa-mpnet-base-dot-v1"),
    "dims": int(os.getenv("EMBEDDER_DIMS", 768)),
    "min_words": 100,
    "max_words": 150,
    "overlap": 0.2,
}

# Stopwords concern the identification of named entities in scroll video rendering
# and stats. They are still transcribed, and still found by Elasticsearch.
PROJECT_STOPWORDS = [
    i.lower()
    for i in [
        "Dan",
        "Jordan",
        "Alex",
        # ...
    ]
]

# Set of stopwords that don't vary from pod to pod:
STOPWORDS = [
    i.lower()
    for i in [
        "okay",
        "fair",
        "which",
        "anyway",
        "hello",
        "uh",
        "right",
        "yep",
        "same",
        "wait",
    ]
    + PROJECT_STOPWORDS
]

# Number of vertical bins for the transcript hits plot that decorates the
# transcript scrollbar:
HITS_PLOT_BINS = 500


# -----------------------------------------------------------------------------

#
# Paths and directories - can usually be ignored.
#

# Where the store folder is located:
DATA_DIR = Path("data")

DB_PATH = DATA_DIR / PROJECT_NAME / f"{PROJECT_NAME}.db"
AUDIO_DIR = DATA_DIR / PROJECT_NAME / "audio"
TRANSCRIPT_DIR = DATA_DIR / PROJECT_NAME / "transcripts"
CHUNKS_DIR = DATA_DIR / PROJECT_NAME / "chunks"
WORDCLOUD_DIR = DATA_DIR / PROJECT_NAME / "wordclouds"
ASSETS_DIR = Path("podology") / "assets"

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
WORDCLOUD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

ES_PORT = int(os.getenv("ELASTICSEARCH_PORT", 0))

def get_class(class_path):
    module_name, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def get_connector():
    cls = get_class(CONNECTOR_CLASS)
    return cls(**CONNECTOR_ARGS)


def get_transcriber():
    cls = get_class(TRANSCRIBER_CLASS)
    return cls(**TRANSCRIBER_ARGS)
