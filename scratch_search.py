from elasticsearch import Elasticsearch
import os
from kfsearch.search.setup_es import TRANSCRIPT_INDEX_NAME

es = Elasticsearch(
    "http://localhost:9200",
    basic_auth=(os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASSWORD")),
    # verify_certs=True,
    # ca_certs=basedir / "http_ca.crt"
)

response = es.search(
    index=TRANSCRIPT_INDEX_NAME,
    body={"query": {"match_all": {}}},
    size=10,
    from_=0,
)

print(response)
