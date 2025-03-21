import re
from collections import defaultdict
from datetime import datetime
from typing import List

import dash_bootstrap_components as dbc
from dash import html

from kfsearch.search.utils import format_time


HLTAG = "bling"


class ResultSet:
    def __init__(self, es_client, episode_store, index_name, search_term, page_size=10):
        self.es_client = es_client
        self.episode_store = episode_store
        self.index_name = index_name
        self.search_term = search_term
        self.page_size = page_size
        self.hits, self.total_hits = self._perform_search()
        self.episodes = self._group_by_episode()
        self.pages: List[ResultsPage] = self._create_pages()

    def _perform_search(self):
        results = self.es_client.search(
            index=self.index_name,
            body={
                "query": {"match_phrase": {"text": self.search_term}},
                "size": 10000,
                "highlight": {
                    "fields": {
                        "text": {
                            "number_of_fragments": 0,
                            "pre_tags": ["<bling>"],
                            "post_tags": ["</bling>"],
                        }
                    }
                },
            },
        )
        hits = results["hits"]["hits"]
        total_hits = results["hits"]["total"]["value"]
        return hits, total_hits

    def _group_by_episode(self):
        episodes = defaultdict(list)
        for hit in self.hits:
            eid = hit["_source"]["eid"]
            episodes[eid].append(hit)
        return episodes

    def _create_pages(self):
        episode_list = list(self.episodes.items())
        pages = []
        for i in range(0, len(episode_list), self.page_size):
            page_episodes = dict(episode_list[i:i + self.page_size])
            pages.append(ResultsPage(page_episodes, self.episode_store))
        return pages

    def get_page(self, page_number):
        if 0 <= page_number < len(self.pages):
            return self.pages[page_number]
        return None


class ResultsPage:
    def __init__(self, episodes, episode_store):
        self.episodes = episodes
        self.episode_store = episode_store
        self.cards = self._create_cards()

    def _create_cards(self):
        return [ResultCard(eid, hits, self.episode_store)
                for eid, hits in self.episodes.items()]


class ResultCard:
    def __init__(self, eid, within_ep_hitlist, episode_store):
        self.episode_store = episode_store
        self.title = within_ep_hitlist[0]["_source"]["episode_title"]
        self.pub_date = within_ep_hitlist[0]["_source"]["pub_date"]
        self.hit_count = len(within_ep_hitlist)
        self.id = eid


    def to_html(self):
        formatted_date = datetime.strptime(self.pub_date, "%Y-%m-%dT%H:%M:%S%z").strftime("%d.%m.%Y")

        return dbc.Button(
            dbc.Card(
                dbc.CardBody(
                    dbc.Row(
                        [
                            dbc.Col(
                                html.P(
                                    formatted_date,
                                    className="text-secondary mb-0 me-1 text-nowrap",
                                ),
                                width="auto",
                                className="text-start fs-6",
                            ),
                            dbc.Col(
                                html.B(
                                    self.title,
                                    className="mb-0 text-truncate text-primary",
                                ),
                            ),
                            dbc.Col(
                                html.P(
                                    f"{self.hit_count} hits",
                                    className="text-secondary mb-0 text-nowrap",
                                ),
                                width="auto",
                                className="text-end",
                            ),
                        ],
                        className="g-0",
                    ),
                    className="py-2",
                ),
            ),
            id={"type": "result-card", "index": self.id},
            class_name="card-button mb-1 w-100",
        )


class ResultContent:
    def __init__(self, text):
        self.text = text

    def to_html_elements(self):
        return highlight_to_html_elements(self.text)


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


# def diarize_transcript(eid, episode_store, search_term) -> list:
#     """
#     Given an episode ID, load the episode transcript and return a list of turns where
#     each turn contains a contiguous list of segments from one speaker.
#     """
#
#     # Pick episode based on eid, then its segment-wise transcript:
#     episode = [i for i in episode_store.episodes() if i.eid == eid][0]
#     segments = episode.get_transcript()["segments"]
#
#     turns = []
#
#     while segments:
#         # Start new turn:
#         turn_segments = []
#         this_speaker = segments[0]["speaker"]
#
#         while segments and segments[0]["speaker"] == this_speaker:
#             # Add segments to this turn while speaker doesn't change:
#             turn_segments.append(segments.pop(0)["text"])
#
#         # Make turn into a paragraph and add to result:
#         turn = html.P(
#             [html.B(this_speaker), ": ", " ".join(turn_segments)],
#             className="this_speake",
#         )
#         turns.append(turn)
#
#     return turns
def diarize_transcript(eid, episode_store, search_term) -> list:
    """
    Create a diarized transcript with highlighted search terms.
    """
    def speaker_class(speaker):
        return f"speaker-{speaker[-2:]}"

    # Pick episode based on eid, then its segment-wise transcript:
    episode = [i for i in episode_store.episodes() if i.eid == eid][0]
    segments = episode.get_transcript()["segments"]

    # Compile search term pattern for case-insensitive matching
    search_term = rf"\b{search_term}\b"
    pattern = re.compile(search_term, re.IGNORECASE)

    turns = []
    while segments:
        turn_segments = []
        this_speaker = segments[0]["speaker"]
        this_start = segments[0]["start"]

        while segments and segments[0]["speaker"] == this_speaker:
            # Highlight search terms in segment text
            text = segments.pop(0)["text"]
            highlighted_text = pattern.sub(lambda m: f"<bling>{m.group()}</bling>", text)
            turn_segments.append(highlighted_text)

        # Convert highlighted text to HTML elements
        highlighted_turn = highlight_to_html_elements(" ".join(turn_segments))
        turn_header = dbc.Row(
            children=[
                dbc.Col([html.B([this_speaker + ":"])], className="text-start text-bf", width=6),
                dbc.Col([format_time(this_start)], className="text-end text-secondary", width=6),
            ],
            className="mt-2"
        )
        turn_body = dbc.Row(
            children=[
                html.Div([highlighted_turn], className=speaker_class(this_speaker))
            ]
        )

        turns.append(turn_header)
        turns.append(turn_body)

    return turns
