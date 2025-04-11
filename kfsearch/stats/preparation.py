import json
from pathlib import Path

import pandas as pd
from loguru import logger

from config import PROJECT_NAME
from kfsearch.data.models import EpisodeStore


stats_folder_path = Path("data") / PROJECT_NAME / "stats"
stats_folder_path.mkdir(parents=True, exist_ok=True)

word_count_path = stats_folder_path / "word_count.parquet"
metadata_path = stats_folder_path / "metadata.parquet"


def ensure_stats_data(episode_store: EpisodeStore):
    """
    There are a bunch of computations that we need to do at indexing time, that take
    too long at runtime. This function is called to compute those stats and store them
    in the stats directory.
    """
    get_metadata(episode_store).to_parquet(metadata_path)
    get_word_count(episode_store).to_parquet(word_count_path)


def get_timerange(episode_store: EpisodeStore) -> tuple:

    pub_dates = [pd.Timestamp(ep.pub_date) for ep in episode_store.episodes()]

    return min(pub_dates), max(pub_dates)


def get_word_count(episode_store: EpisodeStore) -> pd.DataFrame:
    """
    Count the number of words per episode.

    pd.DataFrame:
    - eid (str): The episode ID
    - count (str): The number of words in the episode
    """
    eps_list = []

    for episode in episode_store.episodes(script=True):
        script_path = episode.transcript_path

        if Path(script_path).exists():
            with open(script_path, "r") as f:
                segments = json.load(f)["segments"]
                try:
                    count = sum([len(i["words"]) for i in segments])
                except KeyError:
                    logger.error(f"No words in {script_path} or wrong structure.")
                    count = pd.NA

        else:
            count = pd.NA

        eps_list.append(
            {
                "eid": episode.eid,
                "count": count,
            }
        )

    return pd.DataFrame(eps_list)

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
