import re

import dash_bootstrap_components as dbc
from dash import html
from kfsearch.data.models import EpisodeStore
from kfsearch.frontend.utils import sec_to_time

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
    len_prefix = len_suffix = {"S": 30, "M": 40, "L": 200}[detail_level]

    excerpt = "lorem <bling>ipsum</bling> dolor sit amet"

    episode = store.episodes(eid)[0]
    transcript = episode.get_transcript()["segments"]

    hl_prefix = highlight.split(f"<{HLTAG}>")[0]
    hl = highlight.split(f"<{HLTAG}>")[1].split(f"</{HLTAG}>")[0]
    hl_suffix = highlight.split(f"</{HLTAG}>")[1]

    # Add prior segments until prefix length of len_prefix is reached or beginning
    # of transcript:
    cur_id = sid
    while len(hl_prefix) < len_prefix and cur_id > 0:
        cur_id -= 1
        hl_prefix = transcript[cur_id]["text"] + " " + hl_prefix
    hl_prefix = hl_prefix[-len_prefix:]

    # Same for suffix:
    cur_id = sid
    while len(hl_suffix) < len_suffix and cur_id < len(transcript):
        cur_id += 1
        hl_suffix += " " + transcript[cur_id]["text"]
    hl_suffix = hl_suffix[:len_suffix]

    excerpt = [html.B(hl_prefix), html.Mark(hl), html.I(hl_suffix)]

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
            detail_level="L",
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


def process_highlighted_text(text):
    parts = re.split(r"(<bling>.*?</bling>)", text)
    result = []

    for part in parts:
        if part.startswith("<bling>") and part.endswith("</bling>"):
            highlighted = part[7:-8]  # Remove <bling> and </bling>
            result.append(html.Mark(highlighted))
        else:
            result.append(html.Span(part))

    return html.Div(result)
