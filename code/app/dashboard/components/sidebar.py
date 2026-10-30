from dash import html, dcc

def get_sidebar(url_prefix="/dashboard/"):
    base = url_prefix.rstrip("/")

    link_style = {
        "display": "block",
        "padding": "10px 0",
        "color": "#050505",
        "textDecoration": "none",
        "fontSize": "15px"
    }

    return html.Div(
        children=[
            html.H2("Ecommerce Dashboard", style={"marginBottom": "24px"}),
            dcc.Link("Page 1. Growth Structure", href=f"{base}/growth", style=link_style),
            dcc.Link("Page 2. Funnel Analysis", href=f"{base}/funnel", style=link_style),
            dcc.Link("Page 3. Retention", href=f"{base}/retention", style=link_style),
            dcc.Link("Page 4. Product Mix", href=f"{base}/product-mix", style=link_style),
            dcc.Link("Page 5. Behavior Segmentation", href=f"{base}/behavior", style=link_style),
        ],
        style={"padding": "24px"}
    )