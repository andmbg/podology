from kfsearch.data.models import Episode, EpisodeStore
from kfsearch.data.rss import PodcastRSSExtractor
from config import STORAGE_NAME

store = EpisodeStore(name="Knowledge Fight")

rss_extractor = PodcastRSSExtractor(
    rss_link="https://knowledgefight.libsyn.com/rss",
    store=store,
)
rss_extractor.download_rss()

for ep in rss_extractor.extract_episodes():
    episode = Episode(
        store=store,
        audio_url=ep["audio_url"],
        title=ep["title"],
        pub_date=ep["pub_date"],
        description=ep["description"],
        duration=ep["duration"],
    )

episode = [ep for ep in store.episodes() if ep.eid == "2iPRY"][0]

episode.transcribe()

store.to_json()
