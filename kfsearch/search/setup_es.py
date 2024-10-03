"""
Assuming a running Elasticsearch instance on localhost:9200, this script indexes our data.
"""
import os
import json
import logging
from pathlib import Path
from elasticsearch import Elasticsearch
from dotenv import load_dotenv, find_dotenv


# get credentials (user pw, cert):
load_dotenv(find_dotenv())

logging.basicConfig(level=logging.DEBUG)

basedir = Path().cwd().parent
poe_json_path = Path().cwd() / "data" / "interim" / "poe.json"
index_name = "poe_index"

# the shape of our index:
index_settings = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "text": {"type": "text"},
            "title": {"type": "text"},
            "chapter": {"type": "integer"},
            "paragraph": {"type": "integer"},
            "sentence": {"type": "integer"},
        }
    },
}


# init Elasticsearch client
# we are currently running ES without security; this needs to change once
# we go productive.
es = Elasticsearch(
    "http://localhost:9200",
    # basic_auth=(os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASSWORD")),
    # verify_certs=True,
    # ca_certs="http_ca.crt",
)

# create index:
if not es.indices.exists(index=index_name):
    es.indices.create(index=index_name, body=index_settings)

    # load and index data:
    with open(poe_json_path, "r") as f:
        poe_data = json.load(f)

    for doc in poe_data:
        es.index(index="poe_index", body=doc)
