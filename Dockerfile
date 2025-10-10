# Use a small official Python image
FROM python:3.12-bookworm

ENV PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    PORT=8080 \
    NLTK_DATA=/app/nltk_data

WORKDIR /app

# system deps for building wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
 && rm -rf /var/lib/apt/lists/*

# install poetry
RUN pip install --no-cache-dir "poetry>=1.2"

# copy dependency metadata for better cache
COPY pyproject.toml poetry.lock* /app/

# install runtime deps (no dev deps)
RUN poetry install --no-interaction --no-ansi

# download NLTK data to the right location
RUN mkdir -p /app/nltk_data
RUN python -m nltk.downloader \
    stopwords \
    punkt \
    punkt_tab \
    averaged_perceptron_tagger \
    averaged_perceptron_tagger_eng \
    maxent_ne_chunker \
    maxent_ne_chunker_tab \
    words

# download ML models to avoid doing it at runtime
ARG EMBEDDER_MODEL=multi-qa-mpnet-base-dot-v1 \
    EMBEDDER_DIMS=768
ENV HF_HOME=/app/.cache/huggingface/transformers \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/huggingface/sentence_transformers \
    EMBEDDER_MODEL=$EMBEDDER_MODEL \
    EMBEDDER_DIMS=$EMBEDDER_DIMS
RUN poetry run python -c "from sentence_transformers import SentenceTransformer; \
                          import os; \
                          SentenceTransformer(os.getenv('EMBEDDER_MODEL'))"

# copy project files
COPY . /app

# create non-root runtime user and give ownership of app dir
RUN useradd --create-home --home-dir /nonroot -u 1000 nonroot \
 && chown -R nonroot:nonroot /app
USER nonroot

ENV FLASK_ENV=production
ENV DASH_ENV=production

EXPOSE 8080

CMD [ \
    "poetry", "run", "gunicorn", "app:server", \
    "--bind", "0.0.0.0:8080", \
    "-k", "gthread", \
    "--workers", "1", \
    "--threads", "4", \
    "--timeout", "600", \
    "--preload" \
]
# Local testing:
# CMD ["poetry", "run", "python", "app.py"]
