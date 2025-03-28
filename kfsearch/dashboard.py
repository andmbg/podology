import json
from dash import Dash, dcc, html, Input, Output, State, ALL, ctx
import dash_bootstrap_components as dbc

from kfsearch.data.models import EpisodeStore, Episode
from kfsearch.search.search_classes import ResultSet, ResultsPage, diarize_transcript
from kfsearch.search.setup_es import INDEX_NAME
from kfsearch.frontend.utils import clickable_tag

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
    #  ___________
    # | Setup tab |
    #  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
    setup_tab = dbc.Card(
        className="m-0 no-top-border",
        children=dbc.CardBody(
            [
                dbc.Row(

                )
            ]
        )
    )

    #
    #  ____________
    # | Browse tab |
    #  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
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
                dbc.Row(
                    children=[

                        # Transcript of selected episode
                        dbc.Col(
                            children=[
                                # Header: Metadata of the currently selected episode
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
    #  ___________
    # | Terms tab |
    #  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
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

                # Frequency Table view (DEBUG)
                # ----------------------------
                html.Div(
                    id="ft-view",
                    className="mt-3",
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
                        dbc.Tab(browse_tab, label="Browse"),
                        dbc.Tab(terms_tab, label="My Terms"),
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
        Output("episode-list", "children"),
        Output("pagination", "max_value"),
        Output("pagination", "active_page"),
        Input("input", "n_submit"),
        Input("search-button", "n_clicks"),
        Input("pagination", "active_page"),
        State("input", "value"),
    )
    def update_episode_list(n_submit, search_nclicks, active_page, search_term):
        """
        Callback that reacts to search term changes and pagination.
        In:
            - entering new search term (enter or search button)
            - clicking pagination buttons
        Out:
            - list of episodes with hits in them
        """

        # Nothing has happened yet, fill target components with defaults:
        if not ctx.triggered:
            return [], 0, 0

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Trigger was a new search term - reset page to 1:
        page = 1 if trigger_id in ["input", "search-button"] else active_page or 1

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
                current_results_page: ResultsPage = result_set.get_page(page - 1)
                if current_results_page is None:
                    return [], 1, 1

                this_page_hits: dict = current_results_page.episodes
                total_hits = result_set.total_hits
                max_pages = -(-len(result_set.episodes) // 10)  # Ceiling division

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
                    index_name=INDEX_NAME,
                    search_term=term,
                    page_size=10,
                )
                new_freq_entry = {term: {k: len(v) for k, v in result_set.episodes.items()}}
                freq_dict.update(new_freq_entry)

        return freq_dict

    # DEBUG show content of freq list:
    @app.callback(
        Output("ft-view", "children"),
        Input("frequency-dict", "data"),
        prevent_initial_call=True,
    )
    def update_frequency_table_view(frequency_dict):
        """
        Callback that updates the frequency table view.
        """
        pass
