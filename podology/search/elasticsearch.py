"""setup_es.py"""

# pylint: disable=W1514
import os
import json
from pathlib import Path
from datetime import datetime
import multiprocessing
from typing import List

from loguru import logger
from elasticsearch import Elasticsearch, helpers
from elasticsearch.helpers import BulkIndexError

from config import PROJECT_NAME, TRANSCRIPT_DIR
from podology.data.Episode import Episode
from podology.search.utils import make_index_name


TRANSCRIPT_INDEX_NAME = make_index_name(PROJECT_NAME)
STATS_PATH = Path(__file__).parent.parent / "data" / PROJECT_NAME / "stats"
MAX_PARALLEL_INDEXING_PROCESSES = 4  # max: multiprocessing.cpu_count()

# the shape of the transcript index:
TRANSCRIPT_INDEX_SETTINGS = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "eid": {"type": "keyword"},
            "pub_date": {"type": "date"},
            "title": {"type": "text"},
            "text": {"type": "text"},
            "start_time": {"type": "keyword"},
            "end_time": {"type": "keyword"},
        }
    },
}


def index_segments(episodes: List[Episode]) -> None:
    """
    Parallelize the indexing of episodes into Elasticsearch.
    """
    with multiprocessing.Pool(processes=MAX_PARALLEL_INDEXING_PROCESSES) as pool:
        pool.map(index_segment, episodes)


def index_segment(episode: Episode) -> None:
    """Index episode in Elasticsearch.

    Creates and feeds index "TRANSCRIPT_INDEX".
    """
    es_client = Elasticsearch(
        "http://localhost:9200",
        basic_auth=(os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASSWORD")),
        # verify_certs=True,
        # ca_certs=basedir / "http_ca.crt"
    )

    # Using direct access to raw transcription file; using Transcript was slow
    if is_indexed(episode, es_client):
        logger.debug(f"{episode.eid} is already indexed.")
        return

    # Index segments
    segments = json.load(open(TRANSCRIPT_DIR / f"{episode.eid}.json", "r"))["segments"]
    logger.debug(f"{episode.eid}: Indexing in Elasticsearch")

    actions = []
    try:
        for seg in segments:
            seg["pub_date"] = episode.pub_date
            seg["eid"] = episode.eid
            seg["title"] = episode.title
            doc_id = f"{episode.eid}_{seg['start']}_{seg['end']}"
            doc = {
                "_index": TRANSCRIPT_INDEX_NAME,
                "_id": doc_id,
                "_source": seg,
            }
            actions.append(doc)
    except TypeError:
        logger.error(
            f"Error processing segments for episode {episode.eid}. Segment seems not to be a dict."
        )
        return

    # Use the bulk API for efficient indexing
    try:
        helpers.bulk(es_client, actions)
        logger.debug(f"{episode.eid}: Transcript indexed.")
    except BulkIndexError as e:
        logger.error(f"Bulk indexing failed: {e.errors}")
        for err in e.errors:
            logger.error(json.dumps(err, indent=2))
        raise


def is_indexed(episode: Episode, es_client: Elasticsearch) -> bool:
    """Check if episode is already indexed in Elasticsearch."""
    raw_transcript = json.load(open(TRANSCRIPT_DIR / f"{episode.eid}.json", "r"))
    s0 = raw_transcript["segments"][0]
    first_segment_id = f"{episode.eid}_{s0['start']}_{s0['end']}"
    return bool(es_client.exists(index=TRANSCRIPT_INDEX_NAME, id=first_segment_id))
