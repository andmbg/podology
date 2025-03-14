import sys
from pathlib import Path

import json
from dash import Dash, dcc, html, Input, Output, State, ALL, ctx
import dash_bootstrap_components as dbc

from kfsearch.data.models import EpisodeStore, Episode
from kfsearch.search.utils import get_para
from kfsearch.search.search_classes import ResultSet, ResultsPage, diarize_transcript
from kfsearch.search.setup_es import INDEX_NAME

# # import from config relatively, so it remains portable:
# dashapp_rootdir = Path(__file__).resolve().parents[1]
# sys.path.append(str(dashapp_rootdir))
episode_store = EpisodeStore(name="Knowledge Fight")


def init_dashboard(flask_app, route, es_client):

    app = Dash(
        __name__,
        server=flask_app,
        routes_pathname_prefix=route,
        # relevant for standalone launch, not used by main flask app:
        external_stylesheets=[dbc.themes.FLATLY],
    )

    app.es_client = es_client

    #
    #  ____________
    # | Search tab |
    #  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
    searchtab = dbc.Card(
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        # search input
                        dbc.Col(
                            dbc.Input(
                                id="input",
                                placeholder="Enter a search term...",
                                type="text",
                            ),
                            xs=10,
                            md=5,
                        ),
                        dbc.Col(
                            dbc.Button(
                                "Search",
                                id="search-button",
                                n_clicks=0,
                            ),
                            xs=2,
                            md=1,
                        ),
                    ],
                    justify="center",
                    className="mt-5",
                ),
                dbc.Row(
                    # results
                    [
                        dbc.Col(
                            [
                                html.Div(id="transcript-hits"),
                            ],
                            width=5,
                        ),
                        dbc.Col(
                            # match list
                            [
                                html.Div(id="episode-hits"),
                                dbc.Pagination(
                                    id="pagination",
                                    max_value=5,
                                    first_last=True,
                                ),
                            ],
                            width=5,
                        ),
                        dbc.Col(
                            # result information
                            [
                                dbc.Row(
                                    # context
                                    dbc.Col(
                                        [
                                            html.Div(id="context"),
                                        ],
                                    )
                                ),
                                dbc.Row(
                                    # episode info
                                ),
                            ],
                            width=2,
                        ),
                    ],
                    className="mt-3",
                ),
            ]
        ),
        className="mt-3",
    )

    app.layout = html.Div(
        dbc.Container(
            # dbc.Row(
            #     dbc.Col(
            [
                dbc.Tabs(
                    [
                        dbc.Tab(searchtab, label="Search"),
                        dbc.Tab(
                            "This tab is under construction",
                            label="Episodes",
                            disabled=True,
                        ),
                        dbc.Tab(
                            "This tab is under construction",
                            label="The Cast",
                            disabled=True,
                        ),
                        dbc.Tab(
                            "This tab is under construction",
                            label="Associations",
                            disabled=True,
                        ),
                    ]
                )
            ]
            #     )
            # )
        )
    )

    init_callbacks(app)

    return app  # .server


def init_callbacks(app):

    # @app.callback(
    #     Output("search-results", "children"),
    #     Input("search-button", "n_clicks"),
    #     State("search-input", "value"),
    # )
    # def perform_search(n_clicks, search_term):
    #     if n_clicks > 0 and search_term:
    #         results = app.es_client.search(
    #             index="poe_index", body={"query": {"match": {"text": search_term}}}
    #         )

    #         hits = results["hits"]["hits"]
    #         return [html.Div(f"Result: {hit['_source']}") for hit in hits]

    #     return "Enter a search term and click 'Search'"
    @app.callback(
        Output("episode-hits", "children"),
        Output("transcript-hits", "children"),
        Output("pagination", "max_value"),
        Output("pagination", "active_page"),
        Input("input", "n_submit"),
        Input("search-button", "n_clicks"),
        Input({"type": "result-card", "index": ALL}, "n_clicks"),
        Input("pagination", "active_page"),
        State("input", "value"),
    )
    def perform_search(n_submit, src_nclicks, card_nclicks, active_page, search_term):
        if not ctx.triggered:
            return [], [], 1, 1

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if trigger_id in ["input", "search-button"]:
            page = 1
        else:
            page = active_page or 1

        if search_term:

            if (n_submit is not None and n_submit > 0) or active_page:
                page = active_page or 1

                result_set = ResultSet(
                    es_client=app.es_client,
                    episode_store=episode_store,
                    index_name=INDEX_NAME,
                    search_term=search_term,
                    page_size=10,
                )

                this_page = result_set.get_page(page - 1)
                if this_page is None:
                    return [], [], 1, 1

                this_page_hits = this_page.hits
                total_hits = result_set.total_hits
                max_pages = -(-total_hits // 10)  # Ceiling division

                results_page = ResultsPage(this_page_hits, episode_store, hltag="bling")
                result_cards = [c.to_html() for c in results_page.cards]

                diarized_transcript = []

                if "result-card" in trigger_id:
                    card_index = int(json.loads(trigger_id)["index"])
                    episode_id = [
                        i for i in this_page_hits if i["_source"]["id"] == card_index
                    ][0]["_source"]["eid"]
                    episode = [
                        i for i in episode_store.episodes() if i.eid == episode_id
                    ][0]

                    diarized_transcript = diarize_transcript(
                        eid=episode_id,
                        episode_store=episode_store,
                    )

                return result_cards, diarized_transcript, max_pages, page

        return [], [], 0, 1
