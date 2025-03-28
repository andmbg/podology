from kfsearch.data.connectors.rss import RSSConnector


PROJECT_NAME = "Knowledge Fight"
conn = RSSConnector(
    store=store,
    rss_link="https://decoding-the-gurus.captivate.fm/rssfeed",
)