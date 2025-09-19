from datetime import datetime

import dash_mantine_components as dmc
from dash import html


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
        self.hits_by_ep = self._count_by_episode()
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
                        "match_phrase": {
                            "text": term
                        }  # Search for the term as a phrase
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

    def _count_by_episode(self) -> dict:
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
                        "_title": hit["_source"]["title"],
                        "_pub_date": hit["_source"]["pub_date"],
                    }

                if term not in episodes[eid]:
                    episodes[eid][term] = 0

                episodes[eid][term] += 1

        return episodes

    def _create_cards(self):
        return [
            ResultCard(eid, term_hits_dict, self.term_colorid_dict)
            for eid, term_hits_dict in self.hits_by_ep.items()
        ]


# FIXME: This function is a twin of ResultSet._create_cards(). Looks ugly.
def create_cards(hits_by_ep, term_colorid_dict):
    """
    Twin function to ResultSet._create_cards() to be used in the search page.
    """
    return [
        ResultCard(eid, term_hits_dict, term_colorid_dict)
        for eid, term_hits_dict in hits_by_ep.items()
    ]


class ResultCard:
    """
    A class to represent a single search result card.
    """

    def __init__(self, eid, term_hits_dict, term_colorid_dict: dict):
        self.title = term_hits_dict["_title"]
        self.pub_date = term_hits_dict["_pub_date"]
        self.term_nhits = {
            k: v for k, v in term_hits_dict.items() if k not in ["_title", "_pub_date"]
        }
        self.term_colorid_dict = term_colorid_dict
        self.id = eid

    def to_html(self):
        """
        Create a Dash HTML representation for the result card.
        """
        formatted_date = datetime.strptime(
            self.pub_date,
            "%Y-%m-%dT%H:%M:%S",
        ).strftime("%Y-%m-%d")

        return dmc.Card(
            [
                dmc.Grid(
                    [
                        dmc.GridCol(
                            html.P(
                                formatted_date,
                                className="text-secondary text-nowrap",
                            ),
                            span="auto",
                            className="text-start",
                        ),
                        dmc.GridCol(
                            html.B(
                                self.title,
                                className="text-truncate text-primary",
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
                ),
                dmc.Grid(
                    (
                        [
                            html.Button(
                                i,
                                className=f"text-secondary hit-count term-color-{self.term_colorid_dict[term]}",
                            )
                            for term, i in self.term_nhits.items()
                        ]
                        if self.term_nhits
                        else []
                    ),
                ),
            ],
            id={"type": "result-card", "index": self.id},
            className="card-button",
        )
