import re

import dash_bootstrap_components as dbc
from dash import html
from kfsearch.data.models import EpisodeStore
from kfsearch.frontend.utils import sec_to_time, split_highlight_string

store = EpisodeStore(name="Knowledge Fight")
HLTAG = "bling"


def construct_result_card(
    title: str,
    start_time: str,
    text: list,
    card_id: int,
):
    """
    Put the convoluted code for HTML-construction of result cards here.
    """
    out = dbc.Button(
        dbc.Card(
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                html.P(
                                    title,
                                    className="result-card-location-text text-secondary",
                                ),
                                width=8,
                            ),
                            dbc.Col(
                                html.P(
                                    f"{start_time}, ",
                                    # f"title {hit["_source"].get("episode_title", "--")}, "
                                    # f"text {hit["_source"].get("text", "--")}",
                                    className="result-card-location-text text-secondary text-end",
                                ),
                                width=4,
                            ),
                        ]
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div(
                                    text,
                                    className="result-card-citation-text",
                                ),
                                width=12,
                            ),
                        ]
                    ),
                ],
                className="result-card-body",
            ),
            # className="mb-1",
            # style={"cursor": "pointer"},
        ),
        id={"type": "result-card", "index": card_id},
        class_name="card-button mb-1",
    )

    return out


def get_context(detail_level, sid, eid, highlight):
    """
    Extract the relevant information from the hit dictionary, add information from the
    EpisodeStore and return it as a dict.
    """
    global store, HLTAG
    len_context = {"S": 100, "M": 400, "L": 600}[detail_level]

    episode = store.episodes(eid)[0]
    transcript = episode.get_transcript()["segments"]

    # Split the highlight string into prefix, mid, and suffix:
    (hl_prefix, hl, hl_suffix), len_hl = split_highlight_string(highlight, HLTAG)

    # Add prior segments until prefix length of len_prefix is reached or beginning
    # of transcript:
    cur_id = sid
    while len(hl_prefix) + len_hl / 2 < len_context / 2 and cur_id > 0:
        cur_id -= 1
        hl_prefix = transcript[cur_id]["text"] + " " + hl_prefix
    # Crop prefix to be half the desired context length minus half the highlight length:
    hl_prefix = hl_prefix[-(int((len_context - len_hl) / 2)) :]

    # Analogously for suffix:
    cur_id = sid
    while len(hl_suffix) + len_hl / 2 < len_context / 2 and cur_id < len(transcript):
        cur_id += 1
        hl_suffix += " " + transcript[cur_id]["text"]
    hl_suffix = hl_suffix[: int((len_context - len_hl) / 2)]

    excerpt = [hl_prefix] + hl + [hl_suffix]

    return excerpt


def get_result_cards(hits, detail_level="L"):
    """
    Load the current set of result cards, given
    - the search results (hits)
    - the detail level (S, M, L)
    """
    result_cards = []
    for i, hit in enumerate(hits):
        excerpt = get_context(
            eid=hit["_source"].get("eid"),
            sid=hit["_source"].get("id"),
            detail_level="S",
            highlight=hit["highlight"]["text"][0],
        )

        card = construct_result_card(
            title=hit["_source"].get("episode_title", "No title"),
            start_time=sec_to_time(int(hit["_source"].get("start_time", "--"))),
            text=excerpt,
            card_id=i,
        )
        result_cards.append(card)

    return result_cards


def highlight_to_html_elements(text):
    """
    Turn a string with 1 or more <bling>highlighted</bling> parts into a list of
    Dash HTML elements, where the highlighted parts are wrapped in a Mark element.
    """
    parts = re.split(r"(<bling>.*?</bling>)", text)
    result = []

    for part in parts:
        if part.startswith("<bling>") and part.endswith("</bling>"):
            highlighted = part[7:-8]  # Remove <bling> and </bling>
            result.append(html.Mark(highlighted))
        else:
            result.append(html.Span(part))

    return html.Div(result)
