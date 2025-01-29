.PHONY: data, elastic-up, elastic-down, run, test

data/interim/poe.json: data/raw/poe.html
	python convert_to_json.py data/raw/poe.html data/interim/poe.json

elastic-up:
	docker-compose up -d elasticsearch

elastic-down:
	docker-compose down

run:
	poetry run python -m kfsearch.dashboard

test:
	poetry run python -m kfsearch.search.use_es
