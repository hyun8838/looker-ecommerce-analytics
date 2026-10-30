from dash import Dash, html, dcc, Input, Output

from dashboard.components.sidebar import get_sidebar
from dashboard.pages import growth, funnel, retention, product_mix, behavior


def init_dash(server, url_prefix="/dashboard/"):
    dash_app = Dash(
        __name__,
        server=server,
        url_base_pathname=url_prefix,
        suppress_callback_exceptions=True
    )

    dash_app.layout = html.Div(
        children=[
            dcc.Location(id="url", refresh=False),

            html.Div(
                children=[
                    html.Div(
                        get_sidebar(url_prefix=url_prefix),
                        style={
                            "width": "240px",
                            "minWidth": "240px",
                            "borderRight": "1px solid #e5e7eb",
                            "backgroundColor": "#fafafa"
                        }
                    ),
                    html.Div(
                        id="page-content",
                        style={
                            "flex": "1",
                            "padding": "24px 32px"
                        }
                    )
                ],
                style={
                    "display": "flex",
                    "minHeight": "100vh"
                }
            )
        ]
    )

    @dash_app.callback(
        Output("page-content", "children"),
        Input("url", "pathname")
    )
    def render_page(pathname):
        # None 방지
        pathname = pathname or "/"

        # trailing slash 정리
        current = pathname.rstrip("/")
        prefix = url_prefix.rstrip("/")

        # /dashboard 또는 /dashboard/growth 형태를 page key로 변환
        if current == prefix:
            page_key = "growth"
        elif current.startswith(prefix + "/"):
            page_key = current.replace(prefix + "/", "", 1)
        else:
            page_key = ""

        if page_key in ["", "growth"]:
            return growth.get_layout()
        elif page_key == "funnel":
            return funnel.get_layout()
        elif page_key == "retention":
            return retention.get_layout()
        elif page_key == "product-mix":
            return product_mix.get_layout()
        elif page_key == "behavior":
            return behavior.get_layout()
        else:
            return html.Div(
                [
                    html.H2("404"),
                    html.P(f"Page not found. pathname={pathname}")
                ]
            )

    return dash_app