.PHONY: data, elastic-up, elastic-down

data: data/interim/poe.json

data/interim/poe.json: data/raw/poe.html
	python convert_to_json.py data/raw/poe.html data/interim/poe.json

elastic-up:
	docker-compose up -d elasticsearch

elastic-down:
	docker-compose down
