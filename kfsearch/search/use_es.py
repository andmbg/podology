import os
from pathlib import Path
import json
from elasticsearch import Elasticsearch

# import logging
from dotenv import find_dotenv, load_dotenv


load_dotenv(find_dotenv())


# logging.getLogger("elasticsearch").setLevel(logging.DEBUG)
basedir = Path().cwd()

print((os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASSWORD")))

es = Elasticsearch(
    "http://localhost:9200",
    basic_auth=(os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASSWORD")),
    # verify_certs=True,
    # ca_certs=basedir / "certs" / "http_ca.crt",
)

if es.ping():
    print("Connected to Elasticsearch")
else:
    print("Could not connect to Elasticsearch")
    quit()


def format_search_hit(hit):
    raw = hit["highlight"]["text"][0]


def search_by_term(term):
    response = es.search(
        index="poe_index",
        body={
            "query": {"match": {"text": term}},
            "highlight": {
                "fields": {
                    "text": {
                        "number_of_fragments": 0,
                    }
                }
            },
        },
    )

    # Print results
    for hit in response["hits"]["hits"]:
        for key in ["id", "text", "chapter", "paragraph", "sentence"]:
            print(f"{key}: {hit['_source'][key]}", end="\n")
        print("\n---------------")


if __name__ == "__main__":
    search_by_term("car")
