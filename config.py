import os
import importlib
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


PROJECT_NAME = "Project Name"
SOURCE = "http://feeds.libsyn.com/92106/rss"  # your RSS feed

#
# Settings about the transcription and rendering APIs
#

# Renderer:
RENDERER_CONFIG = {
    "server_url": os.getenv("RENDERER_URL_PORT"),
    "submit_endpoint": "render",
    # frame step - temporal resolution of the scroll video:
    #    25 - one frame per second (reasonably smooth effect)
    # 10000 - 9 frames per hour (for testing)
    "frame_step": 100,
}

# Connector:
CONNECTOR_CLASS = "podology.data.connectors.rss.RSSConnector"
CONNECTOR_ARGS = {"remote_resource": SOURCE}

# Transcriber:
# Dummy audio is for testing: no audio files are downloaded. If True and using
# the WhisperX transcriber API, its endpoint should be set to "dummytranscribe" below.
DUMMY_AUDIO = False
TRANSCRIBER_CLASS = "podology.data.transcribers.whisperx.WhisperXTranscriber"
TRANSCRIBER_ARGS = {
    "server_url": os.getenv("TRANSCRIBER_URL_PORT"),
    # alternatively "dummytranscribe" for testing with our whisperX server:
    "endpoint": "transcribe",
}

# Stopwords concern the identification of named entities in scroll video rendering
# and stats. They are still transcribed, and still found by Elasticsearch.
PROJECT_STOPWORDS = [
    i.lower()
    for i in [
        # "Dan",  # e.g., presenter names
        # "Jordan",
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

# -----------------------------------------------------------------------------

#
# Paths and directories - can usually be ignored.
#

# Where the store folder is located:
DATA_DIR = Path("data")

DB_PATH = DATA_DIR / PROJECT_NAME / f"{PROJECT_NAME}.db"
AUDIO_DIR = DATA_DIR / PROJECT_NAME / "audio"
TRANSCRIPT_DIR = DATA_DIR / PROJECT_NAME / "transcripts"
WORDCLOUD_DIR = DATA_DIR / PROJECT_NAME / "wordclouds"
SCROLLVID_DIR = DATA_DIR / PROJECT_NAME / "scrollvids"
ASSETS_DIR = Path("podology") / "assets"

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
WORDCLOUD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


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
