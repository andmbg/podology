import os
import sys
from flask import Flask
from elasticsearch import Elasticsearch
from kfsearch.dashboard import init_dashboard
from dotenv import find_dotenv, load_dotenv


load_dotenv(find_dotenv())

app = Flask(__name__, instance_relative_config=False)
app = init_dashboard(app, route="/")
if app is None:
    print("Failed to initialize dashboard")
    sys.exit(1)

app.run(host="0.0.0.0", port=8080, debug=True, load_dotenv=False)
