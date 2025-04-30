from typing import List

from numpy import zeros
import pandas as pd
import plotly.graph_objects as go
from elasticsearch import Elasticsearch
import sqlite3

from kfsearch.search.setup_es import TRANSCRIPT_INDEX_NAME
from kfsearch.data.models import EpisodeStore
from kfsearch.search.search_classes import ResultSet
from kfsearch.stats.preparation import get_pub_dates, stats_db_path
from kfsearch.frontend.utils import colorway


episode_store = EpisodeStore("Knowledge Fight")
colordict = {i[0]: i[1] for i in colorway}


def plot_word_freq(term_colid_tuples: List[tuple], es_client: Elasticsearch) -> go.Figure:

    term_colid_dict = {i[0]: i[1] for i in term_colid_tuples}
    terms = term_colid_dict.keys()
    eids = [ep.eid for ep in episode_store.episodes(script=True)]
    
    # Span all episodes & dates for every term:
    df = pd.MultiIndex.from_product(
        [terms, eids],
        names=["term", "eid"]
    ).to_frame(index=False)
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
    query = f"select eid, count as total from word_count where eid in ({unique_eps_query})"
    word_counts = pd.read_sql(
        query,
        sqlite3.connect(stats_db_path),
        params=unique_eps,
    )

    df = pd.merge(df, word_counts, on="eid", how="left")
    df["freq1k"] = df["count"] / df["total"] * 1000

    df.sort_values("pub_date", inplace=True)

    fig = go.Figure()

    for term, grp in df.groupby("term"):

        fig.add_trace(
            go.Scatter(
                x=grp["pub_date"],
                y=grp["freq1k"],
                mode="lines+markers",
                line=dict(color=colordict[term_colid_dict[term]]),
                marker=dict(color=colordict[term_colid_dict[term]]),
                name=term,
                showlegend=True,
                customdata=grp[["title", "term", "count", "total"]],
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
                y=.5,
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
