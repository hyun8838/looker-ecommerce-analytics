from dash import html, dcc


def page_header(title: str, description: str):
    return html.Div(
        [
            html.H2(title, className="page-shell-title"),
            html.P(description, className="page-shell-description"),
        ],
        className="page-shell-header",
    )


def kpi_card(title: str, value: str):
    return html.Div(
        [
            html.Div(title, className="kpi-card-title"),
            html.Div(value, className="kpi-card-value"),
        ],
        className="kpi-card",
    )


def kpi_row(cards):
    return html.Div(cards, className="kpi-row")


def chart_card(figure, graph_id=None):
    graph = dcc.Graph(figure=figure, id=graph_id) if graph_id else dcc.Graph(figure=figure)
    return html.Div(graph, className="chart-card")


def chart_grid(figures, columns: int = 2):
    return html.Div(
        [chart_card(fig) for fig in figures],
        className=f"chart-grid chart-grid-{columns}",
    )


def chart_block(children):
    return html.Div(children, className="chart-block")


def insight_box(title: str, items):
    return html.Div(
        [
            html.H4(title, className="insight-title"),
            html.Ul([html.Li(item) for item in items], className="insight-list"),
        ],
        className="insight-box",
    )