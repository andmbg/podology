import sys
import json
from pathlib import Path
import logging

# from flask import Flask
import pandas as pd
from dash import Dash, dcc, html, Input, Output, State, ALL, ctx
import dash_bootstrap_components as dbc

from kfsearch.search.utils import process_highlighted_text, get_para

# import from config relatively, so it remains portable:
dashapp_rootdir = Path(__file__).resolve().parents[1]
sys.path.append(str(dashapp_rootdir))

logging.basicConfig(
    filename=dashapp_rootdir / "logs" / "kfsearch.log",
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


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
                            # match list
                            [
                                html.Div(id="search-results"),
                                dbc.Pagination(
                                    id="pagination",
                                    max_value=5,
                                    first_last=True,
                                ),
                            ],
                            width=6,
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
                            ]
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
        Output("search-results", "children"),
        Output("pagination", "max_value"),
        Output("pagination", "active_page"),
        Input("input", "n_submit"),
        Input("search-button", "n_clicks"),
        Input("pagination", "active_page"),
        State("input", "value"),
    )
    def perform_search(n_submit, n_clicks, active_page, search_term):
        if not ctx.triggered:
            return [], 1, 1

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if trigger_id in ["input", "search-button"]:
            page = 1
        else:
            page = active_page or 1

        if search_term:

            if (n_submit is not None and n_submit > 0) or active_page:
                page = active_page or 1
                results = app.es_client.search(
                    index="poe_index",
                    body={
                        "query": {"match": {"text": search_term}},
                        "from": (page - 1) * 10,
                        "size": 10,
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
                max_pages = -(-total_hits // 10)  # Ceiling division

                result_cards = []
                for i, hit in enumerate(hits):

                    result_cards.append(
                        dbc.Button(
                            dbc.Card(
                                dbc.CardBody(
                                    [
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    html.P(
                                                        hit["_source"].get("title", "No title"),
                                                        className="result-card-location-text text-secondary",
                                                    ),
                                                    width=8,
                                                ),
                                                dbc.Col(
                                                    html.P(
                                                        f"ch. {hit["_source"].get("chapter", "--")}, "
                                                        f"para. {hit["_source"].get("paragraph", "--")}, "
                                                        f"sent. {hit["_source"].get("sentence", "--")}",
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
                                                        process_highlighted_text(
                                                            hit["highlight"]["text"][0]
                                                        ),
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
                        id={"type": "result-card", "index": i},
                        class_name="card-button mb-1",
                        )
                    )

                return result_cards, max_pages, page

        return [], 0, 1

    @app.callback(
        Output("context", "children"),
        Input({"type": "result-card", "index": ALL}, "n_clicks"),
        State("search-results", "children"),
    )
    def display_additional_info(click_timestamps, search_results):
        if not ctx.triggered:
            return "Click on a result card to see more information."
        
        clicked_result = get_para(ctx.triggered_id, search_results, ctx)

        # clicked_result = search_results[clicked_index]['props']['children']['props']['children']
        # clicked_result = cx.triggered
        
        return html.Div([
            clicked_result
            # json.dumps(ctx.triggered)
            # html.H4(clicked_result[0]['props']['children'][0]['props']['children']),
            # html.P(f"Chapter: {clicked_result[0]['props']['children'][1]['props']['children'].split(', ')[0]}"),
            # html.P(f"Paragraph: {clicked_result[0]['props']['children'][1]['props']['children'].split(', ')[1]}"),
            # html.P(f"Sentence: {clicked_result[0]['props']['children'][1]['props']['children'].split(', ')[2]}"),
            # html.Div(clicked_result[1]['props']['children'])
        ])
    