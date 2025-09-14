import os
import json
from typing import List
from pathlib import Path

import dash_ag_grid as dag
from dash import Dash, dcc, html, Input, Output, State, ALL, ctx, no_update
import dash_bootstrap_components as dbc
from dash.dependencies import ClientsideFunction
from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch
from loguru import logger

from podology.data.Episode import Status
from podology.data.EpisodeStore import EpisodeStore
from podology.data.Transcript import Transcript
from podology.search.search_classes import ResultSet, create_cards
from podology.search.elasticsearch import TRANSCRIPT_INDEX_NAME
from podology.stats.preparation import post_process_pipeline
from podology.stats.plotting import plot_transcript_hits, plot_word_freq
from podology.frontend.utils import (
    clickable_tag,
    colorway,
    get_sort_button,
    empty_term_fig,
    empty_scroll_fig,
    empty_term_hit_fig,
)
from podology.frontend.renderers.wordticker import get_ticker_dict
from config import get_connector, ASSETS_DIR


episode_store = EpisodeStore()

for pub_ep in get_connector().fetch_episodes():
    episode_store.add_or_update(pub_ep)

episode_store.update_from_files()


def get_row_data(episode_store: EpisodeStore) -> List[dict]:
    rowdata = []
    for ep in episode_store:
        row = {
            "eid": ep.eid,
            "pub_date": ep.pub_date,
            "title": ep.title,
            "description": ep.description,
            "description_text": BeautifulSoup(ep.description, "html.parser").get_text(),
            "duration": ep.duration,
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
        wc_url = str(wc_path).replace(str(ASSETS_DIR), "/assets")

        if wc_path.exists():
            row["wordcloud_url"] = wc_url
        else:
            row["wordcloud_url"] = ""

        rowdata.append(row)

    return rowdata


def init_dashboard(flask_app, route):
    """
    Main function to initialize the dashboard.
    """
    # Fill the ES index with transcripts:
    try:
        user = os.getenv("ELASTIC_USER") or ""
        pwd = os.getenv("ELASTIC_PASSWORD") or ""
        es_client = Elasticsearch(
            "http://localhost:9200",
            basic_auth=(user, pwd),
            # verify_certs=True,
            # ca_certs=basedir / "http_ca.crt"
        )
    except TypeError:
        print("Elasticsearch client not initialized. Check environment variables.")
        raise

    post_process_pipeline(episode_store=episode_store)

    app = Dash(
        __name__,
        server=flask_app,
        routes_pathname_prefix=route,
        # relevant for standalone launch, not used by main flask app:
        # FIXME this overrides our custom CSS!
        external_stylesheets=[dbc.themes.CERULEAN],
        assets_folder=str(Path(__file__).parent / "assets"),
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

    transcribe_tab = dbc.Card(
        className="m-0 no-top-border",
        children=dbc.CardBody(
            [
                # Episode List
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.H5("Episodes"),
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
                                        "height": "calc(100vh - 200px)",
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
                            width=12,
                        ),
                    ],
                    className="mt-3",
                ),
            ],
        ),
    )

    #
    #  ____________________
    # | Search Transcripts |
    #  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
    browse_tab = dbc.Card(
        className="m-0 no-top-border",
        children=dbc.CardBody(
            [
                #
                # Output
                # ----------------
                dbc.Row(
                    children=[
                        #
                        # Animated word cloud (Ticker)
                        # ----------------------------
                        dbc.Col(
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
                            md=6,
                            xs=12,
                        ),
                        #
                        # Transcript of selected episode
                        # ------------------------------
                        dbc.Col(
                            children=[
                                html.Div(
                                    children=[
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    [
                                                        dcc.Store(
                                                            id="playback-time-store",
                                                            data=0,
                                                        ),
                                                        # dbc.Button(
                                                        #     "⏸",
                                                        #     id="play",
                                                        #     color="secondary",
                                                        #     size="sm",
                                                        #     className="me-1",
                                                        # ),
                                                        html.Audio(
                                                            id="audio-player",
                                                            controls=True,
                                                            src="/audio/LxvbG",
                                                        ),
                                                        html.H5(
                                                            html.B(
                                                                "Title",
                                                                id="transcript-episode-title",
                                                            ),
                                                            className="mb-0 text-truncate",
                                                        ),
                                                    ],
                                                    width=12,
                                                    className="d-flex align-items-center",
                                                ),
                                            ]
                                        ),
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    html.P(
                                                        "",
                                                        id="transcript-episode-date",
                                                        className="text-muted mb-0",
                                                    ),
                                                    width=6,
                                                ),
                                                dbc.Col(
                                                    html.P(
                                                        [
                                                            html.Span(
                                                                "Duration: ",
                                                                className="text-secondary",
                                                            ),
                                                            html.Span(
                                                                "",
                                                                id="transcript-episode-duration",
                                                            ),
                                                        ],
                                                        className="mb-0 text-end",
                                                    ),
                                                    width=6,
                                                ),
                                            ],
                                        ),
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    html.Div(
                                                        id="transcript",
                                                        className="transcript",
                                                    ),
                                                    className="mb-0 flex-grow-1",
                                                    style={
                                                        "padding-right": "0",
                                                        "height": "100%",
                                                    },
                                                ),
                                                dbc.Col(
                                                    [
                                                        dcc.Graph(
                                                            id="search-hit-column",
                                                            config={
                                                                "displayModeBar": False,
                                                                "staticPlot": True,
                                                            },
                                                            figure=empty_term_hit_fig,
                                                            style={"height": "100%"},
                                                        ),
                                                    ],
                                                    className="col-search-hits p-0",
                                                    style={"height": "100%"},
                                                ),
                                            ],
                                            className="align-items-stretch",
                                            style={"height": "calc(100vh - 340px)"},
                                        ),
                                    ],
                                    className="mb-3",
                                ),
                            ],
                            xs=12,
                            md=6,
                        ),
                    ],
                    className="mt-5",
                ),
            ]
        ),
    )

    #
    #  _________________
    # | Across Episodes |
    #  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
    terms_tab = dbc.Card(
        className="m-0 no-top-border",
        children=dbc.CardBody(
            [
                # Word frequency plot
                # ----------------------------
                dbc.Row(
                    [
                        dbc.Col(
                            [dcc.Graph(id="word-count-plot", figure=empty_term_fig)],
                            width=12,
                        )
                    ]
                ),
                #
                # List of episodes found in search
                # --------------------------------
                dbc.Row(
                    [
                        dbc.Col(
                            id="episode-column",
                            children=[
                                dcc.Store(id="selected-episode", data=""),
                                dcc.Store(id="sorting", data={}),
                                dcc.Store(id="episode-list-data", data=[]),
                                dbc.Row(
                                    id="sort-buttons",
                                    style={"position": "relative"},
                                ),
                                dbc.Row(
                                    children=[
                                        html.Div(
                                            id="episode-list",
                                            className="episode-list",
                                            children=["Episodes"],
                                        )
                                    ]
                                ),
                            ],
                            xs=12,
                            md=6,
                        ),
                    ],
                ),
            ]
        ),
    )

    app.layout = html.Div(
        dbc.Container(
            [
                dcc.Store(id="frequency-dict", data={"": 0}),
                dcc.Store(id="scroll-position-store", data=0),
                # Add a hidden div to trigger the scroll listener setup:
                html.Div(id="scroll-listener-trigger", style={"display": "none"}),
                # Input (search field)
                dbc.Row(
                    [
                        dbc.Col(width=2),
                        dbc.Col(
                            [
                                dbc.Input(
                                    id="input",
                                    type="text",
                                    placeholder="Enter search term",
                                    debounce=True,
                                ),
                            ],
                            width=7,
                        ),
                        dbc.Col(
                            [
                                dbc.Button("Add", id="add-button", color="secondary"),
                            ],
                            width=1,
                        ),
                    ],
                    className="mt-3",
                ),
                # Term Tags
                # ---------
                dbc.Row(
                    dbc.Col(
                        [
                            dcc.Store(
                                id="terms-store",
                                data={
                                    "termtuples": [],
                                    "colorid-stack": [i.id for i in colorway],
                                },
                            ),
                            html.Div(
                                id="terms-list",
                                className="d-flex flex-row flex-wrap justify-content-center align-items-center",
                            ),
                        ],
                        xs=12,
                        md=12,
                        id="keyword-tags",
                        className="p-0 d-flex justify-content-center align-items-center",
                    ),
                    className="mt-3",
                ),
                dbc.Tabs(
                    [
                        dbc.Tab(transcribe_tab, label="Metadata"),
                        dbc.Tab(
                            browse_tab, label="Within Episode", tab_id="Transcripts"
                        ),
                        dbc.Tab(terms_tab, label="Across Episodes"),
                    ],
                    id="tab-container",
                    className="mt-3",
                ),
                dcc.Interval(id="pageload-trigger", interval=100, max_intervals=1),
                dcc.Interval(id="job-status-update", interval=1000),
                dcc.Store(id="ongoing-jobs", data=[]),
                dcc.Store(id="scroll-sync-init", data=0),
            ]
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
        Input("scroll-position-store", "data"),
        State("transcript-episode-duration", "children"),
        State("ticker-dict", "data"),
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
        logger.debug("pageload-trigger went off")
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
        Output("tab-container", "active_tab"),
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
            return "Transcripts"

        if ctx.triggered_id == "transcribe-episode-list":
            columnClicked = cellClicked.get("colId", {})
            eid = cellClicked.get("rowId", "")
            if eid:
                episode = episode_store[eid]
                if episode.transcript.status and columnClicked == "title":
                    return "Transcripts"

        # Tricky indirect filtering: switch only if a result card was clicked,
        # not a sorting button:
        if (
            ctx.triggered_id and 
            "result-card" in str(ctx.triggered_id) and 
            episode_list_nclicks and 
            not all(x is None for x in episode_list_nclicks) and
            episode_list_id
        ):
            return "Transcripts"

        return no_update

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
        if not ctx.triggered or terms_store_input["termtuples"] == []:
            return []

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        eplist_updated = None

        # Terms list has changed - get search results as a set:
        if terms_store_input:
            result_set = ResultSet(
                es_client=app.es_client,
                index_name=TRANSCRIPT_INDEX_NAME,
                term_colorids=terms_store_input["termtuples"],
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
                i for i, j in terms_store_state["termtuples"] if j == sort_btn_id
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

        term_colorid_dict = {k: v for k, v in terms_store["termtuples"]}
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
        termtuples = terms_store["termtuples"]

        out = html.Div(
            [get_sort_button(i) for i in termtuples],
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
        Output("transcript-episode-duration", "children"),
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
        termtuples = terms_store["termtuples"]

        # Get the transcript of the selected episode as HTML:
        diarized_script = Transcript(episode=episode)
        diarized_script_element = diarized_script.to_html(termtuples, diarized=True)

        # Set the scroll animation word dict to the episode's words:
        ticker_dict = get_ticker_dict(
            eid=episode.eid,
            window_width=120,
        )

        return (
            diarized_script_element,
            episode.title,
            episode.pub_date,
            episode.duration,
            ticker_dict,
            f"/audio/{eid}",
            0,
        )

    # Update search terms in the comparison list:
    @app.callback(
        Output("terms-store", "data"),
        Output("input", "value"),
        Input("input", "n_submit"),
        Input("add-button", "n_clicks"),
        Input({"type": "remove-term", "index": ALL}, "n_clicks"),
        State("input", "value"),
        State("terms-store", "data"),
    )
    def update_terms_store(
        n_submit,
        add_clicks,
        remove_clicks,
        input_term,
        terms_store,
    ):
        """
        Update the terms Storage by adding the newly entered search term or removing
        the one that just got clicked. Empty the input field.

        At the same time, updates the visual representation of the Store.
        """
        if not ctx.triggered:
            return terms_store, None

        # Analyse the search term dict into a list of tuples and the color stack:
        term_tuples = terms_store["termtuples"]
        terms = [i[0] for i in term_tuples]
        colorid_stack = terms_store["colorid-stack"]

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # User adds new term by clicking "Add" button or pressing Enter:
        if trigger_id in ["add-button", "input"] and input_term:
            if len(term_tuples) < 10 and input_term not in terms:
                # assign the first available color to the new term_colorid:
                new_term_tuple = (input_term, colorid_stack.pop())
                term_tuples.append(new_term_tuple)

        # A tag was clicked for removal:
        elif "remove-term" in trigger_id:
            index = int(json.loads(trigger_id)["index"])
            if 0 <= index < len(term_tuples):
                freed_colorid = term_tuples.pop(index)[1]
                colorid_stack.append(freed_colorid)

        new_terms_colors_dict = {
            "termtuples": term_tuples,
            "colorid-stack": colorid_stack,
        }

        return new_terms_colors_dict, None

    @app.callback(
        Output("terms-list", "children"),
        Input("terms-store", "data"),
    )
    def update_terms_lists(terms_store):
        tag_elements = [
            clickable_tag(i, term_colorid)
            for i, term_colorid in enumerate(terms_store["termtuples"])
        ]
        return tag_elements

    @app.callback(
        Output("word-count-plot", "figure"),
        Input("terms-store", "data"),
        prevent_initial_call=True,
    )
    def update_word_freq_plot(terms_dict):
        """
        Callback that updates the frequency table view.
        """
        if not terms_dict or terms_dict["termtuples"] == []:
            return empty_term_fig

        return plot_word_freq(terms_dict["termtuples"], es_client=app.es_client)

    @app.callback(
        Output("search-hit-column", "figure"),
        Input("terms-store", "data"),
        Input("selected-episode", "data"),
        prevent_initial_call=True,
    )
    def update_transcript_hits_plot(terms_dict, eid):
        """
        Update the transcript hits plot when adding/removing search terms or
        changing the selected episode.
        """
        if not terms_dict or terms_dict["termtuples"] == [] or not eid:
            return empty_term_hit_fig

        return plot_transcript_hits(terms_dict["termtuples"], eid)
