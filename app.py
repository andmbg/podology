import os
import sys
from pathlib import Path

from flask import Flask, send_from_directory
from dotenv import find_dotenv, load_dotenv

from podology.dashboard import init_dashboard
from config import PROJECT_NAME, BASE_PATH


load_dotenv(find_dotenv())
test = os.getenv("TEST", "False") == "True"

server = Flask(__name__)

route = BASE_PATH

@server.route(f"{route}audio/<eid>")
def serve_audio(eid):
    audio_dir = Path("data") / PROJECT_NAME / "audio"
    return send_from_directory(audio_dir, f"{eid}.mp3")

app = init_dashboard(server, route=route)
if app is None:
    print("Failed to initialize dashboard")
    sys.exit(1)

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080,
        debug=False,
        # load_dotenv=False
    )
