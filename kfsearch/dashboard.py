import json
import dash_ag_grid as dag
from dash import Dash, dcc, html, Input, Output, State, ALL, ctx, no_update
import dash_bootstrap_components as dbc
from loguru import logger

from kfsearch.data.models import EpisodeStore
from kfsearch.search.search_classes import (
    ResultSet,
    ResultsPage,
    diarize_transcript,
)
from kfsearch.search.setup_es import TRANSCRIPT_INDEX_NAME, ensure_transcript_index, index_episode_transcript
from kfsearch.stats.preparation import ensure_stats_data
from kfsearch.stats.plotting import plot_word_freq
from kfsearch.frontend.utils import clickable_tag
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
        "duration": e.duration,
        "transcript_exists": "no" if e.transcript_path is None else "yes",
    } for e in episode_store.episodes()
]

def init_dashboard(flask_app, route, es_client):

    # Fill the ES index with transcripts:
    ensure_transcript_index(es_client)
    ensure_stats_data(episode_store)

    app = Dash(
        __name__,
        server=flask_app,
        routes_pathname_prefix=route,
        # relevant for standalone launch, not used by main flask app:
        external_stylesheets=[dbc.themes.CERULEAN],
    )

    app.es_client = es_client

    # AG Grid column definitions for the episode list in the Metadata tab:
    conditional_style  = {
        "function": "params.data.transcript_exists == 'yes' ? {backgroundColor: '#00ff0011'} : (params.data.transcript_exists == 'no' ? {backgroundColor: '#ff000011'} : {backgroundColor: '#ffff0011'})"
    }

    column_defs = [
        {
            "headerName": "EID",
            "field": "eid",
            "maxWidth": 80,
            "cellStyle": conditional_style,
        },
        {
            "headerName": "Publication Date",
            "field": "pub_date",
            "type": "date",
            "sortable": True,
            "filter": True,
            "cellStyle": conditional_style,
            "maxWidth": 170,
        },
        {
            "headerName": "Title",
            "field": "title",
            "sortable": True,
            "filter": True,
            "cellStyle": conditional_style,
        },
        {
            "headerName": "Description",
            "field": "description",
            "cellStyle": {
                "whiteSpace": "pre-wrap",  # Wraps the text
                "wordBreak": "break-word",  # Prevents overflow by breaking words
            },
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
            "maxWidth": 90,
            "cellStyle": conditional_style,
        }
    ]

    #
    #  _________________
    # | Search Metadata |
    #  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
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
                                    defaultColDef={"resizable": True, "sortable": True, "filter": True},
                                    rowModelType="clientSide",
                                    style={"height": "calc(100vh - 200px)", "width": "100%"},
                                    rowData=episode_list,
                                    className="ag-theme-quartz",
                                    dashGridOptions={
                                        "rowSelection": "single",
                                    },
                                ),
                            ],
                            width=12,
                        ),
                    ],
                    className="mt-3",
                ),
            ],
        )
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
                                dbc.Button("Search", id="search-button", color="primary", className="me-1"),
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
                            dcc.Store(id="terms-store", data=[]),
                            html.Div(
                                id="terms-list",
                                className="d-flex flex-row flex-wrap justify-content-center align-items-center",
                            )
                        ],
                        xs=12,
                        md=12,
                        id="keyword-tags",
                        className="p-0 d-flex justify-content-center align-items-center",
                    ),
                    className="mt-3",
                ),

                # Output
                # ----------------
                dbc.Row(
                    children=[

                        # Transcript of selected episode
                        # ------------------------------
                        dbc.Col(
                            children=[
                                # TODO Header: Metadata of the currently selected episode  <<<
                                html.Div(
                                    children = [
                                        dbc.Row([
                                            dbc.Col(
                                                [
                                                    dcc.Store(id="playback-time-store", data=0),
                                                    dbc.Button("⏸", id="play", color="secondary", size="sm", className="me-1"),
                                                    html.H5(html.B("Title"), id="episode-title", className="mb-0 text-truncate"),
                                                ],
                                                width=12,
                                                className="d-flex align-items-center",
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
                                        "box-shadow": "inset 0 6px 12px rgba(0, 0, 0, 0.2)",
                                    },
                                ),
                            ],
                            xs=12,
                            md=6,
                        ),

                        # List of episodes found in search
                        # --------------------------------
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
                                dbc.Row(
                                    children=[
                                        html.Div(
                                            id="episode-list",
                                            children=["Episodes"]
                                        )
                                    ]
                                ),
                                dbc.Row(
                                    dbc.Col(
                                        dbc.Pagination(
                                            id="pagination",
                                            max_value=5,
                                            first_last=True,
                                        ),
                                        width="auto"
                                    ),
                                    align="center",
                                    justify="center"
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
                                dbc.Button("Add", id="add-button-termstab", color="secondary"),
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
                )
            ]
        )
    )


    app.layout = html.Div(
        dbc.Container(
            [
                dcc.Store(id="frequency-dict", data={"": 0}),
                dbc.Tabs(
                    [
                        dbc.Tab(transcribe_tab, label="Metadata"),
                        dbc.Tab(browse_tab, label="Transcripts"),
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
                    className="mt-3"
                ),
            ]
        )
    )

    init_callbacks(app)

    return app  # .server


def init_callbacks(app):
    @app.callback(
        Output("transcribe-episode-list", "rowData"),
        Input("transcribe-episode-list", "selectedRows"),
        State("transcribe-episode-list", "rowData"),
    )
    def transcribe_episode(selected_rows, row_data):
        if selected_rows is None or selected_rows == []:
            return no_update

        logger.debug(selected_rows)

        # Which episode and is it missing?
        is_missing = selected_rows[0]["transcript_exists"] == "no"
        selected_eid = selected_rows[0]["eid"]

        # Clicked on an episode that has no transcript yet:
        if is_missing:
            # TODO color the cell yellow immediately (may take chained callbacks):
            pass

            episode = episode_store.get_episode(selected_eid)
            episode.transcribe()  # DEBUG
            logger.debug(f"Indexing episode {episode.eid}")
            index_episode_transcript(episode, app.es_client)  # DEBUG
            episode_store.to_json()

            for i, row in enumerate(row_data):
                if row["eid"] == selected_eid:
                    row_data[i]["transcript_exists"] = "yes"
                    break

            return row_data

        return no_update

    @app.callback(
        Output("episode-list", "children"),
        Output("pagination", "max_value"),
        Output("pagination", "active_page"),
        Input("input", "n_submit"),
        Input("search-button", "n_clicks"),
        Input("pagination", "active_page"),
        State("input", "value"),
    )
    def update_episode_transcript_search_list(n_submit, search_nclicks, active_page, search_term):
        """
        Callback that reacts to search term changes and pagination.
        In:
            - entering new search term (enter or search button)
            - clicking pagination buttons
            - (State) current search term
        Out:
            - list of episodes with hits in them
        """

        # Nothing has happened yet, fill target components with defaults:
        if not ctx.triggered:
            return [], 0, 0

        if search_term:

            if (
                    (n_submit is not None and n_submit > 0)  # hit enter in search field
                    or (search_nclicks is not None and search_nclicks > 0)  # click Search
                    or active_page  # click pagination buttons
            ):
                page = active_page or 1

                # Get search results as a set:
                page_size = 10

                result_set = ResultSet(
                    es_client=app.es_client,
                    episode_store=episode_store,
                    index_name=TRANSCRIPT_INDEX_NAME,
                    search_term=search_term,
                    page_size=page_size,
                )

                # Get the current result page:
                current_results_page: ResultsPage = result_set.get_page(page - 1)
                if current_results_page is None:
                    return ["No hits found."], 0, 0

                this_page_hits: dict = current_results_page.episodes
                total_hits = result_set.total_hits
                max_pages = -(-len(result_set.episodes) // page_size)  # Ceiling division

                results_page = ResultsPage(this_page_hits, episode_store)
                result_cards = [c.to_html() for c in results_page.cards]

                return result_cards, max_pages, page

        return [], 0, 1


    @app.callback(
        Output("transcript", "children"),
        Input({"type": "result-card", "index": ALL}, "n_clicks"),
        State({"type": "result-card", "index": ALL}, "id"),
        State("input", "value"),
        State("transcript", "children")
    )
    def update_transcript(resultcard_nclicks, card_ids, search_term, current_transcript):
        """
        Callback that reacts to clicks on result cards, given pagination.
        """
        if not ctx.triggered:
            return current_transcript

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if "result-card" in trigger_id and resultcard_nclicks and any(i is not None for i in resultcard_nclicks):
            episode_id = json.loads(trigger_id)["index"]

            diarized_transcript = diarize_transcript(
                eid=episode_id,
                episode_store=episode_store,
                search_term=search_term,
            )

            return diarized_transcript

        return current_transcript


    # Update search terms in the comparison list:
    @app.callback(
        Output("terms-store", "data"),
        Output("terms-list", "children"),
        Output("terms-list-termstab", "children"),
        Input("add-button", "n_clicks"),
        Input("add-button-termstab", "n_clicks"),
        Input({"type": "remove-term", "index": ALL}, "n_clicks"),
        State("input", "value"),
        State("input-termstab", "value"),
        State("terms-store", "data"),
    )
    def update_terms_store(
            add_clicks,
            add_termstab_clicks,
            remove_clicks,
            input_value,
            input_termstab,
            search_terms
    ):
        """
        Callback that reacts to clicks on the Add button or the tags (=remove).

        In:
            - clicking the Add button or a tag
            - the current input value
            - the current list of search terms
        Out:
            - updated list of search terms
        """
        if not ctx.triggered:
            tag_elements = [clickable_tag(i, term) for i, term in enumerate(search_terms)]
            return search_terms, tag_elements, tag_elements

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Add button on first tab was clicked:
        if trigger_id == "add-button" and input_value:
            if input_value not in search_terms:
                search_terms.append(input_value)

        # Add button on terms tab was clicked:
        elif trigger_id == "add-button-termstab" and input_termstab:
            if input_termstab not in search_terms:
                search_terms.append(input_termstab)

        # elif "add-button-termstab" in trigger_id and search_term:
        elif "remove-term" in trigger_id:
            index = int(json.loads(trigger_id)["index"])
            if 0 <= index < len(search_terms):
                search_terms.pop(index)

        tag_elements = [clickable_tag(i, term) for i, term in enumerate(search_terms)]

        return search_terms, tag_elements, tag_elements


    # Update frequency dict:
    @app.callback(
        Output("frequency-dict", "data"),
        Input("terms-store", "data"),
        State("frequency-dict", "data"),
    )
    def update_frequency_dict(terms_in_store, freq_dict):
        """
        Callback that updates the frequency dict when the selection of terms changes.
        """
        # Initialize frequency dict if it is empty:
        if freq_dict is None:
            freq_dict = {}

        # Remove term from frequency dict if it is not in the store anymore:
        for term in list(freq_dict.keys()):
            if term not in terms_in_store:
                freq_dict.pop(term)

        # Add new term to frequency dict if it is not in the list yet:
        for term in terms_in_store:
            if term not in freq_dict:
                result_set = ResultSet(
                    es_client=app.es_client,
                    episode_store=episode_store,
                    index_name=TRANSCRIPT_INDEX_NAME,
                    search_term=term,
                    page_size=10,
                )
                new_freq_entry = {term: {k: len(v) for k, v in result_set.episodes.items()}}
                freq_dict.update(new_freq_entry)

        return freq_dict


    @app.callback(
        Output("word-count-plot", "figure"),
        Input("terms-store", "data"),
        prevent_initial_call=True,
    )
    def update_word_freq_plot(terms):
        """
        Callback that updates the frequency table view.
        """
        if not terms:
            return no_update

        fig = plot_word_freq(terms, es_client=app.es_client)

        return fig
