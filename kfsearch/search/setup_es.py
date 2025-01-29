"""
Assuming a running Elasticsearch instance on localhost:9200,
this script indexes our data.
"""

import os
import json
from loguru import logger
from pathlib import Path
from elasticsearch import Elasticsearch
from dotenv import load_dotenv, find_dotenv
from config import STORAGE_NAME
from kfsearch.data.models import EpisodeStore

# get credentials (user pw, cert):
load_dotenv(find_dotenv())

TRANSCRIPTS_DIR = Path("data") / STORAGE_NAME
INDEX_NAME = "kf_index"

# the shape of our index:
index_settings = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "eid": {"type": "keyword"},
            "episode_title": {"type": "text"},
            "text": {"type": "text"},
            "start_time": {"type": "keyword"},
            "end_time": {"type": "keyword"},
        }
    },
}


# init Elasticsearch client
# we are currently running ES without security; this needs to change once
# we go productive.
es = Elasticsearch(
    "http://localhost:9200",
    basic_auth=(os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASSWORD")),
    # verify_certs=True,
    # ca_certs="http_ca.crt",
)

# create index:
if es.indices.exists(index=INDEX_NAME):
    logger.info("Index already exists.")

else:
    es.indices.create(index=INDEX_NAME, body=index_settings)
    logger.info(f"Initialized index {INDEX_NAME}")

    # Load EpisodeStore
    episode_store = EpisodeStore(name=STORAGE_NAME)

    # Index data from all episodes
    n = 0
    for episode in episode_store.episodes(script=True):
        logger.debug(f"Indexing episode {episode.eid}")
        transcript_path = episode.transcript_path
        if transcript_path.exists():
            with open(transcript_path, "r") as f:
                transcript_data = json.load(f)
                for entry in transcript_data["segments"]:
                    doc = {
                        "eid": episode.eid,
                        "episode_title": episode.title,
                        "id": entry["id"],
                        "text": entry["text"],
                        "start_time": entry["start"],
                        "end_time": entry["end"],
                    }
                    es.index(index=INDEX_NAME, body=doc)
