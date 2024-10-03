import sys
from pathlib import Path
import logging

# from flask import Flask
import pandas as pd
from dash import Dash, dcc, html, Input, Output, State, dash_table#, callback
import dash_bootstrap_components as dbc

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

    # DataTable for text search:
    table_search = dash_table.DataTable(
        id="table-textsearch",
        columns=[
            {"name": "Suchen:", "id": "label_key", "type": "text"},
        ],
        data=catalog.to_dict("records"),
        filter_action="native",
        page_size=15,
        style_cell={
            "overflow": "hidden",
            "textOverflow": "ellipsis",
            "maxWidth": 0,
            "fontSize": 16,
            "font-family": "sans-serif",
        },
        css=[
            {"selector": ".dash-spreadsheet tr", "rule": "height: 45px;"},
        ],
    )

    # define app layout:
    app.layout = html.Div(
        [
            html.Div(className="background-fixed"),
            html.Div(
                className="container",
                children=[
                    dbc.Container(
                        style={"paddingTop": "50px"},
                        children=[
                            # Intro
                            dbc.Row(
                                [
                                    dbc.Col(
                                        "Hello world",
                                        xs={"size": 12},
                                        lg={"size": 8, "offset": 2},
                                    ),
                                ],
                                class_name="para",
                            ),
                            # browsing area
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            dbc.Tabs(
                                                [
                                                    dbc.Tab(
                                                        [fig_sunburst],
                                                        label="Blättern",
                                                        tab_id="keypicker",
                                                    ),
                                                    dbc.Tab(
                                                        [table_search],
                                                        label="Suchen",
                                                        tab_id="textsearch",
                                                    ),
                                                ],
                                                id="tabs",
                                                active_tab="keypicker",
                                            )
                                        ],
                                        xs={"size": 6},
                                        lg={
                                            "size": 6,
                                        },
                                    ),
                                    dbc.Col(
                                        [html.Div([fig_presence])],
                                        xs={"size": 6},
                                        lg={"size": 6},
                                    ),
                                    dbc.Col([], width={"size": 1}),
                                ],
                                class_name="para mt-4",
                            ),
                            # DEBUG: see what comes out of the sunburst clickdata:
                            # dbc.Row([
                            #     dbc.Col([
                            #         html.Div(id="location")
                            #     ])
                            # ]),
                            # ---------------------------------------------------
                            # prose after selection
                            dbc.Row(
                                [
                                    dbc.Col(
                                        md_post_selection,
                                        lg={"size": 8, "offset": 2},
                                        sm=10,
                                    ),
                                ],
                                class_name="para mt-4",
                            ),
                            # clearance timeseries
                            dbc.Row(
                                dbc.Col(fig_ts_clearance, width=12),
                                class_name="para mt-1",
                                # style={"height": "750px"},
                            ),
                            # reset button
                            dbc.Row(
                                dbc.Col(
                                    html.Center([button_reset]),
                                    lg={"size": 8, "offset": 2},
                                    sm=12,
                                ),
                                class_name="",
                            ),
                            # prose between timeseries
                            dbc.Row(
                                [
                                    dbc.Col(
                                        md_between_ts,
                                        lg={"size": 8, "offset": 2},
                                        sm=12,
                                    ),
                                ],
                                class_name="para mt-4",
                            ),
                            # states timeseries
                            dbc.Row(
                                [
                                    dbc.Col(
                                        fig_ts_states,
                                        width=12,
                                    )
                                ],
                                class_name="para mt-1",
                            ),
                            # post-dashboard text
                            dbc.Row(
                                dbc.Col(
                                    md_post_ts,
                                    xs={"size": 12},
                                    lg={"size": 8, "offset": 2},
                                ),
                                class_name="para mt-4",
                            ),
                            # row: Footer
                            dbc.Row(
                                dbc.Col(
                                    html.Center(
                                        "Quelle: PKS Bundeskriminalamt, Berichtsjahre 2013 bis 2023. "
                                        "Es gilt die Datenlizenz Deutschland – Namensnennung – Version 2.0",
                                        style={"height": "200px"},
                                    ),
                                    lg={"size": 6, "offset": 3},
                                    sm=12,
                                    class_name="mt-4",
                                )
                            ),
                        ],
                    )
                ],
            ),
        ]
    )

    init_callbacks(app, data_bund, data_raw)

    return app#.server


def init_callbacks(app, data_bund, data_raw):

    # DEBUG: display sunburst clickdata:
    # @app.callback(
    #     Output("location", "children"),
    #     Input("fig-sunburst", "clickData")
    # )
    # def update_location(clickdata):
    #     return(sunburst_location(clickdata))
    # ---------------------------------

    # Update Presence chart
    @app.callback(
        Output("fig-key-presence", "figure"),
        Input("fig-sunburst", "clickData"),
        Input("table-textsearch", "derived_viewport_data"),
        Input("tabs", "active_tab"),
    )
    def update_presence_chart(keypicker_parent, table_data, active_tab):
        """
        Presence chart
        """
        if active_tab == "keypicker":
            key = sunburst_location(keypicker_parent)

            if (
                key == "root" or key is None
            ):  # just special syntax for when parent is None
                child_keys = data_bund.loc[data_bund.parent.eq("------")].key.unique()
            else:
                child_keys = data_bund.loc[data_bund.parent == key].key.unique()
            selected_keys = child_keys

        elif active_tab == "textsearch":
            selected_keys = []
            for element in table_data:
                selected_keys.append(element["key"])

        colormap = {k: grp.color.iloc[0] for k, grp in data_bund.groupby("key")}

        fig = get_presence_chart(data_bund, selected_keys, colormap)

        return fig

    # Update key store
    # ----------------

    @app.callback(
        Output("keystore", "data", allow_duplicate=True),
        State("keystore", "data"),
        Input("fig-key-presence", "clickData"),
        prevent_initial_call=True,
    )
    def update_keystore(keyselection_old, click_presence):

        if click_presence:
            key_selection_new = keyselection_old
            key_to_add = click_presence["points"][0]["y"]
            if len(key_selection_new) < MAXKEYS:
                key_selection_new.append(key_to_add)

            return key_selection_new

    # Update key store from time series
    # ---------------------------------

    @app.callback(
        Output("keystore", "data", allow_duplicate=True),
        Input("fig-ts-clearance", "clickData"),
        State("keystore", "data"),
        prevent_initial_call=True,
    )
    def update_keystore_from_timeseries(click_clearance, keyselection_old):
        key_to_remove = click_clearance["points"][0]["x"][0:6]
        keyselection_new = keyselection_old
        keyselection_new.remove(key_to_remove)

        return keyselection_new

    # Reset key store
    # ----------------------------------

    @app.callback(
        Output("keystore", "data", allow_duplicate=True),
        Input("reset", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_keystore(clickevent):
        return []

    # Update clearance timeseries from keystore
    # -----------------------------------------

    @app.callback(
        Output("fig-ts-clearance", "figure"),
        Input("keystore", "data"),
        prevent_initial_call=True,
    )
    def update_clearance_from_keystore(keylist):

        if keylist == []:
            return empty_plot(
                f"Bis zu {MAXKEYS} Schlüssel/Delikte<br>"
                "auswählen, um sie hier zu vergleichen!"
            )

        # filter on selected keys:
        df_ts = data_bund.loc[data_bund.key.isin(keylist)].reset_index()

        # remove years in which cases = 0 (prevent div/0):
        df_ts = df_ts.loc[df_ts["count"].gt(0)]

        # prepare transformed columns for bar display:
        df_ts["unsolved"] = df_ts["count"] - df_ts.clearance
        df_ts["clearance_rate"] = df_ts.apply(
            lambda r: round(r["clearance"] / r["count"] * 100, 1), axis=1
        )

        # prepare long shape for consumption by plotting function:
        df_ts = pd.melt(
            df_ts,
            id_vars=[
                "key",
                "state",
                "year",
                "shortlabel",
                "label",
                "color",
                "clearance_rate",
                "count",
            ],
            value_vars=["clearance", "unsolved"],
        )

        fig = get_ts_clearance(df_ts)

        return fig

    # Update state timeseries from keystore
    # -------------------------------------

    @app.callback(
        Output("fig-ts-states", "figure"),
        Input("keystore", "data"),
        prevent_initial_call=True,
    )
    def update_states_from_keystore(keylist):

        if keylist == []:
            return empty_plot(
                "Schlüssel/Delikte auswählen, um hier<br>den Ländervergleich zu sehen!"
            )

        # filter on selected keys:
        df_ts = data_raw.loc[data_raw.key.isin(keylist)].reset_index()

        fig = get_ts_states(df_ts)

        return fig
