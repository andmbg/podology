from kfsearch.data.connectors.rss import RSSConnector
from kfsearch.data.transcribers.lemonfox import LemonfoxTranscriber

PROJECT_NAME = "Decoding"
LANGUAGE = "english"  # see the documentation of your chosen API for language codes
CONNECTOR = RSSConnector(
    resource="https://decoding-the-gurus.captivate.fm/rssfeed",
)
TRANSCRIBER = LemonfoxTranscriber(LANGUAGE)
