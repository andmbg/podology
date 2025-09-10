"""setup_es.py"""

# pylint: disable=W1514
import os
import json
from pathlib import Path
from datetime import datetime
import multiprocessing
import sqlite3
from typing import List

from loguru import logger
from elasticsearch import Elasticsearch, helpers
from elasticsearch.helpers import BulkIndexError
import requests

from config import DB_PATH, PROJECT_NAME, CHUNKS_DIR
from podology.data.Episode import Episode
from podology.search.utils import make_index_name
from podology.data.Transcript import Transcript


TRANSCRIPT_INDEX_NAME = make_index_name(PROJECT_NAME)
STATS_PATH = Path(__file__).parent.parent / "data" / PROJECT_NAME / "stats"
EMBEDDER_URL_PORT = os.getenv("TRANSCRIBER_URL_PORT")
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

    transcript = Transcript(episode)

    segments = transcript.segments(
        episode_attrs=["eid", "pub_date", "title"],
        segment_attrs=["start", "end", "text"],
        diarized=False,
    )

    # Abort if the episode is already indexed
    s0 = segments[0]
    first_segment_id = f"{episode.eid}_{s0['start']}_{s0['end']}"
    if es_client.exists(index=TRANSCRIPT_INDEX_NAME, id=first_segment_id):
        logger.debug(f"{episode.eid} is already indexed.")
        return

    # Index segments
    logger.debug(f"{episode.eid}: Indexing in Elasticsearch")
    actions = []
    try:
        for seg in segments:
            seg["pub_date"] = datetime.strptime(seg["pub_date"], "%Y-%m-%d")
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


def get_chunk_embeddings(episodes: List[Episode]):

    ep_transcribed = [ep for ep in episodes if ep.transcript.status]
    ep_chunked = [ep for ep in ep_transcribed if Path(CHUNKS_DIR / f"{ep.eid}_chunks.json").exists()]
    ep_to_do = [ep for ep in ep_transcribed if ep not in ep_chunked]

    for episode in ep_to_do:

        logger.debug(f"{episode.eid}: Getting chunk embeddings from WhisperX service")

        try:
            assert episode.transcript.status
            transcript = Transcript(episode)

        except Exception as e:
            logger.error(f"{episode.eid}: Failed to read transcript file: {e}")
            return {}

        chunks = transcript.chunks(
            episode_attrs=["eid", "pub_date", "title"],
            chunk_attrs=["start", "end", "text"],
            min_words=20,
            max_words=70,
            overlap=0.2,
        )

        headers = {
            "Authorization": f"Bearer {os.getenv('API_TOKEN')}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{EMBEDDER_URL_PORT}/embed",
                json={"chunks": chunks},
                headers=headers,
                timeout=1800,  # anything > 30 min. is fishy.
            )
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Failed to connect to WhisperX service: {e}")
        except requests.exceptions.Timeout as e:
            raise RuntimeError(f"WhisperX service timeout: {e}")

        if response.status_code != 200:
            raise RuntimeError(
                f"WhisperX service failed with status {response.status_code}: {response.text}"
            )

        result = response.json()

        chunk_path = CHUNKS_DIR / f"{episode.eid}_chunks.json"

        with open(chunk_path, "w") as f:
            json.dump(result, f, indent=2)

    return
