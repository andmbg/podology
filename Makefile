.PHONY: elastic-up elastic-down workers app run install test

# Dependencies
install:
	poetry install

# Individual services
elastic-up:
	docker compose up -d elasticsearch
	@echo "Waiting for Elasticsearch to start..."
	@sleep 5

elastic-down:
	docker compose down -v

workers:
	@echo "Starting RQ worker..."
	@poetry run rq worker transcription & echo $$! > .worker1.pid

stop-workers:
	@if [ -f .worker1.pid ]; then kill `cat .worker1.pid` 2>/dev/null || true; rm .worker1.pid; fi

app:
	poetry run python main.py

# Combined targets
run: elastic-up workers app stop-workers

dev: elastic-up
	@echo "Starting development environment..."
	@echo "Starting workers..."
	@poetry run rq worker transcription & W1=$$!; \
	poetry run rq worker scrollvid & W2=$$!; \
	poetry run python main.py; \
	kill $$W1 $$W2
