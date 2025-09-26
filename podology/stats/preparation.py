"""
This module contains functions to prepare and store statistics for episodes.
First come the ensure-functions, which are to be run at init time, followed
by the functions that they apply to the whole corpus.
"""

# pylint: disable=W1514
import os
import json
from pathlib import Path
from typing import Generator, List, Optional
import multiprocessing
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from podology.data.EpisodeStore import EpisodeStore

import pandas as pd
from loguru import logger
from redis import Redis
import requests

from config import CHUNKS_DIR, DB_PATH, WORDCLOUD_DIR, TRANSCRIPT_DIR, EMBEDDER_ARGS
from podology.data.Episode import Episode, Status
from podology.data.Transcript import Transcript
from podology.stats.nlp import (
    type_proximity,
    get_wordcloud,
    timed_named_entity_tokens,
)
from podology.search.elasticsearch import index_segments, setup_elasticsearch_indices


def post_process_pipeline(
    episode_store: "EpisodeStore", episodes: Optional[List[Episode]] = None
):
    """
    Run analysis pipeline on one, some or all transcribed episodes.

    :param episode_store: The episode store containing all episodes.
    :param eid: The episode ID or list of episode IDs to process. Default is "all", which
      is translated to all episodes that have a transcript.
    :return: None
    """
    # Deal with eid parameter:
    if episodes is None:
        initialize_stats_db()
        episodes = [ep for ep in episode_store if ep.transcript.status]

    setup_elasticsearch_indices()
    index_segments(episodes)
    store_chunk_embeddings(episodes)
    get_word_counts(episodes)
    store_wordclouds(episodes)
    store_timed_named_entities(episodes)
    store_named_entity_types(episodes)
    store_type_proximity(episodes)  # depends on store_timed_named_entities()

    for episode in episodes:
        episode_store.add_or_update(episode)


def get_word_counts(episodes: List[Episode]):
    """
    Add an entry to the word_count table for each given episode.
    Exclude episodes that are not transcribed or already have a word count entry.

    :param episodes: List of episodes to process.
    :return: None
    """
    # Filter: only do word counts for transcribed episodes...
    # ... that are NOT already in the word_count table:
    with sqlite3.connect(DB_PATH) as conn:
        sqlout = conn.execute("select eid from word_count").fetchall()
        eids_in_db = {i[0] for i in sqlout}
    ep_to_do = [ep for ep in episodes if ep.eid not in eids_in_db]

    # Parallelize the loop using multiprocessing
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        pool.map(word_count_worker, ep_to_do)


def word_count_worker(episode: Episode):
    """Individual function used in multiprocessing function get_wordcounts.

    Reads the transcript of `episode`, counts words, and inserts the count
    into the `word_count` table in the stats database.

    :param episode: The episode to process.
    :return: None (side effect only)
    """
    if episode.transcript.status:
        script_path = TRANSCRIPT_DIR / f"{episode.eid}.json"

        try:
            with open(script_path, "r") as f:
                segments = json.load(f)["segments"]
                word_count = sum(len(segment["words"]) for segment in segments)

            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO word_count (eid, count)
                    VALUES (?, ?)
                    """,
                    (episode.eid, word_count),
                )
            logger.debug(f"{episode.eid}: Stored word count")

        except FileNotFoundError:
            logger.error(
                f"Transcript file not found for episode {episode.eid}. Cannot update word count."
            )


def store_wordclouds(episodes: List[Episode]):
    """
    Create a png word cloud file for each given episode.
    Exclude episodes that are not transcribed or already have a word cloud file.

    :param episodes: List of episodes to process.
    :return: None
    """
    # Filter: only do word clouds for transcribed episodes without a cloud png:
    transcribed_episodes = [ep for ep in episodes if ep.transcript.status]

    ep_to_do = [
        episode
        for episode in transcribed_episodes
        if not (WORDCLOUD_DIR / f"{episode.eid}.png").exists()
    ]

    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        pool.map(wordcloud_worker, ep_to_do)

    for episode in ep_to_do:
        # Update the episode's wordcloud status in db:
        episode.transcript.wcstatus = Status.DONE
        logger.debug(f"{episode.eid}: Word cloud stored")


def wordcloud_worker(episode: Episode):
    """Get wordcloud from nlp module, store it...

    ...both in the data directory of the current podcast and in the assets directory
    of the podology package. The latter is for use in the web app.

    Args:
        episode (Episode): The episode for which to create the word cloud.
    """
    path = WORDCLOUD_DIR / f"{episode.eid}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = get_wordcloud(episode)
    fig.savefig(path, bbox_inches="tight", dpi=300)

    wc_assets_dir = Path.cwd() / "podology" / "assets" / "wordclouds"
    wc_assets_dir.mkdir(parents=True, exist_ok=True)
    dest_path = wc_assets_dir / f"{episode.eid}.png"
    dest_path.write_bytes(path.read_bytes())

    episode.transcript.wcstatus = Status.DONE


def store_named_entity_types(episodes: List[Episode]):
    """
    For each given episode, store in the stats database the counts per type
    of named entity. This facilitates type frequency calculations.

    :param episode_store: The episode store containing all episodes.
    :return: None
    """
    with sqlite3.connect(DB_PATH) as conn:

        # Get all indexed episode IDs
        indexed_eids = {
            row[0] for row in conn.execute("SELECT eid FROM named_entity_types")
        }

    ep_to_do = [
        ep for ep in episodes if ep.transcript.status and ep.eid not in indexed_eids
    ]

    # Iterate over all episodes and index missing ones
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        pool.map(nament_types_worker, ep_to_do)


def nament_types_worker(episode: Episode):
    """
    Individual function used in multiprocessing function store_named_entity_types.
    """
    # Get the named entities:
    logger.debug(f"{episode.eid}: Storing named entity types")

    query = f"""
        SELECT token, timestamp
        FROM named_entity_tokens
        WHERE eid = '{episode.eid}'
    """
    with sqlite3.connect(DB_PATH) as conn:
        nedf = pd.read_sql(sql=query, con=conn)

    nedf = nedf.groupby("token").size().reset_index(name="count")
    nedf["eid"] = episode.eid
    nedf.rename(columns={"token": "type"}, inplace=True)

    with sqlite3.connect(DB_PATH) as conn:
        nedf.to_sql(
            con=conn, if_exists="append", index=False, name="named_entity_types"
        )


def store_type_proximity(episodes: List[Episode]):
    """
    Ensure that the type proximity data is computed and stored.
    Like all ensure-functions, this is to be run at init time.

    :param episode_store: The episode store containing all episodes.
    :return: None
    """
    with sqlite3.connect(DB_PATH) as conn:

        # eids where [v] NEs indexed & [ ] proximities indexed:
        ep_to_do = [
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT eid FROM named_entity_tokens "
                "WHERE eid NOT IN (SELECT eid FROM type_proximity_episode)"
            )
        ]

    # Iterate over all episodes and index missing ones
    with multiprocessing.Pool(
        # TODO allowing more processes leads to sqlite lock errors.
        processes=2  # multiprocessing.cpu_count()
    ) as pool:
        pool.map(type_proximity_worker, ep_to_do)


def type_proximity_worker(eid: str):
    """
    For a given episode, store in the stats database the pairwise proximity
    scores of its named entities.
    """
    # Skip if this episode is already in this table. Not necessary for
    # the ensure function, but who knows where else we might call this later.
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            SELECT 1 FROM type_proximity_episode WHERE eid = ? LIMIT 1
            """,
            (eid,),
        )
        if cursor.fetchone():
            return

    # Get the named entities:
    logger.debug(f"{eid}: Updating type proximity table")
    query = f"""
        SELECT token, timestamp
        FROM named_entity_tokens
        WHERE eid = '{eid}'
    """
    named_entities = pd.read_sql(sql=query, con=sqlite3.connect(DB_PATH))
    ne_dict = named_entities.groupby("token")["timestamp"].apply(list).to_dict()

    # Get the proximity:
    proximity_df = type_proximity(ne_dict)
    proximity_df["eid"] = eid

    # Store the proximity in the database:
    with sqlite3.connect(DB_PATH) as conn:
        proximity_df.to_sql(
            con=conn, if_exists="append", index=False, name="type_proximity_episode"
        )


def store_timed_named_entities(episodes: List[Episode]):
    """
    Store named entities for each given episode along with their word index.
    This is for the experimental dynamic word cloud.

    :param episodes: List of episodes to process.
    """
    # Get ID of all episodes with named entity tokens:
    with sqlite3.connect(DB_PATH) as conn:
        indexed_eids = {
            row[0] for row in conn.execute("SELECT eid FROM named_entity_tokens")
        }
    ep_to_do = [
        ep for ep in episodes if ep.transcript.status and ep.eid not in indexed_eids
    ]

    for ep in ep_to_do:
        logger.debug(f"{ep.eid}: Storing timestamped named entity tokens")

        tne = timed_named_entity_tokens(Transcript(ep))

        with sqlite3.connect(DB_PATH) as conn:
            for token in tne:
                entity_name, ts = token
                conn.execute(
                    """
                    INSERT INTO named_entity_tokens (eid, timestamp, token)
                    VALUES (?, ?, ?)
                    """,
                    (ep.eid, ts, entity_name),
                )


def initialize_stats_db():
    """
    Initialize the SQLite database for storing statistics.
    """
    logger.info("Initializing stats database")

    with sqlite3.connect(DB_PATH) as conn:

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
                timestamp FLOAT,
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


def store_chunk_embeddings(episodes: List[Episode]):
    """Store chunk embeddings for the given episodes.

    Args:
        episodes (List[Episode]): List of episodes to process.

    Raises:
        RuntimeError: If there is an error while processing episodes.

    Returns:
        None
    """
    # Identify episodes without chunk embeddings indexed:
    ep_to_do = [
        ep
        for ep in episodes
        if ep.transcript.status
        and not Path(CHUNKS_DIR / f"{ep.eid}_chunks.json").exists()
    ]

    for episode in ep_to_do:
        logger.debug(f"{episode.eid}: Getting chunk embeddings from WhisperX service")

        transcript = None
        chunks = None

        try:
            transcript = Transcript(episode)
            chunks = transcript.chunks(
                attrs=["start", "end", "eid", "title", "pub_date"]
            ).reset_index().to_dict("records")

            headers = {
                "Authorization": f"Bearer {os.getenv('API_TOKEN')}",
                "Content-Type": "application/json",
            }
            response = None
            try:
                response = requests.post(
                    f"{EMBEDDER_ARGS['url']}/embed",
                    json={"chunks": chunks},
                    headers=headers,
                    timeout=1800,
                    stream=True,  # Stream the response
                )

                if response.status_code != 200:
                    raise RuntimeError(
                        f"WhisperX service failed with status {response.status_code}: {response.text}"
                    )

                # Stream directly to file instead of loading into memory
                chunk_path = CHUNKS_DIR / f"{episode.eid}_chunks.json"
                with open(chunk_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

            finally:
                if response:
                    response.close()  # Explicitly close the response

        finally:
            # Explicit cleanup
            del transcript
            del chunks
            import gc

            gc.collect()
