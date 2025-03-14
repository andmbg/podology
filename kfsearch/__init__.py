import sys
from pathlib import Path

import json
from dash import Dash, dcc, html, Input, Output, State, ALL, ctx
import dash_bootstrap_components as dbc

from kfsearch.data.models import EpisodeStore, Episode
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
        external_stylesheets=[dbc.themes.CERULEAN],
    )

    app.es_client = es_client

    #
    #  ____________
    # | Browse tab |
    #  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
    browse_tab = dbc.Card(
        dbc.CardBody(
            [
                # Input (search field)
                dbc.Row(
                    [
                        dbc.Col(width=4),
                        dbc.Col(
                            [
                                dbc.Input(
                                    id="input",
                                    type="text",
                                    placeholder="Enter search term",
                                    debounce=True,
                                ),
                            ],
                            width=4,
                        ),
                        dbc.Col(
                            [
                                dbc.Button("Search", id="search-button", color="primary"),
                            ],
                            width=1,
                        ),
                    ],
                    className="mt-3",
                ),
                # Output
                dbc.Row(
                    children=[

                        # Transcript of selected episode
                        dbc.Col(
                            children=[
                                html.Div(
                                    id="this-episode-metadata",
                                    children = [
                                        dbc.Row([
                                            dbc.Col(
                                                html.H5(html.B("Title"), id="episode-title", className="mb-0 text-truncate"),
                                                width=12,
                                            ),
                                        ]),
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    html.P("1970-01-01", id="episode-date", className="text-muted mb-0"),
                                                    width=6,
                                                ),
                                                dbc.Col(
                                                    html.P(
                                                        [
                                                            html.Span("Ep. 100", id="episode-number"),
                                                            " • ",
                                                            html.Span("1:21:49", id="episode-duration"),
                                                        ],
                                                        className="text-muted mb-0 text-end",
                                                    ),
                                                    width=6,
                                                ),
                                            ],
                                        ),
                                    ],
                                    className="mb-3",
                                ),
                                html.Div(
                                    id="transcript",
                                    style={
                                        "max-height": "calc(100vh - 300px)",
                                        "overflow-y": "auto",
                                        "padding": "1rem",
                                        "box-shadow": "inset 0 4px 6px rgba(0, 0, 0, 0.1)",
                                    },
                                ),
                            ],
                            xs=10,
                            md=5,
                        ),

                        # List of episodes found in search
                        dbc.Col(
                            id="episode-column",
                            children=[
                                dbc.Row(
                                    id="sort-buttons",
                                    children=[
                                        html.Div(
                                            html.P("sort-buttons")
                                        )
                                    ],
                                ),
                                dbc.Row([
                                    html.Div(
                                        id="episode-list",
                                        children=["Episodes"]
                                    ),
                                    dbc.Pagination(
                                        id="pagination",
                                        max_value=5,
                                        first_last=True,
                                    ),
                                ]),
                            ],
                            xs=10,
                            md=5,
                            style={"border": "1px dashed #008800"},
                        ),

                        dbc.Col(
                            [
                                html.Div(
                                    html.P("Hello")
                                )
                            ],
                            xs=10,
                            md=2,
                            id="keyword-tags",
                            style={"border": "1px dashed #000088"},
                        )
                    ],
                    className="mt-5",
                ),
            ]
        ),
        className="mt-3",
    )

    app.layout = html.Div(
        dbc.Container(
            [
                dbc.Tabs(
                    [
                        dbc.Tab(browse_tab, label="Browse"),
                        dbc.Tab(
                            "This tab is under construction",
                            label="My Terms",
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
                    ],
                    className="mt-3"
                )
            ]
        )
    )

    init_callbacks(app)

    return app  # .server


def init_callbacks(app):

    @app.callback(
        Output("episode-list", "children"),
        Output("transcript", "children"),
        Output("pagination", "max_value"),
        Output("pagination", "active_page"),
        Input("input", "n_submit"),
        Input("search-button", "n_clicks"),
        Input({"type": "result-card", "index": ALL}, "n_clicks"),
        Input("pagination", "active_page"),
        State("input", "value"),
    )
    def perform_search(n_submit, src_nclicks, card_nclicks, active_page, search_term):

        # Nothing has happened yet, fill target components with defaults:
        if not ctx.triggered:
            return [], [], 1, 1

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Trigger was a new search term - reset page to 1:
        if trigger_id in ["input", "search-button"]:
            page = 1
        else:
            page = active_page or 1

        if search_term:

            if (n_submit is not None and n_submit > 0) or active_page:
                page = active_page or 1

                # Get search results as a set:
                result_set = ResultSet(
                    es_client=app.es_client,
                    episode_store=episode_store,
                    index_name=INDEX_NAME,
                    search_term=search_term,
                    page_size=10,
                )

                # Get the current result page:
                this_page = result_set.get_page(page - 1)
                if this_page is None:
                    return [], [], 1, 1

                this_page_hits = this_page.episodes
                total_hits = result_set.total_hits
                max_pages = -(-len(result_set.episodes) // 10)  # Ceiling division

                results_page = ResultsPage(this_page_hits, episode_store)
                result_cards = [c.to_html() for c in results_page.cards]

                diarized_transcript = []

                if "result-card" in trigger_id:
                    episode_id = json.loads(trigger_id)["index"]
                    episode = [
                        i for i in episode_store.episodes() if i.eid == episode_id
                    ][0]

                    diarized_transcript = diarize_transcript(
                        eid=episode_id,
                        episode_store=episode_store,
                        search_term=search_term,
                    )

                return result_cards, diarized_transcript, max_pages, page

        return [], [], 0, 1
