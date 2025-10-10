import os
import sys
from pathlib import Path

from flask import Flask, send_from_directory
from dotenv import find_dotenv, load_dotenv

from podology.dashboard import init_dashboard
from config import PROJECT_NAME


load_dotenv(find_dotenv())
test = os.getenv("TEST", "False") == "True"

server = Flask(
    __name__,
    # instance_relative_config=False
)


@server.route("/audio/<eid>")
def serve_audio(eid):
    audio_dir = Path("data") / PROJECT_NAME / "audio"
    return send_from_directory(audio_dir, f"{eid}.mp3")


app = init_dashboard(server, route="/")
if app is None:
    print("Failed to initialize dashboard")
    sys.exit(1)

flask_app = app.server

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080,
        debug=False,
        # load_dotenv=False
    )
