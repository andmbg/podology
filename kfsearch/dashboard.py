import os
import json
import base64

import dash_ag_grid as dag
from dash import Dash, dcc, html, Input, Output, State, ALL, ctx, no_update
import dash_bootstrap_components as dbc
from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch

from kfsearch.data.models import Episode, EpisodeStore, DiarizedTranscript
from kfsearch.search.search_classes import ResultSet, create_cards
from kfsearch.search.setup_es import (
    TRANSCRIPT_INDEX_NAME,
    index_all_transcripts,
    index_episode_worker,
)
from kfsearch.stats.preparation import ensure_stats_data
from kfsearch.stats.plotting import plot_word_freq
from kfsearch.frontend.utils import clickable_tag, colorway, get_sort_button
from config import PROJECT_NAME, CONNECTOR, TRANSCRIBER

episode_store = EpisodeStore(name=PROJECT_NAME)
episode_store.set_connector(CONNECTOR)
episode_store.set_transcriber(TRANSCRIBER)
episode_store.populate()
episode_store.to_json()

# Metadata tab: Pre-sort episode list by publication date:
episode_list = [
    {
        "eid": e.eid,
        "pub_date": e.pub_date,
        "title": e.title,
        "description": e.description,
        "description_text": BeautifulSoup(e.description, "html.parser").get_text(),
        "duration": e.duration,
        "transcript_exists": "Get" if e.transcript_path is None else "✅",
    }
    for e in episode_store.episodes()
]


def init_dashboard(flask_app, route):
    """
    Main function to initialize the dashboard.
    """

    # Fill the ES index with transcripts:
    try:
        es_client = Elasticsearch(
            "http://localhost:9200",
            basic_auth=(os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASSWORD")),
            # verify_certs=True,
            # ca_certs=basedir / "http_ca.crt"
        )
    except TypeError:
        print("Elasticsearch client not initialized. Check environment variables.")
        return

    index_all_transcripts(episode_store)
    ensure_stats_data(episode_store)

    app = Dash(
        __name__,
        server=flask_app,
        routes_pathname_prefix=route,
        # relevant for standalone launch, not used by main flask app:
        # FIXME this overrides our custom CSS!
        external_stylesheets=[dbc.themes.CERULEAN],
    )

    app.es_client = es_client

    #
    #  _________________
    # | Search Metadata |
    #  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾

    # AG Grid column definitions for the episode list in the Metadata tab:
    conditional_style = {
        "function": "params.data.transcript_exists == '✅' ? {backgroundColor: '#00ff0011'} : ("
        "params.data.transcript_exists == 'Get' ? {backgroundColor: '#ff000011'} : {backgroundColor: "
        "'#ffff0033'})"
    }

    column_defs = [
        {
            "headerName": "EID",
            "field": "eid",
            "maxWidth": 80,
            "cellStyle": conditional_style,
            "hide": True,
        },
        {
            "headerName": "Date",
            "field": "pub_date",
            "type": "date",
            "sortable": True,
            "filter": True,
            "cellStyle": conditional_style,
            "maxWidth": 120,
        },
        {
            "headerName": "Title",
            "field": "title",
            "sortable": True,
            "filter": True,
            "maxWidth": 600,
            "cellStyle": conditional_style,
        },
        {
            "headerName": "Description",
            "field": "description_text",
            "tooltipField": "description",
            "tooltipComponent": "CustomTooltip",
            "cellStyle": conditional_style,
        },
        {
            "headerName": "Duration",
            "field": "duration",
            "sortable": True,
            "filter": True,
            "maxWidth": 100,
            "cellStyle": conditional_style,
        },
        {
            "headerName": "Script",
            "field": "transcript_exists",
            "maxWidth": 70,
            "cellStyle": conditional_style,
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
                                    rowData=episode_list,
                                    className="ag-theme-quartz",
                                    dashGridOptions={
                                        "rowSelection": "single",
                                        "tooltipShowDelay": 0,
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
                # Input (search field)
                # --------------------
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
                                dbc.Button("Add", id="add-button", color="secondary"),
                            ],
                            width=2,
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
                #
                # Output
                # ----------------
                dbc.Row(
                    children=[
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
                                                        dbc.Button(
                                                            "⏸",
                                                            id="play",
                                                            color="secondary",
                                                            size="sm",
                                                            className="me-1",
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
                                    ],
                                    className="mb-3",
                                ),
                                html.Div(
                                    id="transcript",
                                    className="transcript",
                                ),
                            ],
                            xs=12,
                            md=6,
                        ),
                        #
                        # List of episodes found in search
                        # --------------------------------
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
                                #
                                # Wordcloud
                                # ----------------
                                dbc.Row(dbc.Col(html.Div(id="wordcloud"))),
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
    #  _______________
    # | Analyse Terms |
    #  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
    terms_tab = dbc.Card(
        className="m-0 no-top-border",
        children=dbc.CardBody(
            [
                # Input (search field)
                # --------------------
                dbc.Row(
                    [
                        dbc.Col(width=4),
                        dbc.Col(
                            [
                                dbc.Input(
                                    id="input-termstab",
                                    type="text",
                                    placeholder="Enter search term",
                                    debounce=True,
                                ),
                            ],
                            width=4,
                        ),
                        dbc.Col(
                            [
                                dbc.Button(
                                    "Add", id="add-button-termstab", color="secondary"
                                ),
                            ],
                            width=2,
                        ),
                    ],
                    className="mt-3",
                ),
                # Term Tags
                # ---------
                dbc.Row(
                    dbc.Col(
                        [
                            html.Div(
                                id="terms-list-termstab",
                                className="d-flex flex-row flex-wrap justify-content-center align-items-center",
                            )
                        ],
                        xs=12,
                        md=12,
                        id="keyword-tags-termstab",
                        className="p-0 d-flex justify-content-center align-items-center",
                    ),
                    className="mt-3",
                ),
                # Word frequency plot
                # ----------------------------
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dcc.Graph(
                                    id="word-count-plot",
                                )
                            ],
                            width=12,
                        )
                    ]
                ),
            ]
        ),
    )

    app.layout = html.Div(
        dbc.Container(
            [
                dcc.Store(id="frequency-dict", data={"": 0}),
                dbc.Tabs(
                    [
                        dbc.Tab(transcribe_tab, label="Metadata"),
                        dbc.Tab(browse_tab, label="Transcripts", tab_id="Transcripts"),
                        dbc.Tab(terms_tab, label="Terms"),
                        dbc.Tab(
                            "This tab is under construction",
                            label="Savegames",
                        ),
                        dbc.Tab(
                            "This tab is under construction",
                            label="Global stats",
                        ),
                    ],
                    id="tab-container",
                    className="mt-3",
                ),
            ]
        )
    )

    init_callbacks(app)

    return app  # .server


def init_callbacks(app):
    """
    Initialize the callbacks for the Dash app.
    """
    @app.callback(
        Output("transcribe-episode-list", "rowData"),
        Input("transcribe-episode-list", "selectedRows"),
        Input("transcribe-episode-list", "cellClicked"),
        State("transcribe-episode-list", "rowData"),
    )
    def transcribe_episode(selected_rows, cell_clicked, row_data):
        """
        If you click on the Script column on the Metadata tab, then if that episode has
        no transcript yet, get it, index it, and update the stats, so it will be shown
        in the search results and analyses.
        """
        if (
            selected_rows is None
            or selected_rows == []
            or cell_clicked.get("colId", "") != "transcript_exists"
        ):
            return no_update

        # Which episode and is it missing?
        is_missing = selected_rows[0]["transcript_exists"] == "Get"
        selected_eid = selected_rows[0]["eid"]

        # Clicked on an episode that has no transcript yet:
        if is_missing:
            # TODO color the cell yellow immediately (may take chained callbacks):

            episode: Episode = episode_store[selected_eid]
            episode.transcribe()
            index_episode_worker(episode)
            episode_store.to_json()  # TODO necessary? Doesn't seem to change upon transcription.

            # Update the episode metadata table:
            for i, row in enumerate(row_data):
                if row["eid"] == selected_eid:
                    row_data[i]["transcript_exists"] = "Yes"
                    break

            # Update the stats database:
            ensure_stats_data(episode_store, eid=selected_eid)

            return row_data

        return no_update

    @app.callback(
        Output("tab-container", "active_tab"),
        Input("transcribe-episode-list", "selectedRows"),
    )
    def tab_to_transcript(
        episodes_selected_rows,
    ):
        if episodes_selected_rows:
            eid = episodes_selected_rows[0]["eid"]
            if episode_store[eid].transcript_path is not None:
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
        termtuples = terms_store["termtuples"]

        out = html.Div(
            [get_sort_button(i) for i in termtuples],
        )

        return out

    # @app.callback(
    #     Output("episode-list", "children"),
    #     Input({"type": "sort-button", "index": ALL}, "n_clicks"),
    #     State({"type": "sort-button", "index": ALL}, "id"),
    #     State("episode-list", "children"),
    # )
    # def sort_episode_list(
    #     sortbtn_nclicks,
    #     sortbtn_id,
    #     episode_list,
    # ):
    #     pass

    @app.callback(
        Output("selected-episode", "data"),
        Input("transcribe-episode-list", "selectedRows"),
        Input({"type": "result-card", "index": ALL}, "n_clicks"),
        State({"type": "result-card", "index": ALL}, "id"),
        State("selected-episode", "data"),
    )
    def update_selected_episode(
        episodes_selected_rows,
        resultcard_nclicks,
        resultcard_id,
        current_eid,
    ):

        if not ctx.triggered:
            return no_update

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Click on episode list in meta tab:
        if trigger_id == "transcribe-episode-list" and episodes_selected_rows:
            eid = episodes_selected_rows[0]["eid"]
            if episode_store[eid].transcript_path is not None:
                return eid

        # Click on result card:
        if (
            "result-card" in trigger_id
            and resultcard_nclicks
            and any(i is not None for i in resultcard_nclicks)
        ):
            selected_eid = json.loads(trigger_id)["index"]

            return selected_eid

        return no_update

    @app.callback(
        Output("transcript", "children"),
        Output("wordcloud", "children"),
        Output("transcript-episode-title", "children"),
        Output("transcript-episode-date", "children"),
        Output("transcript-episode-duration", "children"),
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
        dia_script = DiarizedTranscript(episode=episode)
        dia_script_element = dia_script.to_html(termtuples)

        # Get the word cloud of the selected episode as HTML img element:
        with open(episode.wordcloud_path, "rb") as f:
            encoded_image = base64.b64encode(f.read()).decode("utf-8")
            encoded_image = f"data:image/png;base64,{encoded_image}"

        word_cloud_element = html.Img(
            src=encoded_image,
            style={
                "max-height": "300px",
                "width": "100%",
                "object-fit": "contain",
                "margin-top": "1rem",
            },
        )

        return (
            dia_script_element,
            word_cloud_element,
            episode.title,
            episode.pub_date,
            episode.duration,
        )

    # Update search terms in the comparison list:
    @app.callback(
        Output("terms-store", "data"),
        Output("input", "value"),
        Output("input-termstab", "value"),
        Input("input", "n_submit"),
        Input("input-termstab", "n_submit"),
        Input("add-button", "n_clicks"),
        Input("add-button-termstab", "n_clicks"),
        Input({"type": "remove-term", "index": ALL}, "n_clicks"),
        State("input", "value"),
        State("input-termstab", "value"),
        State("terms-store", "data"),
    )
    def update_terms_store(
        n_submit,
        n_submit_termstab,
        add_clicks,
        add_clicks_termstab,
        remove_clicks,
        input_term_searchtab,
        input_term_termstab,
        terms_store,
    ):
        """
        Update the terms Storage by adding the newly entered search term or removing
        the one that just got clicked.

        At the same time, updates the visual representation of the Store.
        """
        if not ctx.triggered:
            return terms_store, None, None

        # Analyse the search term dict into a list of tuples and the color stack:
        old_term_tuples = terms_store["termtuples"]
        old_terms = [i[0] for i in old_term_tuples]
        colorid_stack = terms_store["colorid-stack"]

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # "Add" button on first tab was clicked:
        if trigger_id in ["add-button", "input"] and input_term_searchtab:
            if len(old_term_tuples) < 10 and input_term_searchtab not in old_terms:
                # assign the first available color to the new term_colorid:
                new_term_tuple = (input_term_searchtab, colorid_stack.pop())
                old_term_tuples.append(new_term_tuple)

        # "Add" button on terms tab was clicked:
        elif (
            trigger_id in ["add-button-termstab", "input-termstab"]
            and input_term_termstab
        ):
            if len(old_term_tuples) < 10 and input_term_termstab not in old_terms:
                # assign the first available color to the new term_colorid:
                new_term_tuple = (input_term_termstab, colorid_stack.pop())
                old_term_tuples.append(new_term_tuple)

        # A tag was clicked for removal:
        elif "remove-term" in trigger_id:
            index = int(json.loads(trigger_id)["index"])
            if 0 <= index < len(old_term_tuples):
                freed_colorid = old_term_tuples.pop(index)[1]
                colorid_stack.append(freed_colorid)

        new_terms_colors_dict = {
            "termtuples": old_term_tuples,
            "colorid-stack": colorid_stack,
        }

        return new_terms_colors_dict, None, None

    @app.callback(
        Output("terms-list", "children"),
        Output("terms-list-termstab", "children"),
        Input("terms-store", "data"),
    )
    def update_terms_lists(terms_store):
        tag_elements = [
            clickable_tag(i, term_colorid)
            for i, term_colorid in enumerate(terms_store["termtuples"])
        ]
        return tag_elements, tag_elements

    # # Update frequency dict:
    # @app.callback(
    #     Output("frequency-dict", "data"),
    #     Input("terms-store", "data"),
    #     State("frequency-dict", "data"),
    # )
    # def update_frequency_dict(terms_in_store, freq_dict):
    #     """
    #     Callback that updates the frequency dict when the selection of terms changes.
    #     """
    #     # Initialize frequency dict if it is empty:
    #     if freq_dict is None:
    #         freq_dict = {}

    #     # Remove term_colorid from frequency dict if it is not in the store anymore:
    #     for term in list(freq_dict.keys()):
    #         if term not in terms_in_store:
    #             freq_dict.pop(term)

    #     # Add new term_colorid to frequency dict if it is not in the list yet:
    #     for term in terms_in_store:
    #         if term not in freq_dict:
    #             result_set = ResultSet(
    #                 es_client=app.es_client,
    #                 index_name=TRANSCRIPT_INDEX_NAME,
    #                 search_terms=[term],
    #             )
    #             new_freq_entry = {term: {k: len(v) for k, v in result_set.hits_by_ep.items()}}
    #             freq_dict.update(new_freq_entry)

    #     return freq_dict

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
            return no_update

        return plot_word_freq(terms_dict["termtuples"], es_client=app.es_client)
