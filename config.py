import os
import importlib
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# DA is for testing: no audio files are downloaded.
# If True, set the TRANSCRIBER to DummyTranscriber or else it will complain about
# not finding audio files.
DUMMY_AUDIO = False

# PROJECT_NAME = "Knowledge Fight"
PROJECT_NAME = "Decoding"
LANGUAGE = "english"  # see the documentation of your chosen API for language codes
HFAPIKEY = os.getenv("HUGGINGFACE_API_KEY")

#
# Specify class paths as strings:
# We set here (1) the connector class and its arguments, and (2) the transcriber class
# and its arguments. Since this means making the class dynamic instead of hard-coding it,
# your IDE may not be able to resolve the class names. On the other hand, this allows
# you to switch and also add your own classes without changing the code.
CONNECTOR_CLASS = "kfsearch.data.connectors.rss.RSSConnector"
CONNECTOR_ARGS = {
    "remote_resource": "https://decoding-the-gurus.captivate.fm/rssfeed"
}

# WhisperX transcription: "transcribe"; Dummy: "dummytranscribe"
TRANSCRIBER_CLASS = "kfsearch.data.transcribers.whisperx.WhisperXTranscriber"
TRANSCRIBER_ARGS = {
    "server_url": "http://127.0.0.1:8001",  # locally running
    # "server_url": "http://192.168.178.27:8001",  # Gaius Pupus
    "endpoint": "dummytranscribe",  # or "dummytranscribe"
}

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
SCROLLVID_DIR = DATA_DIR / PROJECT_NAME / "scrollvids"
ASSETS_DIR = Path("kfsearch") / "assets" / "scrollvids"

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
WORDCLOUD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
