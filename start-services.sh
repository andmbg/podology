#!/bin/bash
set -e

echo "Starting Podology APIs..."

# Start transcriber in background with uvicorn
cd /app/transcriber
poetry run uvicorn podology_transcriber.server:app --host 0.0.0.0 --port 8001 &
TRANSCRIBER_PID=$!

# Start renderer in background with uvicorn
cd /app/renderer
poetry run uvicorn podology_renderer.server:app --host 0.0.0.0 --port 8002 &
RENDERER_PID=$!

# Cleanup function
cleanup() {
    echo "Shutting down..."
    kill $TRANSCRIBER_PID $RENDERER_PID 2>/dev/null || true
    wait
}

trap cleanup EXIT INT TERM

echo "Both APIs started successfully"
echo "Transcriber: http://localhost:8001"
echo "Renderer: http://localhost:8002"

# Wait for both processes
wait $TRANSCRIBER_PID $RENDERER_PID
