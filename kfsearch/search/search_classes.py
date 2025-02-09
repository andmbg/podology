import re

import dash_bootstrap_components as dbc
from dash import html

from kfsearch.frontend.utils import sec_to_time, split_highlight_string
from kfsearch.data.models import EpisodeStore


class ResultSet:
    def __init__(self, es_client, index_name, search_term, page_size=10):
        self.es_client = es_client
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
            pages.append(ResultsPage(self.hits[i : i + self.page_size]))
        return pages

    def get_page(self, page_number):
        if 0 <= page_number < len(self.pages):
            return self.pages[page_number]
        return None


class ResultsPage:
    def __init__(self, hits):
        self.hits = hits
        self.cards = self._create_cards()

    def _create_cards(self):
        return [ResultCard(hit) for hit in self.hits]


class ResultCard:
    def __init__(self, hit):
        self.title = hit["_source"].get("episode_title", "No title")
        self.start_time = sec_to_time(int(hit["_source"].get("start_time", "--")))
        self.text = self._get_context(hit)
        self.id = hit["_source"].get("id")

    def _get_context(self, hit):

        def get_context(detail_level, sid, eid, highlight):
            """
            Extract the relevant information from the hit dictionary, add information from the
            EpisodeStore and return it as a dict.

            :param str detail_level: one of S, M, L; amount of context to deliver
            :param int sid: segment ID: count within episode
            :param str eid: episode ID (5-char hash)
            :param str highlight: highlighted search hit; hl is marked by custom tag
            """
            global store, HLTAG
            len_context = {"S": 100, "M": 400, "L": 600}[detail_level]

            episode = [i for i in store.episodes() if i.eid == eid][0]
            segments = episode.get_transcript()["segments"]

            # Split the highlight string into prefix, mid, and suffix:
            (hl_prefix, hl, hl_suffix), len_hl = split_highlight_string(
                highlight, HLTAG
            )

            # Add prior segments until prefix length of len_prefix is reached or beginning
            # of transcript:
            cur_id = sid
            while len(hl_prefix) + len_hl / 2 < len_context / 2 and cur_id > 0:
                cur_id -= 1
                hl_prefix = segments[cur_id]["text"] + " " + hl_prefix
            # Crop prefix to be half the desired context length minus half the highlight length:
            hl_prefix = hl_prefix[-(int((len_context - len_hl) / 2)) :]

            # Analogously for suffix:
            cur_id = sid
            while len(hl_suffix) + len_hl / 2 < len_context / 2 and cur_id < len(
                segments
            ):
                cur_id += 1
                hl_suffix += " " + segments[cur_id]["text"]
            hl_suffix = hl_suffix[: int((len_context - len_hl) / 2)]

            excerpt = [hl_prefix] + hl + [hl_suffix]

            return excerpt

        excerpt = get_context(
            eid=hit["_source"].get("eid"),
            sid=hit["_source"].get("id"),
            detail_level="L",
            highlight=hit["highlight"]["text"][0],
        )
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
                                        self.text,
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


def diarize_transcript(eid) -> list:
    """
    Given an episode ID, load the episode transcript and return a list of turns where
    each turn contains a contiguous list of segments from one speaker.
    """
    global store, HLTAG

    # Pick episode based on eid, then its segment-wise transcript:
    episode = [i for i in store.episodes() if i.eid == eid][0]
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
            [html.B(this_speaker), " ".join(turn_segments)], className="this_speake"
        )
        turns.append(turn)

    return turns


HLTAG = "bling"
store = EpisodeStore(name="Knowledge Fight")
