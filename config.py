from kfsearch.data.connectors.rss import RSSConnector

PROJECT_NAME = "Knowledge Fight"
LANGUAGE = "english"  # see the documentation of your chosen API for language codes
CONNECTION = RSSConnector(
    resource="https://decoding-the-gurus.captivate.fm/rssfeed",
)
