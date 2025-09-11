from collections import namedtuple
from typing import Tuple

from bs4 import BeautifulSoup
from dash import html
import plotly.graph_objects as go

idcolor = namedtuple("idcolor", ["id", "color"])
colorway = [
    idcolor(id=0, color="#4c72b0"),
    idcolor(id=1, color="#3aba57"),
    idcolor(id=2, color="#c53a5b"),
    idcolor(id=3, color="#8172b3"),
    idcolor(id=4, color="#bfa545"),
    idcolor(id=5, color="#64b5cd"),
    idcolor(id=6, color="#6c4c20"),
    idcolor(id=7, color="#e37c4d"),
    idcolor(id=8, color="#555555"),
    idcolor(id=9, color="#606805"),
]
colorway.reverse()


def clickable_tag(index: int, term_colorid: Tuple[str, int]) -> html.Button:
    """
    Generate a clickable tag that removes itself when clicked.

    :param int index: The index of the tag. Used for coloring and for identifying the tag when it comes to removing it.
    :param str term_colorid: The content of the tag. Can be several words.
        It needn't be continuous but should be unique.
    """
    return html.Button(
        term_colorid[0],
        id={"type": "remove-term", "index": index},
        className=f"term-item term-color-{term_colorid[1]}",
        title=term_colorid[0],
    )


def get_sort_button(term_colorid: Tuple[str, int]) -> html.Button:
    return html.Button(
        "⇩",
        id={"type": "sort-button", "index": term_colorid[1]},
        className=(
            f"m-2 half-circle-highlight highlight-color-{term_colorid[1]} "
            f"term-color-{term_colorid[1]}"
        ),
        title=term_colorid[0],
    )


empty_term_fig = (
    go.Figure()
    .add_annotation(
        text=(
            "Enter at least one search term<br>"
            "to see its distribution over episodes."
        ),
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=20, color="grey"),
    )
    .update_layout(
        plot_bgcolor="rgba(0,0,0, 0)",
        paper_bgcolor="rgba(0,0,0, 0)",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
)

empty_scroll_fig = (
    go.Figure()
    .add_annotation(
        text=(
            "Select an episode<br>"
            "to see its transcript."
        ),
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=20, color="grey"),
    )
    .update_layout(
        plot_bgcolor="rgba(0,0,0, 0)",
        paper_bgcolor="rgba(0,0,0, 0)",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
)
