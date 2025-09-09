"""setup_es.py"""

# pylint: disable=W1514
import os
import json
from pathlib import Path
from datetime import datetime
from typing import List
import multiprocessing

from loguru import logger
from elasticsearch import Elasticsearch, helpers

from config import PROJECT_NAME, TRANSCRIPT_DIR
from podology.search.utils import make_index_name


TRANSCRIPT_INDEX_NAME = make_index_name(PROJECT_NAME)
STATS_PATH = Path(__file__).parent.parent / "data" / PROJECT_NAME / "stats"

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


def index_episode(episode: "Episode") -> None:
    """Index episode in Elasticsearch."""
    es_client = Elasticsearch(
        "http://localhost:9200",
        basic_auth=(os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASSWORD")),
        # verify_certs=True,
        # ca_certs=basedir / "http_ca.crt"
    )

    logger.debug(f"{episode.eid}: Indexing in Elasticsearch")

    try:
        assert episode.transcript.status
        with open(TRANSCRIPT_DIR / f"{episode.eid}.json", "r") as f:
            transcript_data = json.load(f)
    except Exception as e:
        logger.error(f"{episode.eid}: Failed to read transcript file: {e}")
        return

    # Abort if the episode is already indexed
    s0 = transcript_data["segments"][0]
    first_segment_id = f"{episode.eid}_{s0['start']}_{s0['end']}"
    if es_client.exists(index=TRANSCRIPT_INDEX_NAME, id=first_segment_id):
        logger.debug(f"{episode.eid} is already indexed.")
        return

    # Index segments
    # Here, we rely not on the Episode's Transcript class, but directly on the JSON:
    actions = []
    try:
        for entry in transcript_data["segments"]:
            doc_id = f"{episode.eid}_{entry['start']}_{entry['end']}"
            doc = {
                "_index": TRANSCRIPT_INDEX_NAME,
                "_id": doc_id,
                "_source": {
                    "eid": episode.eid,
                    "pub_date": datetime.strptime(episode.pub_date, "%Y-%m-%d"),
                    "episode_title": episode.title,
                    "text": entry["text"],
                    "start_time": entry["start"],
                    "end_time": entry["end"],
                },
            }
            actions.append(doc)
    except TypeError:
        logger.error(
            f"Error processing segments for episode {episode.eid}. Segment seems not to be a dict."
        )
        return

    # Use the bulk API for efficient indexing
    helpers.bulk(es_client, actions)
    logger.debug(f"{episode.eid}: Transcript indexed.")


def parallel_index_episodes(episodes):
    """
    Parallelize the indexing of episodes into Elasticsearch.
    """
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        pool.map(index_episode, episodes)


def index_all_transcripts(episode_store):
    """
    Index transcripts for all transcribed episodes in parallel.
    """
    episodes = [ep for ep in episode_store if ep.transcript.status]
    parallel_index_episodes(episodes)
