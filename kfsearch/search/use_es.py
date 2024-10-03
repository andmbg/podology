import os
from pathlib import Path
import json
from elasticsearch import Elasticsearch

basedir = Path().cwd().parent
es = Elasticsearch(
    "https://localhost:9200",
    basic_auth=(os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASSWORD")),
    verify_certs=True,
    ca_certs=basedir / "http_ca.crt",
)

poe_json_path = basedir / "data" / "interim" / "poe.json"
with open(poe_json_path, "r") as f:
    poe_data = json.load(f)

for doc in poe_data:
    es.index(index="poe_index", body=doc)


def search_by_term(term):
    response = es.search(index="poe_index", body={"query": {"match": {"text": term}}})

    # Print results
    for hit in response["hits"]["hits"]:
        for key in ["id", "text", "chapter", "paragraph", "sentence"]:
            print(f"{key}: {hit['_source'][key]}", end="\n")
        print("\n---------------")
