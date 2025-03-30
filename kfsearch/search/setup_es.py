import json
from loguru import logger
from pathlib import Path
from datetime import datetime
from elasticsearch import Elasticsearch

from config import PROJECT_NAME
from kfsearch.data.models import EpisodeStore, Episode
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


def index_transcripts(es_client: Elasticsearch):
    """
    Create an Elasticsearch index for the transcripts of podcast episodes.
    """
    # Init index if it does not exist:
    if not es_client.indices.exists(index=TRANSCRIPT_INDEX_NAME):
        es_client.indices.create(index=TRANSCRIPT_INDEX_NAME, body=TRANSCRIPT_INDEX_SETTINGS)
        logger.info(f"Initialized index {TRANSCRIPT_INDEX_NAME}")

    # Load EpisodeStore
    episode_store = EpisodeStore(name=PROJECT_NAME)

    # Index transcripts from all transcribed episodes:
    n = 0
    for episode in episode_store.episodes(script=True):
        if index_episode_transcript(episode, es_client):
            n += 1
    logger.debug(f"Indexed {n} transcripts into {TRANSCRIPT_INDEX_NAME}.")


def index_episode_transcript(episode: Episode, es_client: Elasticsearch) -> bool:
    transcript_path = Path(episode.transcript_path)
    if transcript_path.exists():
        with open(transcript_path, "r") as f:
            transcript_data = json.load(f)

        # Check if first segment in index (means episode was indexed):
        s0 = transcript_data["segments"][0]
        first_segment_id = f"{episode.eid}_{s0['start']}_{s0['end']}"

        if es_client.exists(index=TRANSCRIPT_INDEX_NAME, id=first_segment_id):
            return False

        for entry in transcript_data["segments"]:
            doc_id = f"{episode.eid}_{entry['start']}_{entry['end']}"
            doc = {
                "eid": episode.eid,
                "pub_date": datetime.strptime(episode.pub_date, "%Y-%m-%d"),
                "episode_title": episode.title,
                "text": entry["text"],
                "start_time": entry["start"],
                "end_time": entry["end"],
            }
            es_client.index(index=TRANSCRIPT_INDEX_NAME, body=doc, id=doc_id)

        return True