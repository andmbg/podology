from typing import List

import pandas as pd
import plotly.graph_objects as go
from elasticsearch import Elasticsearch

from kfsearch.search.setup_es import TRANSCRIPT_INDEX_NAME
from kfsearch.data.models import EpisodeStore
from kfsearch.search.search_classes import ResultSet
from kfsearch.stats.preparation import metadata_path, word_count_path


meta = pd.read_parquet(metadata_path)
word_count = pd.read_parquet(word_count_path)

episode_store = EpisodeStore("Knowledge Fight")


def plot_word_freq(terms: List[str], es_client: Elasticsearch) -> go.Figure:

    df = pd.DataFrame()

    for term in terms:

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
            }
            for i in result_set.hits
        ])

        df = pd.concat([df, word_df])

    df.pub_date = pd.to_datetime(df.pub_date)
    df = df.groupby(["term", "eid", "pub_date"]).size().reset_index(name="count")
    df = pd.merge(df, word_count.rename(columns={"count": "total"}), on="eid", how="left")
    df["freq1k"] = df["count"] / df["total"] * 1000
    df.sort_values("pub_date", inplace=True)

    fig = go.Figure()

    for term, grp in df.groupby("term"):
        fig.add_trace(
            go.Scatter(
                x=grp["pub_date"],
                y=grp["freq1k"],
                mode="lines",
                name=term,
            )
        )

    return fig
