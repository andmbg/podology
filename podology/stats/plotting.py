"""
Plotting functions
"""

import re
from typing import List
import sqlite3

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
from loguru import logger

from ..search.elasticsearch import TRANSCRIPT_INDEX_NAME, CHUNK_INDEX_NAME
from ..data.EpisodeStore import EpisodeStore
from ..data.Episode import Episode
from ..data.Transcript import Transcript
from ..search.search_classes import ResultSet
from ..stats.preparation import DB_PATH
from ..frontend.utils import colorway, empty_term_hit_fig
from ...config import HITS_PLOT_BINS, EMBEDDER_ARGS


model = SentenceTransformer(EMBEDDER_ARGS["model"])
episode_store = EpisodeStore()
colordict = {i[0]: i[1] for i in colorway}
_transcript_cache = {}


def plot_word_freq(
    term_colid_tuples: List[tuple], es_client: Elasticsearch
) -> go.Figure:
    """Time series plot of word frequencies in the Across Episodes tab.

    Takes part of the term store content where terms are paired with
    color IDs, and an Elasticsearch client. Returns a Plotly Figure.
    """
    df, term_colid_dict = _get_all_episode_term_counts(term_colid_tuples, es_client)

    fig = go.Figure()

    for term, grp in df.groupby("term"):

        fig.add_trace(
            go.Scatter(
                x=grp["pub_date"],
                y=grp["freq1k"],
                mode="lines+markers",
                line=dict(
                    color=colordict[term_colid_dict[term]],
                    width=0.5,
                ),
                marker=dict(
                    color=colordict[term_colid_dict[term]],
                    size=4,
                ),
                name=term,
                showlegend=True,
                customdata=grp[["title", "term", "count", "total", "eid"]],
                hovertemplate=(
                    "<b>%{customdata[1]}</b><br>"
                    "%{y:.2f} words/1000<br>"
                    "%{customdata[2]} occurrences<br>"
                    "%{customdata[3]} total<br><br>"
                    "<i>%{customdata[0]}</i><extra><extra></extra>"
                ),
            )
        )

        fig.update_layout(
            font=dict(size=14),
            plot_bgcolor="rgba(0,0,0, .0)",
            paper_bgcolor="rgba(255,255,255, .0)",
            margin=dict(l=0, r=0, t=0, b=0),
            legend=dict(
                y=0.5,
                yanchor="middle",
            ),
        )

        fig.update_yaxes(
            gridcolor="rgba(0,0,0, .1)",
            title=dict(
                text="Occurrences per 1000",
            ),
            zerolinecolor="rgba(0,0,0, .5)",
            range=[0, df["freq1k"].max() * 1.1],
        )

        fig.update_xaxes(
            showgrid=False,
        )

    return fig


def _get_all_episode_term_counts(
    term_colid_tuples: List[tuple], es_client: Elasticsearch
) -> tuple[pd.DataFrame, dict]:
    """For each term from the terms store, count occurrences in transcripts.

    Return a df with a row for each episode (including zero hits). For use
    by the plotting function below.
    """
    # Filter out semantic search prompts:
    term_colid_tuples = [i for i in term_colid_tuples if i[2] == "term"]

    term_colid_dict = {i[0]: i[1] for i in term_colid_tuples}
    terms: list[str] = list(term_colid_dict.keys())
    eids = [ep.eid for ep in episode_store if ep.transcript.status]

    # Span all episodes & dates for every term:
    df = pd.MultiIndex.from_product([terms, eids], names=["term", "eid"]).to_frame(
        index=False
    )
    df["pub_date"] = df.eid.apply(lambda x: episode_store[x].pub_date)
    df["title"] = df.eid.apply(lambda x: episode_store[x].title)
    df["count"] = 0
    df["colorid"] = pd.NA
    df.set_index(["term", "eid"], inplace=True)

    # Insert counts of hits into the dataframe:
    result_set = ResultSet(
        es_client=es_client,
        index_name=TRANSCRIPT_INDEX_NAME,
        term_colorids=term_colid_tuples,
    )
    for term, hits in result_set.term_hits.items():
        df.loc[(term, slice(None)), "colorid"] = term_colid_dict[term]

        for hit in hits:
            eid = hit["_source"]["eid"]
            df.loc[(term, eid), "count"] += 1

    df.reset_index(inplace=True)

    # Add total word counts of each episode:
    unique_eps = tuple(df.eid.unique())
    unique_eps_query = ",".join(["?"] * len(unique_eps))
    query = (
        f"select eid, count as total from word_count where eid in ({unique_eps_query})"
    )
    word_counts = pd.read_sql(
        query,
        sqlite3.connect(DB_PATH),
        params=unique_eps,
    )

    df = pd.merge(df, word_counts, on="eid", how="left")
    df["freq1k"] = df["count"] / df["total"] * 1000

    df.sort_values("pub_date", inplace=True)

    return df, term_colid_dict


def plot_transcript_hits_es(
    term_colid_tuples: List[list],
    eid: str,
    es_client: Elasticsearch,
    nbins: int = HITS_PLOT_BINS,
) -> go.Figure:
    """Plot the vertical column plot for transcript hits.

    Use elastic to find terms, glean each hit's timing from a transcript word list
    method usage, cached upon first use.
    """
    if not term_colid_tuples:
        return empty_term_hit_fig

    # Remove leading/trailing punctuation/whitespace:
    # TODO Necessary?
    # term_colid_tuples = [
    #     [
    #         re.sub(r"(^\W)|(\W$)", "", term).lower(),
    #         colid,
    #         term_or_prompt
    #     ]
    #     for term, colid, term_or_prompt in term_colid_tuples
    # ]

    # Get episode duration for binning
    episode = EpisodeStore()[eid]
    duration = episode.duration

    # Create time bins
    bin_edges = np.linspace(0, duration, nbins + 1)
    all_bins = np.arange(nbins)
    allbins_df = pd.DataFrame({"bin": all_bins})

    # Search each term in Elasticsearch, index and search method depending on term_or_prompt
    # Target shape per term:
    # list(time_1, time_2, ...)
    for term, colorid, term_or_semantic in term_colid_tuples:

        # Textual search terms:
        if term_or_semantic == "term":
            hit_positions = _search_term_positions(
                es_client, eid, term, term_or_semantic
            )

            # Bin the hit positions
            if hit_positions:
                hit_bins = pd.cut(
                    hit_positions, bins=bin_edges, labels=False, include_lowest=True
                )
                term_counts = (
                    pd.Series(hit_bins).value_counts().reindex(all_bins, fill_value=0)
                )

            else:
                term_counts = pd.Series(0, index=all_bins)

            allbins_df[term] = term_counts

        elif term_or_semantic == "semantic":
            relevances = _chunk_similarities(es_client, episode, term, term_or_semantic)
            allbins_df[term] = relevances["similarity"].values

    allbins_df.set_index("bin", inplace=True)

    # Create plot (same as before)
    return _create_term_hits_plot(allbins_df, term_colid_tuples)


def _create_term_hits_plot(
    allbins_df: pd.DataFrame, term_colid_tuples: list[list]
) -> go.Figure:
    """
    Create a bar plot for the hit counts of each term.

    Args:
        allbins_df: DataFrame with hit counts for each term and bin
        term_colid_dict: Dictionary mapping term names to color IDs

    Returns:
        Plotly Figure object
    """

    semantic_cols = [term for term, _, type in term_colid_tuples if type == "semantic"]
    term_cols = [term for term, _, type in term_colid_tuples if type == "term"]

    maxrange = allbins_df[term_cols].apply(sum, axis=1).max()
    max_similarity = allbins_df[semantic_cols].max().max() if semantic_cols else 0
    min_similarity = allbins_df[semantic_cols].min().min() if semantic_cols else 0

    # allbins_df[semantic_cols] = allbins_df[semantic_cols].apply(np.exp)

    fig = go.Figure()

    # col is at the same time part of the tuples (we surmise):
    for i, col in enumerate(allbins_df.columns):
        term, colid, term_or_prompt = term_colid_tuples[i]

        if term_or_prompt == "term":
            fig.add_trace(
                go.Bar(
                    y=-allbins_df.index,
                    x=allbins_df[col],
                    orientation="h",
                    marker=dict(
                        line_width=0,
                        color=(colordict[colid] if term else "grey"),
                    ),
                    xaxis="x",
                ),
            )

        elif term_or_prompt == "semantic":
            # max_similarity = max(max_similarity, allbins_df[col].max())
            # min_similarity = max(min_similarity, allbins_df[col].min())
            fig.add_trace(
                go.Scatter(
                    y=-allbins_df.index,
                    x=allbins_df[col],
                    mode="lines",
                    line=dict(
                        width=1,
                        color=(colordict[colid] if term else "grey"),
                    ),
                    opacity=.8,
                    xaxis="x2",
                ),
            )

    # Update layout
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        plot_bgcolor="rgba(100,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(
            title=None,
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            range=[-allbins_df.index.max(), 0],
        ),
        xaxis=dict(
            title=None,
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            range=[0, maxrange],
            domain=[0, 1],
        ),
        xaxis2=dict(
            title=None,
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            range=[min_similarity, max_similarity * 1.01 if max_similarity > 0 else 1.0],
            overlaying="x",  # Overlay on the primary x-axis
            domain=[0, 1],
        ),
        barmode="stack",
        bargap=0.02,
    )

    return fig


def _search_term_positions(
    es_client: Elasticsearch, eid: str, term: str, term_or_prompt: str
) -> List[float]:
    """
    Search for term positions using Elasticsearch highlight with positions.
    """
    query = {
        "query": {
            "bool": {
                "must": [{"match": {"eid": eid}}, {"match_phrase": {"text": term}}]
            }
        },
        "highlight": {
            "fields": {
                "text": {
                    "fragment_size": 0,
                    "number_of_fragments": 0,
                    "pre_tags": ["<START>"],
                    "post_tags": ["<END>"],
                }
            }
        },
        "_source": ["start", "text"],
        "size": 1000,  # Adjust as needed
    }
    transcript = _get_transcript_with_elastic_ids(eid)

    try:
        response = es_client.search(index=TRANSCRIPT_INDEX_NAME, body=query)

        positions = []
        for hit in response["hits"]["hits"]:
            if "highlight" in hit:
                hit_elastic_id = hit["_id"]
                hit_transcript_seg = transcript.loc[
                    transcript.elastic_id == hit_elastic_id
                ]
                hit_transcript_seg_len = hit_transcript_seg.shape[0]

                hl_text_words = hit["highlight"]["text"][0].split()
                hit_indices = [
                    min(i, hit_transcript_seg_len - 1)
                    for i, word in enumerate(hl_text_words)
                    if "START" in word
                ]
                hit_times = hit_transcript_seg.iloc[hit_indices].start.values.tolist()
                positions.extend(hit_times)

        return positions

    except Exception as e:
        logger.error(
            f"Error searching term positions for '{term}' in episode {eid}: {e}"
        )
        return []


def _chunk_similarities(
    es_client: Elasticsearch, episode: Episode, term: str, term_or_prompt: str
) -> pd.DataFrame:
    """
    Get relevance scores for a term or prompt using Elasticsearch.
    """
    vector_query = {
        "query": {"bool": {"must": [{"match": {"eid": episode.eid}}]}},
        "knn": {
            "field": "embedding",
            "query_vector": _get_embedding(term),
            "k": 1000,
            "num_candidates": 1000,
            "filter": {"term": {"eid": episode.eid}},
        },
        # "_source": ["eid", "text", "start", "end", "title"]
        "size": 1000,  # Adjust as needed
    }

    response = es_client.search(index=CHUNK_INDEX_NAME, body=vector_query)

    chunk_similarities = [
        {
            "start": hit["_source"]["start"],
            "end": hit["_source"]["end"],
            "similarity_score": hit["_score"],
        }
        for hit in response["hits"]["hits"]
    ]
    relevance_df = pd.DataFrame(chunk_similarities).sort_values("start")
    binned_relevance = bin_relevance_scores(
        relevance_df, ep_duration=episode.duration, n_bins=HITS_PLOT_BINS
    )

    return binned_relevance


def _get_embedding(term: str) -> List[float]:
    """
    Get the embedding vector for a search term using a pre-trained model.
    """
    try:
        embedding = model.encode(term).tolist()
        return embedding
    except Exception as e:
        logger.error(f"Error getting embedding for '{term}': {e}")
        return [0.0] * EMBEDDER_ARGS["dims"]


def _get_transcript_with_elastic_ids(eid: str) -> pd.DataFrame:
    """Prep df in which to find the timing for search terms.

    Cache transcript data with elastic segment IDs to avoid recomputation.
    """
    if eid in _transcript_cache:
        return _transcript_cache[eid]

    transcript = Transcript(EpisodeStore()[eid]).words(
        word_attr=["word", "start"],
        seg_attr=["seg_start", "seg_end"],
    )

    # More efficient string concatenation
    transcript["elastic_id"] = (
        eid
        + "_"
        + transcript["seg_start"].astype(str)
        + "_"
        + transcript["seg_end"].astype(str)
    )

    # Create lookup dict for faster access
    _transcript_cache[eid] = transcript
    return transcript


def bin_relevance_scores(relevance_df, ep_duration, n_bins=500):
    """
    Bin relevance scores into time-based bins, averaging overlapping chunks.
    """
    if relevance_df.empty:
        return pd.DataFrame({"bin_start": [], "bin_end": [], "avg_similarity": []})

    # Get the total time span
    min_time = 0
    max_time = ep_duration

    # Create bin edges
    bin_edges = np.linspace(min_time, max_time, n_bins + 1)

    # Calculate bin centers and create result dataframe

    binned_scores = []

    for i in range(n_bins):
        bin_start = bin_edges[i]
        bin_end = bin_edges[i + 1]

        # Find chunks that overlap with this bin
        overlapping_chunks = relevance_df[
            (relevance_df["start"] < bin_end) & (relevance_df["end"] > bin_start)
        ]

        if len(overlapping_chunks) > 0:
            # Calculate overlap weights for averaging
            weighted_scores = []
            total_weight = 0

            for _, chunk in overlapping_chunks.iterrows():
                # Calculate overlap duration
                overlap_start = max(chunk["start"], bin_start)
                overlap_end = min(chunk["end"], bin_end)
                overlap_duration = overlap_end - overlap_start

                if overlap_duration > 0:
                    # Weight by overlap duration
                    weighted_scores.append(chunk["similarity_score"] * overlap_duration)
                    total_weight += overlap_duration

            if total_weight > 0:
                avg_score = sum(weighted_scores) / total_weight
            else:
                avg_score = overlapping_chunks["similarity_score"].mean()
        else:
            # No chunks in this bin
            avg_score = 0.0

        binned_scores.append(avg_score)

    return pd.DataFrame(
        {
            "similarity": binned_scores,
        }
    )
