from collections import namedtuple
from typing import Tuple

from dash import html

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
