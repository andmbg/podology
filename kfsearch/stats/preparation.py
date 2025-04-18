import json
from os import name
from pathlib import Path

import pandas as pd
from loguru import logger
import sqlite3

from config import PROJECT_NAME
from kfsearch.data.models import EpisodeStore, Episode, DiarizedTranscript
from kfsearch.stats.nlp import get_wordcloud, get_named_entities, type_proximity


stats_folder_path = Path("data").resolve() / PROJECT_NAME / "stats"
stats_db_path = stats_folder_path / "stats.db"
clouds_path = stats_folder_path / "wordclouds"
stats_folder_path.mkdir(parents=True, exist_ok=True)


"""
This module contains functions to prepare and store statistics for episodes.
First come the ensure-functions, which are to be run at init time, followed
by the functions that they apply to the whole corpus.
"""


def ensure_stats_data(episode_store: EpisodeStore):
    """
    There are a bunch of computations that we need to do at indexing time, that take
    too long at runtime. This function is called to compute those stats and store them
    in the stats directory.
    """
    initialize_stats_db()
    ensure_wordcounts(episode_store)
    # get_metadata(episode_store).to_parquet(metadata_path)
    ensure_named_entity_tokens(episode_store)
    ensure_named_entity_types(episode_store)
    ensure_wordclouds(episode_store)
    ensure_type_proximity(episode_store)


def ensure_wordcounts(episode_store: EpisodeStore):
    """
    Identify all episodes that are missing a word count
    and update the word count table
    """
    with sqlite3.connect(stats_db_path) as conn:

        # Get all indexed episode IDs
        indexed_eids = {row[0] for row in conn.execute("SELECT eid FROM word_count")}

        # Iterate over all episodes and index missing ones
        for episode in episode_store.episodes(script=True):
            if episode.eid not in indexed_eids:
                update_word_count_table(episode)


def ensure_wordclouds(episode_store: EpisodeStore):
    """
    Identify all episodes that are missing a word cloud
    and update the word cloud table
    """
    # Get transcribed episodes that lack a word cloud:
    for episode in episode_store.episodes(script=True):

        if (
            episode.transcript_path
            and not (clouds_path / f"{episode.eid}.png").exists()
        ):
            store_wordcloud(episode)


def ensure_named_entity_tokens(episode_store: EpisodeStore):
    """
    Ensure that the named entity tokens are computed and stored.
    Like all ensure-functions, this is to be run at init time.

    :param episode_store: The episode store containing all episodes.
    :return: None
    """
    with sqlite3.connect(stats_db_path) as conn:

        # Get all indexed episode IDs
        indexed_eids = {
            row[0] for row in conn.execute("SELECT eid FROM named_entity_tokens")
        }

        # Iterate over all episodes and index missing ones
        for episode in episode_store.episodes(script=True):
            if episode.eid not in indexed_eids:
                update_named_entity_tokens(episode)


def ensure_named_entity_types(episode_store: EpisodeStore):
    """
    Ensure that the named entity types are computed and stored.
    Like all ensure-functions, this is to be run at init time.

    :param episode_store: The episode store containing all episodes.
    :return: None
    """
    with sqlite3.connect(stats_db_path) as conn:

        # Get all indexed episode IDs
        indexed_eids = {
            row[0] for row in conn.execute("SELECT eid FROM named_entity_types")
        }

        # Iterate over all episodes and index missing ones
        for episode in episode_store.episodes(script=True):
            if episode.eid not in indexed_eids:
                update_named_entity_types(episode)


def ensure_type_proximity(episode_store: EpisodeStore):
    """
    Ensure that the type proximity data is computed and stored.
    Like all ensure-functions, this is to be run at init time.

    :param episode_store: The episode store containing all episodes.
    :return: None
    """
    with sqlite3.connect(stats_db_path) as conn:

        # Get all indexed episode IDs
        indexed_eids = {
            row[0] for row in conn.execute("SELECT eid FROM type_proximity_episode")
        }

        # Iterate over all episodes and index missing ones
        for episode in episode_store.episodes(script=True):
            if episode.eid not in indexed_eids:
                logger.info(f"Checking {episode.eid} for type proximity")
                update_type_proximity_table(episode)


def get_pub_dates(episode_store: EpisodeStore) -> list:

    return [pd.Timestamp(ep.pub_date) for ep in episode_store.episodes()]


def initialize_stats_db():
    logger.info("Initializing stats database")

    with sqlite3.connect(stats_db_path) as conn:

        # Word count by episode:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS word_count (
                eid TEXT PRIMARY KEY,
                count INTEGER
            );
            """
        )

        # Named entity tokens by episode:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS named_entity_tokens (
                eid TEXT,
                idx INTEGER,
                token TEXT
            );
            """
        )

        # Named entity types by episode:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS named_entity_types (
                eid TEXT,
                type TEXT,
                count INTEGER
            );
            """
        )

        # Type proximity by episode (granularity: term pairs):
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS type_proximity_episode (
                eid TEXT,
                type TEXT,
                other_type TEXT,
                proximity REAL
            );
            """
        )


def update_word_count_table(episode: Episode):
    """
    Update the word count index for a single episode.
    """
    script_path = episode.transcript_path

    if Path(script_path).exists():
        with open(script_path, "r") as f:
            segments = json.load(f)["segments"]
            word_count = sum(len(segment["words"]) for segment in segments)

        with sqlite3.connect(stats_db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO word_count (eid, count)
                VALUES (?, ?)
            """,
                (episode.eid, word_count),
            )


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


def store_wordcloud(episode: Episode):
    """
    Get the wordcloud for a given episode and store it as a png file.
    """
    logger.debug(f"Creating wordcloud for {episode.eid}")

    # Prepare storage path:
    path = clouds_path / f"{episode.eid}.png"
    path.parent.mkdir(parents=True, exist_ok=True)

    # Plain text of transcript without speaker labels:
    diarized_transcript = DiarizedTranscript(episode)
    text = [i["text"] for i in diarized_transcript.to_json()]
    text = " ".join(text)

    fig_cloud = get_wordcloud(text)

    fig_cloud.savefig(path, bbox_inches="tight")


def update_named_entity_tokens(episode: Episode):
    """
    For a given episode, store in the stats database the tokens of named
    entities and their index among NEs. This facilitates type frequency and
    proximity calculations.
    """
    # Skip if this episode is already in this table. Not necessary for
    # the ensure function, but who knows where else we might call this later.
    with sqlite3.connect(stats_db_path) as conn:
        cursor = conn.execute(
            """
            SELECT 1 FROM named_entity_tokens WHERE eid = ? LIMIT 1
            """,
            (episode.eid,),
        )
        if cursor.fetchone():
            return

    # Get the transcript text:
    logger.debug(f"{episode.eid}: Updating named entity tokens")
    transcript = DiarizedTranscript(episode)
    text = [i["text"] for i in transcript.to_json()]
    text = " ".join(text)

    # Get the named entities:
    named_entities = [i[0] for i in get_named_entities(text)]

    # Store the named entities in the database:
    with sqlite3.connect(stats_db_path) as conn:
        for token, index in zip(named_entities, range(len(named_entities))):
            conn.execute(
                """
                INSERT INTO named_entity_tokens (eid, idx, token)
                VALUES (?, ?, ?)
            """,
                (episode.eid, index, token),
            )


def update_named_entity_types(episode: Episode):
    """
    For a given episode, store in the stats database the counts per type
    of named entities. This facilitates type frequency and proximity
    calculations.
    """
    # Skip if this episode is already in this table. Not necessary for
    # the ensure function, but who knows where else we might call this later.
    with sqlite3.connect(stats_db_path) as conn:
        cursor = conn.execute(
            """
            SELECT 1 FROM named_entity_types WHERE eid = ? LIMIT 1
            """,
            (episode.eid,),
        )
        if cursor.fetchone():
            return

    # Get the named entities:
    logger.debug(f"{episode.eid}: Updating named entity types")

    query = f"""
        SELECT token, idx
        FROM named_entity_tokens
        WHERE eid = '{episode.eid}'
    """
    with sqlite3.connect(stats_db_path) as conn:
        nedf = pd.read_sql(sql=query, con=conn)

    nedf = nedf.groupby("token").size().reset_index(name="count")
    nedf["eid"] = episode.eid
    nedf.rename(columns={"token": "type"}, inplace=True)

    with sqlite3.connect(stats_db_path) as conn:
        nedf.to_sql(
            con=conn, if_exists="append", index=False, name="named_entity_types"
        )


def update_type_proximity_table(episode: Episode):
    """
    For a given episode, store in the stats database the pairwise proximity
    scores of named entities.
    """
    # Skip if this episode is already in this table. Not necessary for
    # the ensure function, but who knows where else we might call this later.
    with sqlite3.connect(stats_db_path) as conn:
        cursor = conn.execute(
            """
            SELECT 1 FROM type_proximity_episode WHERE eid = ? LIMIT 1
            """,
            (episode.eid,),
        )
        if cursor.fetchone():
            return

    # Get the named entities:
    logger.debug(f"{episode.eid}: Updating type proximity table")
    query = f"""
        SELECT token, idx
        FROM named_entity_tokens
        WHERE eid = '{episode.eid}'
    """
    named_entities = pd.read_sql(sql=query, con=sqlite3.connect(stats_db_path))
    ne_dict = named_entities.groupby("token")["idx"].apply(list).to_dict()

    # Get the proximity:
    proximity_df = type_proximity(ne_dict)
    proximity_df["eid"] = episode.eid

    # Store the proximity in the database:
    with sqlite3.connect(stats_db_path) as conn:
        proximity_df.to_sql(
            con=conn, if_exists="append", index=False, name="type_proximity_episode"
        )
