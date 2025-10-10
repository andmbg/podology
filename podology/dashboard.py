import os
import json
from typing import List
from pathlib import Path
from urllib.parse import urljoin
from flask import url_for

import dash_ag_grid as dag
from dash import Dash, dcc, html, Input, Output, State, ALL, ctx, no_update
import dash_mantine_components as dmc
from dash.dependencies import ClientsideFunction
from dash_iconify import DashIconify
from bs4 import BeautifulSoup
from loguru import logger

from podology.data.Episode import Status
from podology.data.EpisodeStore import EpisodeStore
from podology.data.Transcript import Transcript
from podology.search.search_classes import ResultSet, create_cards
from podology.search.elasticsearch import get_es_client, TRANSCRIPT_INDEX_NAME
from podology.stats.preparation import post_process_pipeline
from podology.stats.plotting import plot_transcript_hits_es, plot_word_freq
from podology.frontend.utils import (
    clickable_tag,
    colorway,
    get_sort_button,
    empty_term_fig,
    empty_scroll_fig,
    empty_term_hit_fig,
    format_duration,
)
from podology.frontend.renderers.wordticker import get_ticker_dict
from config import get_connector, ASSETS_DIR, READONLY, BASE_PATH


max_intervals = 1 if READONLY else None
poll_interval = dcc.Interval(
    id="job-status-update", interval=1000, max_intervals=max_intervals
)

episode_store = EpisodeStore()

for pub_ep in get_connector().fetch_episodes():
    episode_store.add_or_update(pub_ep)

episode_store.update_from_files()


def with_prefix(path: str) -> str:
    # Builds /podology/<path> (or /<path> when no prefix)
    return urljoin(BASE_PATH, path.lstrip("/"))


def get_row_data(episode_store: EpisodeStore) -> List[dict]:
    rowdata = []
    for ep in episode_store:
        row = {
            "eid": ep.eid,
            "pub_date": ep.pub_date,
            "title": ep.title,
            "description": ep.description,
            "description_text": BeautifulSoup(ep.description, "html.parser").get_text(),
            "duration": format_duration(ep.duration),
            "status": (
                Status.DONE.value
                if (
                    ep.transcript.status is Status.DONE
                    and ep.audio.status is Status.DONE
                )
                else Status.NOT_DONE.value
            ),
        }
        wc_path = ASSETS_DIR / "wordclouds" / f"{ep.eid}.png"
        if wc_path.exists():
            wc_url = with_prefix(f"assets/wordclouds/{ep.eid}.png")
        else:
            wc_url = ""
        row["wordcloud_url"] = wc_url
        rowdata.append(row)
    return rowdata


def init_dashboard(flask_app, route):
    """
    Main function to initialize the dashboard.
    """
    # Fill the ES index with transcripts:
    es_client = get_es_client()

    post_process_pipeline(episode_store=episode_store)

    logger.info(f"Route to podology: {route}")

    app = Dash(
        __name__,
        server=flask_app,
        requests_pathname_prefix=route,
        routes_pathname_prefix=route,
        suppress_callback_exceptions=True,
        assets_folder=f"{Path(__file__).parent / 'assets'}",
    )

    app.es_client = es_client

    #
    #  _________________
    # | Search Metadata |
    #  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾

    # AG Grid column definitions for the episode list in the Metadata tab:
    conditional_style = {
        "function": "params.data.status == '✅️' ? {backgroundColor: '#00ff0011'} : ("
        "params.data.status == '➖️' ? {backgroundColor: '#ff000011'} : {backgroundColor: "
        "'#ffff0033'})"
    }

    column_defs = [
        {
            "headerName": "EID",
            "field": "eid",
            "maxWidth": 80,
            # "sort": "asc",
            # "sortIndex": 1,
            # "cellStyle": conditional_style,
            # "hide": True,
        },
        {
            "headerName": "Date",
            "field": "pub_date",
            "type": "date",
            "sortable": True,
            "sort": "desc",
            "sortIndex": 0,
            "filter": True,
            # "cellStyle": conditional_style,
            "maxWidth": 120,
        },
        {
            "headerName": "Title",
            "field": "title",
            "sortable": True,
            "filter": True,
            # "maxWidth": 600,
            # "cellStyle": conditional_style,
            "tooltipField": "description",
            "tooltipComponent": "CustomTooltip",
        },
        {
            "headerName": "Duration",
            "field": "duration",
            "sortable": True,
            "filter": True,
            "maxWidth": 120,
            # "cellStyle": conditional_style,
        },
        {
            "headerName": "Status",
            "field": "status",
            "maxWidth": 120,
            # "cellStyle": conditional_style,
            "filter": False,
        },
    ]

    theme_toggle = dmc.Switch(
        offLabel=DashIconify(
            icon="radix-icons:sun",
            width=20,
            color=dmc.DEFAULT_THEME["colors"]["yellow"][8],
        ),
        onLabel=DashIconify(
            icon="radix-icons:moon",
            width=20,
            color=dmc.DEFAULT_THEME["colors"]["yellow"][6],
        ),
        id="color-scheme-switch",
        persistence=True,
        color="gray",
        size="lg",
    )

    # Currently unused:
    language_toggle = dmc.Switch(
        onLabel="EN",
        offLabel="DE",
        id="language-switch",
        persistence=True,
        color="gray",
        size="lg",
    )

    app.layout = dmc.MantineProvider(
        dmc.Container(
            [
                dcc.Store(id="frequency-dict", data={"": 0}),
                dcc.Store(id="scroll-position-store", data=0),
                # Add a hidden div to trigger the scroll listener setup:
                html.Div(id="scroll-listener-trigger", style={"display": "none"}),
                #
                # Input (search field) and switches
                #
                dmc.Grid(
                    [
                        dmc.GridCol(
                            [
                                dmc.Switch(
                                    onLabel=(
                                        DashIconify(
                                            icon="iconoir:brain",
                                            width=20,
                                            color=dmc.DEFAULT_THEME["colors"]["yellow"][
                                                6
                                            ],
                                        )
                                    ),
                                    offLabel=(
                                        DashIconify(
                                            icon="iconoir:page-search",
                                            width=20,
                                            color=dmc.DEFAULT_THEME["colors"]["gray"][
                                                6
                                            ],
                                        )
                                    ),
                                    id="search-mode-switch",
                                    size="lg",
                                    persistence=True,
                                ),
                            ],
                            style={
                                "display": "flex",
                                "flex-direction": "row-reverse",
                                "align-items": "center",
                                "padding-right": "10px",
                                "padding-top": "50px",
                            },
                            span=2,
                        ),
                        dmc.GridCol(
                            [
                                dmc.TextInput(
                                    id="input",
                                    placeholder="Enter search term",
                                    label="Search",
                                    description="Search for terms used in the transcript",
                                    size="sm",
                                    radius="sm",
                                    debounce=True,
                                )
                            ],
                            id="search-input-container",
                            span=7,
                        ),
                        dmc.GridCol(
                            [
                                theme_toggle,
                                # language_toggle,
                            ],
                            span=3,
                            style={
                                "display": "flex",
                                "flex-direction": "row",
                                "align-items": "center",
                                "justify-content": "space-around",
                                "padding-top": "50px",
                                "padding-left": "30px",
                                "padding-right": "30px",
                            },
                        ),
                    ],
                    # className="mt-3",
                ),
                #
                # Search Tags
                #
                dmc.Grid(
                    dmc.GridCol(
                        [
                            dcc.Store(
                                id="terms-store",
                                data={
                                    "entries": [],
                                    "colorid-stack": [i.id for i in colorway],
                                },
                            ),
                            html.Div(
                                id="terms-list",
                                className="d-flex flex-row flex-wrap justify-content-center align-items-center",
                            ),
                        ],
                        span={"base": 12, "md": 12},
                        id="keyword-tags",
                        # className="p-0 d-flex justify-content-center align-items-center",
                    ),
                    # className="mt-3",
                ),
                dcc.Store(id="visible-segments", data=[]),
                # DEBUG: Display currently visible time span
                # dmc.Grid(dmc.GridCol(dmc.Text(id="visible-segments-display"))),
                #
                # Tabs
                #
                dmc.Tabs(
                    [
                        dmc.TabsList(
                            [
                                dmc.TabsTab("Metadata", value="metadata"),
                                dmc.TabsTab("Within Episode", value="within"),
                                dmc.TabsTab("Across Episode", value="across"),
                            ],
                            style={"marginTop": 20},
                        ),
                        dmc.TabsPanel(
                            #  __________
                            # | Metadata |
                            #  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
                            dmc.Grid(
                                [
                                    dmc.GridCol(
                                        [
                                            dmc.Title("Episodes", order=2),
                                            dag.AgGrid(
                                                id="transcribe-episode-list",
                                                columnDefs=column_defs,
                                                columnSize="sizeToFit",
                                                defaultColDef={
                                                    "resizable": True,
                                                    "sortable": True,
                                                    "filter": True,
                                                },
                                                rowModelType="clientSide",
                                                style={
                                                    "height": "calc(100vh - 300px)",
                                                    "width": "100%",
                                                },
                                                rowData=get_row_data(episode_store),
                                                className="ag-theme-quartz",
                                                getRowId="params.data.eid",
                                                dashGridOptions={
                                                    "rowSelection": "single",
                                                    "tooltipShowDelay": 500,
                                                    "tooltipHideDelay": 10000,
                                                    "tooltipInteraction": True,
                                                    "popupParent": {
                                                        "function": "setPopupsParent()"
                                                    },
                                                },
                                            ),
                                        ],
                                        span=12,
                                        style={"margin-top": "20px"},
                                    ),
                                ],
                            ),
                            value="metadata",
                        ),
                        dmc.TabsPanel(
                            #
                            #     ________________
                            #    | Within Episode |
                            #  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
                            dmc.Grid(
                                children=[
                                    #
                                    # Animated word cloud (Ticker)
                                    # ----------------------------
                                    dmc.GridCol(
                                        children=[
                                            dcc.Graph(
                                                id="scroll-animation",
                                                figure=empty_scroll_fig,
                                                config={
                                                    "displayModeBar": False,
                                                    "staticPlot": True,
                                                },
                                            ),
                                            dcc.Store(
                                                id="ticker-dict",
                                                data="",
                                            ),
                                        ],
                                        span={"md": 5, "xs": 12},
                                    ),
                                    #
                                    # Transcript of selected episode
                                    # ------------------------------
                                    dmc.GridCol(
                                        children=[
                                            dmc.Paper(
                                                children=[
                                                    dmc.Grid(
                                                        [
                                                            dmc.GridCol(
                                                                [
                                                                    dcc.Store(
                                                                        id="playback-time-store",
                                                                        data=0,
                                                                    ),
                                                                    html.Audio(
                                                                        id="audio-player",
                                                                        controls=True,
                                                                        src="",
                                                                    ),
                                                                ],
                                                                span=9,
                                                            ),
                                                            dmc.GridCol(
                                                                [
                                                                    dcc.Store(
                                                                        id="episode-duration",
                                                                        data="",
                                                                    ),
                                                                    dmc.Text(
                                                                        "",
                                                                        id="transcript-episode-date",
                                                                        c="dimmed",
                                                                    ),
                                                                ],
                                                                span=3,
                                                            ),
                                                        ]
                                                    ),
                                                    dmc.Grid(
                                                        [
                                                            dmc.Title(
                                                                "Title",
                                                                order=3,
                                                                id="transcript-episode-title",
                                                            ),
                                                            dmc.GridCol(
                                                                span=12,
                                                            ),
                                                        ],
                                                    ),
                                                    #
                                                    # Transcript and search hit / relevance displays
                                                    #
                                                    dmc.Grid(
                                                        [
                                                            dmc.GridCol(
                                                                dmc.Paper(
                                                                    id="transcript",
                                                                    className="transcript",
                                                                    style={
                                                                        "height": "calc(100vh - 500px)",
                                                                        "overflow-y": "auto",
                                                                    },
                                                                ),
                                                                span=11,
                                                                style={
                                                                    "padding-right": "0",
                                                                    "height": "calc(100vh-500px)",
                                                                },
                                                            ),
                                                            dmc.GridCol(
                                                                html.Div(
                                                                    [
                                                                        # Term occurrences:
                                                                        dcc.Graph(
                                                                            id="search-hit-column",
                                                                            config={
                                                                                "displayModeBar": False,
                                                                                "staticPlot": True,
                                                                            },
                                                                            figure=empty_term_hit_fig,
                                                                            style={
                                                                                "height": "100%",
                                                                                "width": "100%",
                                                                            },
                                                                        ),
                                                                        html.Div(
                                                                            id="visible-area-overlay",
                                                                            style={
                                                                                "position": "absolute",
                                                                                "top": "0%",
                                                                                "left": "0",
                                                                                "right": "0",
                                                                                "height": "0",
                                                                                "background": "rgba(120, 120, 120, 0.2)",
                                                                                "border-left": "3px solid rgba(120, 120, 120, 1.0)",
                                                                                "pointer-events": "none",  # Don't block graph interactions
                                                                                "display": "none",  # Initially hidden
                                                                                "z-index": "10",
                                                                            },
                                                                        ),
                                                                    ],
                                                                    style={
                                                                        "position": "relative",
                                                                        "height": "calc(100vh - 500px)",
                                                                        "width": "100%",
                                                                        "overflow": "hidden",
                                                                    },
                                                                ),
                                                                span=1,
                                                                className="col-search-hits",
                                                                style={
                                                                    "padding-left": "0",
                                                                    "height": "calc(100vh - 500px)",
                                                                },
                                                            ),
                                                        ],
                                                        className="align-items-stretch",
                                                        style={
                                                            "height": "calc(100vh - 500px)",
                                                            "min-height": "500px",
                                                        },
                                                    ),
                                                ],
                                            ),
                                        ],
                                        span=dict(xs=12, md=7),
                                    ),
                                ],
                                style={"margin-top": "20px"},
                            ),
                            value="within",
                        ),
                        dmc.TabsPanel(
                            #
                            #            _________________
                            #           | Across Episodes |
                            #  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
                            dmc.Card(
                                # className="m-0 no-top-border",
                                children=[
                                    #
                                    # Word frequency plot
                                    # ----------------------------
                                    dmc.Grid(
                                        [
                                            dmc.GridCol(
                                                dcc.Graph(
                                                    id="word-count-plot",
                                                    figure=empty_term_fig,
                                                ),
                                                span=12,
                                            )
                                        ]
                                    ),
                                    #
                                    # List of episodes found in search
                                    # --------------------------------
                                    dmc.Grid(
                                        [
                                            dmc.GridCol(
                                                id="episode-column",
                                                children=[
                                                    dcc.Store(
                                                        id="selected-episode", data=""
                                                    ),
                                                    dcc.Store(id="sorting", data={}),
                                                    dcc.Store(
                                                        id="episode-list-data", data=[]
                                                    ),
                                                    dmc.Grid(
                                                        id="sort-buttons",
                                                        style={"position": "relative"},
                                                    ),
                                                    dmc.Grid(
                                                        children=[
                                                            dmc.Stack(
                                                                id="episode-list",
                                                                gap="xs",
                                                                children=["Episodes"],
                                                            )
                                                        ]
                                                    ),
                                                ],
                                                span=dict(xs=12, md=6),
                                            ),
                                        ],
                                    ),
                                ]
                            ),
                            value="across",
                        ),
                    ],
                    id="tab-container",
                    color="teal",
                    orientation="horizontal",
                    variant="default",
                    value="metadata",
                    style={"height": "calc(100vh - 500px)"},
                ),
                dcc.Interval(id="pageload-trigger", interval=100, max_intervals=1),
                poll_interval,
                dcc.Store(id="ongoing-jobs", data=[]),
                dcc.Store(id="scroll-sync-init", data=0),
            ],
            size="lg",
        )
    )

    init_callbacks(app)

    return app  # .server


def init_callbacks(app):
    """
    Initialize the callbacks for the Dash app.
    """

    # Add the scroll listener setup callback
    app.clientside_callback(
        ClientsideFunction(namespace="ticker", function_name="setup_scroll_listener"),
        Output("scroll-listener-trigger", "children"),
        Input("pageload-trigger", "n_intervals"),
    )

    # Add the ticker animation callback
    app.clientside_callback(
        ClientsideFunction(
            namespace="ticker", function_name="update_ticker_from_scroll"
        ),
        Output("scroll-animation", "figure"),
        Input("visible-segments", "data"),
        State("episode-duration", "data"),
        State("ticker-dict", "data"),
    )

    # Color theme switch:
    app.clientside_callback(
        """
        (switchOn) => {
            document.documentElement.setAttribute('data-mantine-color-scheme', switchOn ? 'dark' : 'light');
            return window.dash_clientside.no_update
        }
        """,
        Output("color-scheme-switch", "id"),
        Input("color-scheme-switch", "checked"),
    )

    # Search mode switch:
    app.clientside_callback(
        """
        (switchOn) => {
            document.documentElement.setAttribute('data-search-mode', switchOn ? 'semantic' : 'term');
            return window.dash_clientside.no_update
        }
        """,
        Output("search-mode-switch", "id"),
        Input("search-mode-switch", "checked"),
    )

    # Check which transcript segments are currently visible:
    app.clientside_callback(
        ClientsideFunction(namespace="visible_span", function_name="get_visible_span"),
        Output("visible-segments", "data"),
        Input("transcript", "children"),
    )

    # DEBUG: view the visible time range:
    # app.clientside_callback(
    #     """
    #     function(visible_segments) {
    #         if (!visible_segments || visible_segments.length !== 2) {
    #             return "No segments visible";
    #         }

    #         const firstTime = visible_segments[0];
    #         const lastTime = visible_segments[1];

    #         if (firstTime === null || lastTime === null) {
    #             return "No segments visible";
    #         }

    #         return `Visible: ${firstTime.toFixed(1)}s → ${lastTime.toFixed(1)}s`;
    #     }
    #     """,
    #     Output("visible-segments-display", "children"),
    #     Input("visible-segments", "data"),
    # )

    # Move a rectangle over the hit column to mark the current viewport:
    # app.clientside_callback(
    #     ClientsideFunction(
    #         namespace="visible_span", function_name="scroll_rect"
    #     ),
    #     Output("search-hit-column", "relayoutData"),
    #     Input("visible-segments", "data"),
    #     State("transcript-episode-duration", "children"),
    #     prevent_initial_call=True,
    # )

    app.clientside_callback(
        ClientsideFunction(namespace="visible_span", function_name="scroll_rect"),
        Output("visible-area-overlay", "className"),  # Dummy output
        Input("visible-segments", "data"),
        State("episode-duration", "data"),
        prevent_initial_call=True,
    )

    @app.callback(
        Output("transcribe-episode-list", "rowData"),
        Input("pageload-trigger", "n_intervals"),
    )
    def prefill_table(pageload_trigger):
        """
        Table update upon page load or job status update.
        """
        episode_store = EpisodeStore()
        return get_row_data(episode_store)

    @app.callback(
        Output("transcribe-episode-list", "rowTransaction"),
        Input("transcribe-episode-list", "cellClicked"),
        Input("job-status-update", "n_intervals"),
        State("transcribe-episode-list", "rowData"),
    )
    def download_ep_or_update_table(cell_clicked, n_update, row_data):
        """
        Either user clicks on the status column of an episode in the table,
        or a job status update occurs.
        """
        # Triggered by click, not by clock:
        episode_store = EpisodeStore()
        if ctx.triggered_id == "transcribe-episode-list":

            if cell_clicked.get("colId", "") != "status":
                return no_update

            # User clicked on the status column of an episode. Which one:
            eid = cell_clicked.get("rowId")
            episode = episode_store[eid]

            if episode.transcript.status:
                return no_update

            # So you clicked on the Status column of a missing episode:
            qid = episode_store.enqueue_transcription_job(episode=episode)
            logger.info(f"qid {qid} for episode {eid} enqueued")

            row = [row for row in row_data if row["eid"] == eid]
            row[0]["status"] = Status.QUEUED.value

            return {"update": row}

        elif ctx.triggered_id == "job-status-update":
            update_rows = []
            for ep in episode_store:

                # Find the corresponding row in the frontend data
                row = next((r for r in row_data if r["eid"] == ep.eid), None)
                if row and row["status"] != ep.transcript.status.value:
                    row["status"] = ep.transcript.status.value
                    update_rows.append(row)
            if update_rows:
                return {"update": update_rows}
            return no_update

    @app.callback(
        Output("tab-container", "value"),
        Input("transcribe-episode-list", "cellClicked"),
        Input("word-count-plot", "clickData"),
        Input({"type": "result-card", "index": ALL}, "n_clicks"),
        State({"type": "result-card", "index": ALL}, "id"),
    )
    def tab_to_transcript(
        cellClicked, word_count_click_data, episode_list_nclicks, episode_list_id
    ):
        """
        If user clicks on the title of a transcribed episode in the Metadata
        tab, or on a result card in the Across-Episodes tab, change active tab
        to the Transcripts tab.
        """
        if not ctx.triggered:
            return no_update

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if ctx.triggered_id == "word-count-plot":
            return "within"

        if ctx.triggered_id == "transcribe-episode-list":
            columnClicked = cellClicked.get("colId", {})
            eid = cellClicked.get("rowId", "")
            if eid:
                episode = episode_store[eid]
                if episode.transcript.status and columnClicked == "title":
                    return "within"

        # Tricky indirect filtering: switch only if a result card was clicked,
        # not a sorting button:
        if (
            ctx.triggered_id
            and "result-card" in str(ctx.triggered_id)
            and episode_list_nclicks
            and not all(x is None for x in episode_list_nclicks)
            and episode_list_id
        ):
            return "within"

        return no_update

    @app.callback(
        Output("input", "placeholder"),
        Output("input", "label"),
        Output("input", "description"),
        Input("search-mode-switch", "checked"),
    )
    def switch_search_input(search_mode_checked):
        """
        Switch between term search and semantic search input based on the search mode toggle.
        """
        if search_mode_checked:  # Brain icon (semantic search)
            return ("Enter prompt", "Prompt", "Prompt for topics touched upon")
        else:  # Page search icon (term search)
            return (
                "Enter search term",
                "Search",
                "Search for terms used in the transcript",
            )

    @app.callback(
        Output("episode-list-data", "data"),
        Input("terms-store", "data"),
        Input({"type": "sort-button", "index": ALL}, "n_clicks"),
        State({"type": "sort-button", "index": ALL}, "id"),
        State("episode-list-data", "data"),
        State("terms-store", "data"),
    )
    def update_episode_list_from_terms(
        terms_store_input,
        sortbtn_nclicks,
        sortbtn_id,
        current_data,
        terms_store_state,
    ):
        """
        If the terms list has changed, create a new ResultSet and store its
        hits_by_ep in the episode-list-data Store.
        If a sort button was clicked, work with the Store content and re-sort it.
        """
        # Nothing has happened yet, fill target components with defaults:
        if not ctx.triggered or terms_store_input["entries"] == []:
            return []

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        eplist_updated = None

        # Terms list has changed - get search results as a set:
        if terms_store_input:
            result_set = ResultSet(
                es_client=app.es_client,
                index_name=TRANSCRIPT_INDEX_NAME,
                term_colorids=terms_store_input["entries"],
            )
            eplist_updated = result_set.hits_by_ep

        # A sort button has been clicked - re-sort the current data:
        if (
            "sort-button" in trigger_id
            and sortbtn_nclicks
            and any(i is not None for i in sortbtn_nclicks)
        ):
            sort_btn_id = json.loads(trigger_id)["index"]
            sort_term = [
                i for i, j, _ in terms_store_state["entries"] if j == sort_btn_id
            ][0]
            eplist_updated = dict(
                sorted(
                    current_data.items(),
                    key=lambda item: item[1].get(sort_term, float(0)),
                    reverse=True,
                )
            )

        if eplist_updated is None:
            return no_update

        return eplist_updated

    @app.callback(
        Output("episode-list", "children"),
        Input("episode-list-data", "data"),
        State("terms-store", "data"),
    )
    def update_episode_hitlist(eplist, terms_store):
        """
        React to changes in episode list and re-render html episode list.
        """
        # Get search results as a set:
        if not eplist:
            return []

        term_colorid_dict = {k: v for k, v, _ in terms_store["entries"]}
        result_cards = create_cards(eplist, term_colorid_dict)

        result_card_elements = [c.to_html() for c in result_cards]

        return result_card_elements

    @app.callback(
        Output("sort-buttons", "children"),
        Input("terms-store", "data"),
    )
    def update_sort_buttons(terms_store):
        """
        Update the sort buttons based on the current terms. So if a search term
        is added, add a sort button and so on.
        """
        entries = terms_store["entries"]

        out = html.Div(
            [get_sort_button(i) for i in entries],
        )

        return out

    @app.callback(
        Output("selected-episode", "data"),
        Input("transcribe-episode-list", "cellClicked"),
        Input({"type": "result-card", "index": ALL}, "n_clicks"),
        Input("word-count-plot", "clickData"),
        State({"type": "result-card", "index": ALL}, "id"),
        State("selected-episode", "data"),
    )
    def update_selected_episode(
        table_clicked_cell,
        resultcard_nclicks,
        word_count_click_data,
        resultcard_id,
        current_eid,
    ):
        """Update which episode is active in the Within tab.

        Reacts to clicking title in Metadata tab, result card, or word count plot.
        """
        if not ctx.triggered:
            return no_update

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        all_triggers = [i["prop_id"] for i in ctx.triggered]

        # Click on episode list in meta tab:
        if trigger_id == "transcribe-episode-list":
            column_clicked = table_clicked_cell.get("colId", "")
            row_clicked = table_clicked_cell.get("rowId", "")

            eid = row_clicked
            if column_clicked == "title" and eid:
                episode = episode_store[eid]
                if episode.transcript.status:
                    return eid

        # Click on result card:
        elif (
            "result-card" in trigger_id
            and resultcard_nclicks
            and any(i is not None for i in resultcard_nclicks)
        ):
            selected_eid = json.loads(trigger_id)["index"]

            return selected_eid

        elif word_count_click_data:
            # Extract the episode ID from the clicked point's customdata:
            points = word_count_click_data.get("points", [])
            if not points:
                return no_update

            point = points[0]
            eid = point.get("customdata", None)[4]
            logger.debug(f"word count click data points: {eid}")
            if eid:
                return eid

            return no_update

        return no_update

    @app.callback(
        Output("transcript", "children"),
        Output("transcript-episode-title", "children"),
        Output("transcript-episode-date", "children"),
        Output("episode-duration", "data"),
        Output("ticker-dict", "data"),
        Output("audio-player", "src"),
        Output("scroll-position-store", "data"),
        Input("selected-episode", "data"),
        State("selected-episode", "data"),
        Input("terms-store", "data"),
        State("terms-store", "data"),
        prevent_initial_call=True,
    )
    def update_transcript(
        selected_eid_input,
        selected_eid_state,
        terms_store_input,
        terms_store_state,
    ):
        """
        Callback that updates the displayed transcript and its highlights.
        """

        # Unify input for both cases of each Input being the trigger:
        eid = selected_eid_input or selected_eid_state
        terms_store = terms_store_input or terms_store_state

        if not eid:
            return no_update

        episode = episode_store[eid]
        entries = [entry for entry in terms_store["entries"] if entry[2] == "term"]

        # Get the transcript of the selected episode as HTML:
        diarized_script = Transcript(episode=episode)
        diarized_script_element = diarized_script.to_html(entries)

        # Set the scroll animation word dict to the episode's words:
        ticker_dict = get_ticker_dict(
            eid=episode.eid,
            window_width=120,
        )

        # Get prefix-aware audio URL:
        audio_url = url_for("serve_audio", eid=episode.eid)

        return (
            diarized_script_element,
            episode.title,
            episode.pub_date,
            format_duration(episode.duration),
            ticker_dict,
            audio_url,
            0,
        )

    # Update search terms in the comparison list:
    @app.callback(
        Output("terms-store", "data"),
        Output("input", "value"),
        Input("input", "n_submit"),
        Input({"type": "remove-term", "index": ALL}, "n_clicks"),
        State("input", "value"),
        State("terms-store", "data"),
        State("search-mode-switch", "checked"),
    )
    def update_terms_store(
        n_submit,
        remove_clicks,
        input_term,
        terms_store,
        semantic_search,
    ):
        """
        Update the terms Storage by adding the newly entered search term or removing
        the one that just got clicked. Empty the input field.

        At the same time, updates the visual representation of the Store.
        """
        if not ctx.triggered:
            return terms_store, ""

        # Search mode routing:
        termtype = "semantic" if semantic_search else "term"

        # Analyse the search term dict into a list of tuples and the color stack:
        term_entries = terms_store["entries"]
        terms = [i[0] for i in term_entries]
        colorid_stack = terms_store["colorid-stack"]

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # User adds new term by clicking "Add" button or pressing Enter:
        if trigger_id == "input" and input_term:
            if len(term_entries) < 10 and input_term not in terms:
                # assign the first available color to the new term_colorid:
                new_term_tuple = [input_term, colorid_stack.pop(), termtype]
                term_entries.append(new_term_tuple)

        # A tag was clicked for removal:
        elif "remove-term" in trigger_id:
            index = int(json.loads(trigger_id)["index"])
            if 0 <= index < len(term_entries):
                freed_colorid = term_entries.pop(index)[1]
                colorid_stack.append(freed_colorid)

        new_terms_colors_dict = {
            "entries": term_entries,
            "colorid-stack": colorid_stack,
        }

        return new_terms_colors_dict, ""

    @app.callback(
        Output("terms-list", "children"),
        Input("terms-store", "data"),
    )
    def update_terms_lists(terms_store):
        tag_elements = [
            clickable_tag(i, term_colorid)
            for i, term_colorid in enumerate(terms_store["entries"])
        ]
        return tag_elements

    @app.callback(
        Output("word-count-plot", "figure"),
        Input("terms-store", "data"),
        prevent_initial_call=True,
    )
    def update_word_freq_plot(terms_store):
        """
        Callback that updates the frequency table view.
        """
        termtuples = [t for t in terms_store["entries"] if t[2] == "term"]

        if len(termtuples) == 0:
            return empty_term_fig

        return plot_word_freq(terms_store["entries"], es_client=app.es_client)

    @app.callback(
        Output("search-hit-column", "figure"),
        Input("terms-store", "data"),
        Input("selected-episode", "data"),
        prevent_initial_call=True,
    )
    def update_transcript_hits_plot(terms_store, eid):
        """
        Update the transcript hits plot when adding/removing search terms or
        changing the selected episode.
        """
        if not terms_store or terms_store["entries"] == [] or not eid:
            return empty_term_hit_fig

        episode = episode_store[eid]
        logger.info(terms_store["entries"])

        return plot_transcript_hits_es(
            terms_store["entries"], eid, es_client=app.es_client
        )
