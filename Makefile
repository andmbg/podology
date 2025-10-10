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
	poetry run python app.py

# Combined targets
run: elastic-up workers app stop-workers

dev: workers
	TEST=True poetry run python app.py
	$(MAKE) stop-workers
