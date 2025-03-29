import os
from flask import Flask
from elasticsearch import Elasticsearch
from kfsearch.dashboard import init_dashboard
from dotenv import find_dotenv, load_dotenv

from kfsearch.search.setup_es import create_index


load_dotenv(find_dotenv())

es = Elasticsearch(
    "http://localhost:9200",
    basic_auth=(os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASSWORD")),
    # verify_certs=True,
    # ca_certs=basedir / "http_ca.crt"
)

create_index(es)

app = Flask(__name__, instance_relative_config=False)
app = init_dashboard(app, route="/", es_client=es)
app.run(host="0.0.0.0", port=8080, debug=True, load_dotenv=False)
