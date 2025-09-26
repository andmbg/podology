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

from config import PROJECT_NAME, TRANSCRIPT_DIR, CHUNKS_DIR, EMBEDDER_ARGS
from podology.data.Episode import Episode
from podology.search.utils import make_index_name


TRANSCRIPT_INDEX_NAME = make_index_name(PROJECT_NAME, suffix="")
CHUNK_INDEX_NAME = make_index_name(PROJECT_NAME, suffix="_chunks")
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

CHUNK_INDEX_SETTINGS = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "cid": {"type": "keyword"},
            "eid": {"type": "keyword"},
            "pub_date": {"type": "date"},
            "title": {"type": "text"},
            "text": {"type": "text"},
            "start": {"type": "keyword"},
            "end": {"type": "keyword"},
            "vector": {
                "type": "dense_vector",
                "dims": EMBEDDER_ARGS["dims"],
                "index": True,
                "similarity": "cosine",
            },
        }
    },
}


def setup_elasticsearch_indices() -> None:
    """Create all required Elasticsearch indices with proper settings."""
    es_client = Elasticsearch(
        "http://localhost:9200",
        basic_auth=(os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASSWORD")),
    )

    # Create transcript index
    if not es_client.indices.exists(index=TRANSCRIPT_INDEX_NAME):
        logger.info(f"Creating transcript index: {TRANSCRIPT_INDEX_NAME}")
        es_client.indices.create(
            index=TRANSCRIPT_INDEX_NAME, body=TRANSCRIPT_INDEX_SETTINGS
        )
        logger.info(f"Transcript index created successfully")
    else:
        logger.debug(f"Transcript index {TRANSCRIPT_INDEX_NAME} already exists")

    # Create chunk index
    if not es_client.indices.exists(index=CHUNK_INDEX_NAME):
        logger.info(f"Creating chunk index: {CHUNK_INDEX_NAME}")
        es_client.indices.create(index=CHUNK_INDEX_NAME, body=CHUNK_INDEX_SETTINGS)
        logger.info(f"Chunk index created successfully")
    else:
        logger.debug(f"Chunk index {CHUNK_INDEX_NAME} already exists")


def index_segments(episodes: List[Episode]) -> None:
    """
    Parallelize the indexing of episodes into Elasticsearch.
    """
    with multiprocessing.Pool(processes=MAX_PARALLEL_INDEXING_PROCESSES) as pool:
        pool.map(index_segment, episodes)


def index_segment(episode: Episode) -> None:
    """Index episode in Elasticsearch.

    Feeds index "TRANSCRIPT_INDEX_NAME".
    """
    es_client = Elasticsearch(
        "http://localhost:9200",
        basic_auth=(os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASSWORD")),
        # verify_certs=True,
        # ca_certs=basedir / "http_ca.crt"
    )

    # Using direct access to raw transcription file; using Transcript was slow
    if is_indexed_by_eid(episode.eid, es_client, TRANSCRIPT_INDEX_NAME):
        logger.debug(f"{episode.eid} is already indexed.")
        return

    # Index segments
    segments = json.load(open(TRANSCRIPT_DIR / f"{episode.eid}.json", "r"))["segments"]
    logger.debug(f"{episode.eid}: Indexing segmentsin Elasticsearch")

    actions = []
    try:
        for seg in segments:
            del seg["words"]
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

def index_chunks(episodes: List[Episode]) -> None:
    """
    Parallelize the indexing of chunks into Elasticsearch.
    """
    with multiprocessing.Pool(processes=MAX_PARALLEL_INDEXING_PROCESSES) as pool:
        pool.map(index_chunk, episodes)


def index_chunk(episode: Episode) -> None:
    """Index episode chunks and their vectors in Elasticsearch.

    Creates and feeds index "CHUNK_INDEX_NAME".
    """
    es_client = Elasticsearch(
        "http://localhost:9200",
        basic_auth=(os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASSWORD")),
        # verify_certs=True,
        # ca_certs=basedir / "http_ca.crt"
    )

    if is_indexed_by_eid(episode.eid, es_client, CHUNK_INDEX_NAME):
        logger.debug(f"{episode.eid} chunks are already indexed.")
        return

    # Index chunks
    chunks = json.load(open(CHUNKS_DIR / f"{episode.eid}_chunks.json", "r"))["chunks"]
    logger.debug(f"{episode.eid}: Indexing chunks in Elasticsearch")
    actions = [
        {
            "_index": CHUNK_INDEX_NAME,
            "_id": f"{episode.eid}_{chunk['cid']}",
            "_source": chunk,
        }
        for chunk in chunks
    ]

    print(chunks[5]["embedding"])

    # Use the bulk API for efficient indexing
    try:
        helpers.bulk(es_client, actions)
        logger.debug(f"{episode.eid}: Chunks indexed.")
    except BulkIndexError as e:
        logger.error(f"Bulk indexing failed: {e.errors}")
        for err in e.errors:
            logger.error(json.dumps(err, indent=2))
        raise


def is_indexed_by_eid(eid: str, es_client: Elasticsearch, index_name: str) -> bool:
    """Check if episode is indexed using the eid field."""
    query = {"query": {"match": {"eid": eid}}, "size": 1, "_source": False}

    try:
        response = es_client.search(index=index_name, body=query)
        return response["hits"]["total"]["value"] > 0
    except Exception as e:
        logger.error(f"Error checking index for episode {eid}: {e}")
        return False
