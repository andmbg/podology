from flask import Flask
from elasticsearch import Elasticsearch
from . import init_dashboard


es = Elasticsearch(["https://localhost:9200"])

app = Flask(__name__, instance_relative_config=False)
app = init_dashboard(app, route="/", es_client=es)
app.run(host="0.0.0.0", port=8080, debug=True, load_dotenv=False)
