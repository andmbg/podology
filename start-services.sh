#!/bin/bash
# start-services.sh

# Start transcriber
cd /app/transcriber
poetry run uvicorn podology_transcriber.server:app --host 0.0.0.0 --port 8001 &

# Start renderer
cd /app/renderer  
poetry run uvicorn podology_renderer.server:app --host 0.0.0.0 --port 8002 &

# Wait for both processes
wait
