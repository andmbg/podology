from dash import html

tag_colorway = [
    "#4c72b0"
    "#3aba57"
    "#c53a5b"
    "#8172b3"
    "#bfa545"
    "#64b5cd"
    "#6c4c20"
    "#e37c4d"
    "#555555"
    "#606805"
]

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

