.PHONY: data, elastic-up, elastic-down, run, test

elastic-up:
	docker compose up -d elasticsearch

elastic-down:
	docker compose down -v

run:
	poetry run python main.py

install:
	poetry install
