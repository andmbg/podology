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
from podology.data.Transcript import Transcript
from podology.search.search_classes import ResultSet
from podology.stats.preparation import DB_PATH
from podology.frontend.utils import colorway
from config import HITS_PLOT_BINS


episode_store = EpisodeStore()
colordict = {i[0]: i[1] for i in colorway}


def get_all_episode_term_counts(
    term_colid_tuples: List[tuple], es_client: Elasticsearch
) -> tuple[pd.DataFrame, dict]:
    """
    Fetch all episode term counts from Elasticsearch.
    """
    term_colid_dict = {i[0]: i[1] for i in term_colid_tuples}
    terms = term_colid_dict.keys()
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


def plot_word_freq(
    term_colid_tuples: List[tuple], es_client: Elasticsearch
) -> go.Figure:
    """
    Time series plot of word frequencies in the transcripts of all episodes.
    """
    df, term_colid_dict = get_all_episode_term_counts(term_colid_tuples, es_client)

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


def plot_transcript_hits(
    term_colid_tuples: List[tuple], eid: str, nbins: int = HITS_PLOT_BINS
) -> go.Figure:
    """The display next to the transcript scrollbar showing occurrences of
    search terms over time.

    Args:
        term_colid_tuples (List[tuple]): tuples of searchterm--colorid
        eid (str): Episode ID
        nbins (int, optional): Number of vertical bins along the scrollbar.
            Defaults to 10.

    Returns:
        go.Figure
    """
    # Normalize search terms:
    term_colid_dict = {
        re.sub(r"(^\W)|(\W$)|('\w\b)", "", i).lower(): j for i, j in term_colid_tuples
    }
    terms = list(term_colid_dict.keys())

    timed_words = Transcript(EpisodeStore()[eid]).words(regularize=True)
    words_df = pd.DataFrame(timed_words, columns=["word", "start"])

    all_bins = np.arange(nbins)
    binbounds = np.linspace(0, words_df["start"].max(), nbins + 1)
    words_df["bin"] = pd.cut(
        words_df.start, bins=binbounds, labels=False, include_lowest=True
    )

    allbins_df = pd.DataFrame({"bin": all_bins})
    for (term, bin), grp in words_df.loc[words_df.word.isin(terms)].groupby(
        ["word", "bin"]
    ):
        allbins_df.loc[allbins_df.bin.eq(bin), term] = len(grp)

    allbins_df = allbins_df.fillna(0).astype("int").set_index("bin")
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

    allbins_df.to_csv(f"/tmp/debug_transcript_hits_{eid}.csv", sep=",")

    return fig
