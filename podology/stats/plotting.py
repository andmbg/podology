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
from loguru import logger

from podology.search.elasticsearch import TRANSCRIPT_INDEX_NAME
from podology.data.EpisodeStore import EpisodeStore
from podology.data.Episode import Episode
from podology.data.Transcript import Transcript
from podology.search.search_classes import ResultSet
from podology.stats.preparation import DB_PATH
from podology.frontend.utils import colorway, empty_term_hit_fig
from config import HITS_PLOT_BINS


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
    # Filter to terms only and remove leading/trailing punctuation/whitespace:
    term_colid_dict = {
        re.sub(r"(^\W)|(\W$)", "", i).lower(): j
        for i, j, t in term_colid_tuples
        if t == "term"
    }

    if not term_colid_dict:
        return empty_term_hit_fig

    # Get episode duration for binning
    episode = EpisodeStore()[eid]
    duration = episode.duration

    # Create time bins
    bin_edges = np.linspace(0, duration, nbins + 1)
    all_bins = np.arange(nbins)
    allbins_df = pd.DataFrame({"bin": all_bins})

    # Search each term in Elasticsearch
    # Target shape per term:
    # list(time_1, time_2, ...)
    for term, colorid in term_colid_dict.items():
        hit_positions = _search_term_positions(es_client, eid, term)

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

    allbins_df.set_index("bin", inplace=True)

    # Create plot (same as before)
    return _create_term_hits_plot(allbins_df, term_colid_dict)


def _create_term_hits_plot(
    allbins_df: pd.DataFrame, term_colid_dict: dict
) -> go.Figure:
    """
    Create a bar plot for the hit counts of each term.

    Args:
        allbins_df: DataFrame with hit counts for each term and bin
        term_colid_dict: Dictionary mapping term names to color IDs

    Returns:
        Plotly Figure object
    """
    maxrange = allbins_df.apply(sum, axis=1).max()

    fig = go.Figure()

    for col in allbins_df.columns:
        fig.add_trace(
            go.Bar(
                y=-allbins_df.index,
                x=allbins_df[col],
                orientation="h",
                marker=dict(
                    line_width=0,
                    color=(
                        colordict[term_colid_dict[col]]
                        if col in term_colid_dict
                        else "grey"
                    ),
                ),
            )
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
        ),
        xaxis=dict(
            title=None,
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            range=[0, maxrange],
        ),
        barmode="stack",
        bargap=0.02,
    )

    return fig


def _search_term_positions(
    es_client: Elasticsearch, eid: str, term: str
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
