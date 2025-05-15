from kfsearch.data.connectors.rss import RSSConnector
from kfsearch.data.transcribers.lemonfox import LemonfoxTranscriber
from kfsearch.data.transcribers.dummy import DummyTranscriber

PROJECT_NAME = "Knowledge Fight"
LANGUAGE = "english"  # see the documentation of your chosen API for language codes
CONNECTOR = RSSConnector(
    # resource="https://decoding-the-gurus.captivate.fm/rssfeed"  # Decoding
    resource="https://feeds.libsyn.com/92106/rss"  # Knowledge Fight
)
TRANSCRIBER = LemonfoxTranscriber(LANGUAGE)
# TRANSCRIBER = DummyTranscriber(delay=2)

PROJECT_STOPWORDS = [
        "alex",
        "jones",
        "alex jones",
        "dan",
        "jordan",
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

