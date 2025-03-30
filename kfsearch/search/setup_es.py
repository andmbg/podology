import json
from loguru import logger
from pathlib import Path
from datetime import datetime
from elasticsearch import Elasticsearch

from config import PROJECT_NAME
from kfsearch.data.models import EpisodeStore
from kfsearch.search.utils import make_index_name


TRANSCRIPT_INDEX_NAME = make_index_name(PROJECT_NAME)
META_INDEX_NAME = f"{TRANSCRIPT_INDEX_NAME}_meta"

# the shape of the transcript index:
TRANSCRIPT_INDEX_SETTINGS = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "eid": {"type": "keyword"},
            "pub_date": {"type": "date"},
            "episode_title": {"type": "text"},
            "text": {"type": "text"},
            "start_time": {"type": "keyword"},
            "end_time": {"type": "keyword"},
        }
    },
}

# the shape of the episode metadata index:
META_INDEX_SETTINGS = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "eid": {"type": "keyword"},
            "pub_date": {"type": "date"},
            "episode_title": {"type": "text"},
            "description": {"type": "text"},
        }
    },
}


def create_transcript_index(es_client: Elasticsearch):
    """
    Create an Elasticsearch index for the transcripts of podcast episodes.
    """
    # create index:
    if es_client.indices.exists(index=TRANSCRIPT_INDEX_NAME):
        logger.info("Transcript index already exists.")

    else:
        es_client.indices.create(index=TRANSCRIPT_INDEX_NAME, body=TRANSCRIPT_INDEX_SETTINGS)
        logger.info(f"Initialized index {TRANSCRIPT_INDEX_NAME}")

        # Load EpisodeStore
        episode_store = EpisodeStore(name=PROJECT_NAME)

        # Index transcripts from all transcribed episodes:
        for episode in episode_store.episodes(script=True):
            logger.debug(f"Indexing episode {episode.eid}")
            transcript_path = Path(episode.transcript_path)
            if transcript_path.exists():
                with open(transcript_path, "r") as f:
                    transcript_data = json.load(f)
                    for entry in transcript_data["segments"]:
                        doc = {
                            "eid": episode.eid,
                            "pub_date": datetime.strptime(episode.pub_date, "%a, %Y-%m-%d"),
                            "episode_title": episode.title,
                            "text": entry["text"],
                            "start_time": entry["start"],
                            "end_time": entry["end"],
                        }
                        es_client.index(index=TRANSCRIPT_INDEX_NAME, body=doc)
