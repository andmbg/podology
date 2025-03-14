import re

import dash_bootstrap_components as dbc
from dash import html

from kfsearch.frontend.utils import sec_to_time, split_highlight_string


HLTAG = "bling"


class ResultSet:
    def __init__(self, es_client, episode_store, index_name, search_term, page_size=10):
        self.es_client = es_client
        self.episode_store = episode_store
        self.index_name = index_name
        self.search_term = search_term
        self.page_size = page_size
        self.hits, self.total_hits = self._perform_search()
        self.pages = self._create_pages()

    def _perform_search(self):
        results = self.es_client.search(
            index=self.index_name,
            body={
                "query": {"match": {"text": self.search_term}},
                "size": 10000,  # Adjust the size as needed
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

    def _create_pages(self):
        pages = []
        for i in range(0, len(self.hits), self.page_size):
            pages.append(
                ResultsPage(
                    self.hits[i : i + self.page_size],
                    self.episode_store,
                    hltag=HLTAG,
                )
            )
        return pages

    def get_page(self, page_number):
        if 0 <= page_number < len(self.pages):
            return self.pages[page_number]
        return None


class ResultsPage:
    def __init__(self, hits, episode_store, hltag):
        self.hits = hits
        self.episode_store = episode_store
        self.hltag = hltag
        self.cards = self._create_cards()

    def _create_cards(self):
        return [ResultCard(hit, self.episode_store, self.hltag) for hit in self.hits]


class ResultCard:
    def __init__(self, hit, episode_store, hltag):
        self.episode_store = episode_store
        self.title = hit["_source"].get("episode_title", "No title")
        self.start_time = sec_to_time(int(hit["_source"].get("start_time", "--")))
        self.content = self._get_context(hit, hltag)
        self.id = hit["_source"].get("id")

    def _get_context(self, hit, hltag):
        """
        Return a context string for a hit in the transcript.
        """
        eid = hit["_source"].get("eid")
        sid = hit["_source"].get("id")
        detail_level = "M"
        highlight = hit["highlight"]["text"][0]
        len_context = {"S": 100, "M": 300, "L": 600}[detail_level]

        episode = [i for i in self.episode_store.episodes() if i.eid == eid][0]
        segments = episode.get_transcript()["segments"]

        # Split the highlight string into prefix, mid, and suffix:
        (hl_prefix, hl, hl_suffix), len_hl = split_highlight_string(highlight, hltag)

        # Add prior segments until desired prefix length is reached or beginning
        # of transcript:
        cur_id = sid
        while len(hl_prefix) + len_hl / 2 < len_context / 2 and cur_id > 0:
            cur_id -= 1
            hl_prefix = segments[cur_id]["text"] + " " + hl_prefix
        # Crop prefix to be half the desired context length minus half the highlight length:
        hl_prefix = hl_prefix[-(int((len_context - len_hl) / 2)) :]

        # Analogously for suffix:
        cur_id = sid
        while (
            len(hl_suffix) + len_hl / 2 < len_context / 2 and cur_id < len(segments) - 1
        ):
            cur_id += 1
            hl_suffix += " " + segments[cur_id]["text"]
        hl_suffix = hl_suffix[: int((len_context - len_hl) / 2)]

        excerpt = [hl_prefix] + hl + [hl_suffix]

        return excerpt

    def to_html(self):
        return dbc.Button(
            dbc.Card(
                dbc.CardBody(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.P(
                                        self.title,
                                        className="result-card-location-text text-secondary",
                                    ),
                                    width=8,
                                ),
                                dbc.Col(
                                    html.P(
                                        f"{self.start_time}, ",
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
                                        self.content,
                                        className="result-card-citation-text",
                                    ),
                                    width=12,
                                ),
                            ]
                        ),
                    ],
                    className="result-card-body",
                ),
            ),
            id={"type": "result-card", "index": self.id},
            class_name="card-button mb-1",
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


def diarize_transcript(eid, episode_store) -> list:
    """
    Given an episode ID, load the episode transcript and return a list of turns where
    each turn contains a contiguous list of segments from one speaker.
    """

    # Pick episode based on eid, then its segment-wise transcript:
    episode = [i for i in episode_store.episodes() if i.eid == eid][0]
    segments = episode.get_transcript()["segments"]

    turns = []

    while segments:
        # Start new turn:
        turn_segments = []
        this_speaker = segments[0]["speaker"]

        while segments and segments[0]["speaker"] == this_speaker:
            # Add segments to this turn while speaker doesn't change:
            turn_segments.append(segments.pop(0)["text"])

        # Make turn into a paragraph and add to result:
        turn = html.P(
            [html.B(this_speaker), ": ", " ".join(turn_segments)],
            className="this_speake",
        )
        turns.append(turn)

    return turns
