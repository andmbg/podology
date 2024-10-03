.PHONY: data

data: data/interim/poe.json

data/interim/poe.json: data/raw/poe.html
	python convert_to_json.py data/raw/poe.html data/interim/poe.json
