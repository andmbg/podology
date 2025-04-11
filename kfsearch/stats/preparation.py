import json
from pathlib import Path

import pandas as pd
from loguru import logger
import sqlite3

from config import PROJECT_NAME
from kfsearch.data.models import EpisodeStore


stats_folder_path = Path("data").resolve() / PROJECT_NAME / "stats"
stats_db_path = stats_folder_path / "stats.db"
stats_folder_path.mkdir(parents=True, exist_ok=True)


def ensure_stats_data(episode_store: EpisodeStore):
    """
    There are a bunch of computations that we need to do at indexing time, that take
    too long at runtime. This function is called to compute those stats and store them
    in the stats directory.
    """
    initialize_stats_db()
    write_all_wordcounts(episode_store)
    # get_metadata(episode_store).to_parquet(metadata_path)


def get_timerange(episode_store: EpisodeStore) -> tuple:

    pub_dates = [pd.Timestamp(ep.pub_date) for ep in episode_store.episodes()]

    return min(pub_dates), max(pub_dates)


def initialize_stats_db():
    logger.info("Initializing stats database")

    with sqlite3.connect(stats_db_path) as conn:
        # Create the word count table if it doesn't exist
        conn.execute("""CREATE TABLE IF NOT EXISTS word_count (
                eid TEXT PRIMARY KEY,
                count INTEGER
            )
        """)


def write_all_wordcounts(episode_store: EpisodeStore):
    """
    Ensure all transcribed episodes are indexed with their word counts.
    """
    logger.info("Initializing word count table")
    with sqlite3.connect(stats_db_path) as conn:

        # Get all indexed episode IDs
        indexed_eids = {row[0] for row in conn.execute("SELECT eid FROM word_count")}

        # Iterate over all episodes and index missing ones
        for episode in episode_store.episodes(script=True):
            if episode.eid not in indexed_eids:
                script_path = episode.transcript_path
                if Path(script_path).exists():
                    with open(script_path, "r") as f:
                        segments = json.load(f)["segments"]
                        word_count = sum(len(segment["words"]) for segment in segments)
                        conn.execute("""
                            INSERT INTO word_count (eid, count)
                            VALUES (?, ?)
                        """, (episode.eid, word_count))


def update_word_count_table(episode):
    """
    Update the word count index for a single episode.
    """
    script_path = episode.transcript_path
    if Path(script_path).exists():
        with open(script_path, "r") as f:
            segments = json.load(f)["segments"]
            word_count = sum(len(segment["words"]) for segment in segments)

        with sqlite3.connect(stats_db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO word_count (eid, count)
                VALUES (?, ?)
            """, (episode.eid, word_count))


def get_metadata(episode_store: EpisodeStore) -> pd.DataFrame:
    """
    Save the metadata of the episodes in a DataFrame.

    pd.DataFrame:
    - eid (str): The episode ID
    - pub_date (str): The publication date of the episode
    - episode_title (str): The title of the episode
    - description (str): The description of the episode
    """
    eps_list = []

    for episode in episode_store.episodes(script=True):
        eps_list.append(
            {
                "eid": episode.eid,
                "pub_date": episode.pub_date,
                "episode_title": episode.title,
                "description": episode.description,
            }
        )

    return pd.DataFrame(eps_list)
