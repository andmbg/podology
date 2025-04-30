from os import terminal_size
import re
from collections import defaultdict
from datetime import datetime
from typing import List, Union

import dash_bootstrap_components as dbc
from dash import html

from kfsearch.search.utils import format_time, highlight_search_term


HLTAG = "bling"


class ResultSet:
    """
    A class to handle search results from an Elasticsearch index.
    Contains a paged set of hits for the search term in the given index, along with a
    by-episode grouping of the hits.
    """
    def __init__(self, es_client, index_name, term_colorids):
        self.es_client = es_client
        self.index_name = index_name
        self.term_colorids = term_colorids
        self.term_colorid_dict = {k: v for k, v in term_colorids}
        self.term_hits, self.total_hits = self._perform_search()
        self.hits_by_ep = self._group_by_episode()
        self.cards = self._create_cards()

    def _perform_search(self):
        """
        Perform a search for each term individually and store their hits separately.
        Form of self.term_hits:
        {
            "<term1>": [hit1, hit2, ...],
            "<term2>": [hit1, hit2, ...],
            ...
        }
        """
        term_hits = {}
        total_hits = 0

        for term, _ in self.term_colorids:
            results = self.es_client.search(
                index=self.index_name,
                body={
                    "query": {
                        "match_phrase": {"text": term}  # Search for the term as a phrase
                    },
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
            term_hits[term] = results["hits"]["hits"]
            total_hits += results["hits"]["total"]["value"]

        return term_hits, total_hits

    def _group_by_episode(self):
        """
        Return a dict of the form:
        {
          "<eid>": {
            "<term1>": [hit1, hit2, ...],
            "<term2>": ...,
            ...
          }
        }
        """
        episodes = {}
        for term, hits in self.term_hits.items():

            for hit in hits:
                eid = hit["_source"]["eid"]

                if eid not in episodes:
                    episodes[eid] = {
                        "_title": hit["_source"]["episode_title"],
                        "_pub_date": hit["_source"]["pub_date"]
                    }

                if term not in episodes[eid]:
                    episodes[eid][term] = []

                episodes[eid][term].append(hit)

        return episodes

    def _create_cards(self):
        return [
            ResultCard(eid, term_hits_dict, self.term_colorid_dict)
            for eid, term_hits_dict
            in self.hits_by_ep.items()
        ]


class ResultCard:
    def __init__(self, eid, term_hits_dict, term_colorid_dict: dict):
        self.title = term_hits_dict["_title"]
        self.pub_date = term_hits_dict["_pub_date"]
        self.term_nhits = {
            k: len(v) for k, v in term_hits_dict.items()
            if k not in ["_title", "_pub_date"]
        }
        self.term_colorid_dict = term_colorid_dict
        self.id = eid

 
    def to_html(self):
        formatted_date = datetime.strptime(
            self.pub_date,
            "%Y-%m-%dT%H:%M:%S",
        ).strftime("%Y-%m-%d")

        return dbc.Button(
            dbc.Card(
                dbc.CardBody(
                    [
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
                                # dbc.Col(
                                #     html.P(
                                #         f"{self.term_nhits} hits",
                                #         className="text-secondary mb-0 text-nowrap",
                                #     ),
                                #     width="auto",
                                #     className="text-end",
                                # ),
                            ],
                            className="g-0",
                        ),

                        dbc.Row(
                            [
                                html.Button(
                                    i,
                                    className=f"text-secondary hit-count term-color-{self.term_colorid_dict[term]}",
                                )
                            for term, i in self.term_nhits.items()
                            ] if self.term_nhits else [],
                        )
                    ],
                    className="py-2",
                ),
            ),
            id={"type": "result-card", "index": self.id},
            class_name="card-button mb-1 w-100",
        )


def highlight_to_html_elements(text):
    """
    Turn a string with 1 or more <span [...]>highlighted</span> parts into a list of
    Dash HTML elements, where the highlighted parts are wrapped in a Span element.
    """
    parts = re.split(r"(<span .*?>.*?</span>)", text)
    result = []

    for part in parts:
        if part.startswith("<span ") and part.endswith("</span>"):
            match = re.match(r'(<span .*?>)(.*)(</span>)', part)
            if match:
                opening_tag = match.group(1)
                opening_match = re.match(r'.*?="(.*?)"', opening_tag)
                classname = opening_match.group(1) if opening_match else ""
                text = match.group(2)
                result.append(
                    html.Span(
                        children=[text],
                        className=classname,
                    )
                )
        else:
            result.append(html.Span(part))

    return html.Div(result)


def diarize_transcript(eid, episode_store, search_term) -> list:
    """
    Create a diarized transcript with highlighted search terms.
    """
    def speaker_class(speaker):
        return f"speaker-{speaker[-2:]}"

    # Pick episode based on eid, then its segment-wise transcript:
    episode = [i for i in episode_store.episodes() if i.eid == eid][0]
    segments = episode.get_transcript()["segments"]

    # Compile search term_colorid pattern for case-insensitive matching
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
