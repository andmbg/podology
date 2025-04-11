from typing import List

import pandas as pd
import plotly.graph_objects as go
from elasticsearch import Elasticsearch

from kfsearch.search.setup_es import TRANSCRIPT_INDEX_NAME
from kfsearch.data.models import EpisodeStore
from kfsearch.search.search_classes import ResultSet
from kfsearch.stats.preparation import metadata_path, word_count_path, get_timerange
from kfsearch.frontend.utils import colorway


meta = pd.read_parquet(metadata_path)
word_count = pd.read_parquet(word_count_path)

episode_store = EpisodeStore("Knowledge Fight")
colordict = {i[0]: i[1] for i in colorway}
timerange = get_timerange(episode_store)


def plot_word_freq(term_colid_tuples: List[tuple], es_client: Elasticsearch) -> go.Figure:

    df = pd.DataFrame()
    term_colid_dict = {i[0]: i[1] for i in term_colid_tuples}

    for term, _ in term_colid_tuples:

        result_set = ResultSet(
            es_client=es_client,
            episode_store=episode_store,
            index_name=TRANSCRIPT_INDEX_NAME,
            search_term=term,
            page_size=10,
        )

        word_df = pd.DataFrame([
            {
                "term": term,
                "eid": i["_source"]["eid"],
                "pub_date": i["_source"]["pub_date"],
                "title": i["_source"]["episode_title"],
            }
            for i in result_set.hits
        ])

        df = pd.concat([df, word_df])

    df.pub_date = pd.to_datetime(df.pub_date)
    df = df.groupby(["term", "eid", "pub_date", "title"]).size().reset_index(name="count")
    df = pd.merge(df, word_count.rename(columns={"count": "total"}), on="eid", how="left")
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
                customdata=grp[["title", "term"]],
                hovertemplate="<b>%{customdata[1]}</b><br>%{y:.2f} words/1000<br>%{customdata[0]}"
            )
        )

        fig.update_layout(
            font=dict(size=14),
            plot_bgcolor="rgba(0,0,0, 0)",
            paper_bgcolor="rgba(0,0,0, .025)",
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
            )
        )

        fig.update_xaxes(
            showgrid=False,
            range=[timerange[0], timerange[1]],
        )

    return fig
