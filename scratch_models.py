from kfsearch.data.models import Episode, EpisodeStore
from kfsearch.data.connectors.rss import RSSConnector

store = EpisodeStore(name="Knowledge Fight")

rss_extractor = RSSConnector(
    rss_link="https://knowledgefight.libsyn.com/rss",
    store=store,
)
rss_extractor._download_rss()

for ep in rss_extractor._extract_episodes():
    episode = Episode(
        store=store,
        audio_url=ep["audio_url"],
        title=ep["title"],
        pub_date=ep["pub_date"],
        description=ep["description"],
        duration=ep["duration"],
    )

for i in [0, 2, 3]:
    episode = store.episodes()[i]
    episode.transcribe()
