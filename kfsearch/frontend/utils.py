from dash import html
import dash_bootstrap_components as dbc

def clickable_tag(index: int, term: str) -> html.Button:
    """
    Generate a clickable tag that removes itself when clicked.

    :param int index: The index of the tag. Used for coloring and for identifying the tag when it comes to removing it.
    :param str term: The content of the tag. Can be several words.
        It needn't be continuous but should be unique.
    """
    return html.Button(
        term,
        id={"type": "remove-term", "index": index},
        className=f"term-item term-color-{index % 8}",
        title=term,
    )