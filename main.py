import os
import sys
from flask import Flask
from podology.dashboard import init_dashboard
from dotenv import find_dotenv, load_dotenv


load_dotenv(find_dotenv())

app = Flask(__name__, instance_relative_config=False)
app = init_dashboard(app, route="/")
if app is None:
    print("Failed to initialize dashboard")
    sys.exit(1)

if __name__ == "__main__":
    # Check if the script is run directly or by a WSGI server
    # (to avoid running the app multiple times in debug mode)
    # if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
    app.run(
        host="0.0.0.0", port=8080, debug=True, load_dotenv=False, use_reloader=False
    )
