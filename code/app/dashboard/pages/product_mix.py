from dash import html, dcc, Input, Output, callback

from figures.products import (
    load_product_mix_data,
    build_product_mix_kpi_summary,
    _filter_product_mix_period,
    build_category_share_pie_fig,
    build_department_share_fig,
    build_pareto_fig,
    build_hhi_trend_fig,
    build_topn_share_trend_fig,
    build_category_revenue_trend_fig,
    build_brand_share_within_category_fig,
    build_dept_category_heatmap_fig,
    build_brand_category_heatmap_fig,
    build_department_mix_trend_fig
)

from data_mart.analysis_contract import default_period
from dashboard.components.page_shell import (
    page_header,
    kpi_card,
    kpi_row,
    chart_grid,
    chart_block,
    insight_box,
)


DEFAULT_START_YEAR, DEFAULT_END_YEAR = default_period()


def _format_number(value):
    if value is None:
        return "-"
    try:
        return f"{value:,.0f}"
    except Exception:
        return str(value)


def _format_percent(value):
    if value is None:
        return "-"
    try:
        return f"{value:.1%}"
    except Exception:
        return str(value)


def get_layout():
    df = load_product_mix_data()
    kpi = build_product_mix_kpi_summary(df)

    year_options = ["All"] + sorted(df["order_month"].dt.year.dropna().astype(int).unique().tolist())
    month_options = ["All"] + list(range(1, 13))
    category_options = ["All"] + sorted(df["category"].dropna().astype(str).unique().tolist())
    department_options = ["All"] + sorted(df["department"].dropna().astype(str).unique().tolist())

    return html.Div(
        [
            page_header(
                "Page 4. Product Mix",
                "카테고리, 브랜드, 디파트먼트 구조를 통해 revenue concentration과 portfolio composition을 진단합니다.",
            ),

            html.Div(id="p4-kpis"),

            chart_block(
                [
                    html.H4("Global Period Filter", className="insight-title"),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("Start Year", className="kpi-card-title"),
                                    dcc.Dropdown(
                                        id="p4-start-year",
                                        options=[{"label": str(v), "value": str(v)} for v in year_options],
                                        value=str(DEFAULT_START_YEAR) if str(DEFAULT_START_YEAR) in [str(v) for v in year_options] else "All",
                                        clearable=False,
                                    ),
                                ],
                                style={"flex": "1"},
                            ),
                            html.Div(
                                [
                                    html.Div("Start Month", className="kpi-card-title"),
                                    dcc.Dropdown(
                                        id="p4-start-month",
                                        options=[{"label": str(v), "value": str(v)} for v in month_options],
                                        value="1",
                                        clearable=False,
                                    ),
                                ],
                                style={"flex": "1"},
                            ),
                            html.Div(
                                [
                                    html.Div("End Year", className="kpi-card-title"),
                                    dcc.Dropdown(
                                        id="p4-end-year",
                                        options=[{"label": str(v), "value": str(v)} for v in year_options],
                                        value=str(DEFAULT_END_YEAR) if str(DEFAULT_END_YEAR) in [str(v) for v in year_options] else "All",
                                        clearable=False,
                                    ),
                                ],
                                style={"flex": "1"},
                            ),
                            html.Div(
                                [
                                    html.Div("End Month", className="kpi-card-title"),
                                    dcc.Dropdown(
                                        id="p4-end-month",
                                        options=[{"label": str(v), "value": str(v)} for v in month_options],
                                        value="12",
                                        clearable=False,
                                    ),
                                ],
                                style={"flex": "1"},
                            ),
                        ],
                        style={
                            "display": "flex",
                            "gap": "16px",
                            "marginBottom": "8px",
                            "flexWrap": "wrap",
                        },
                    ),
                ]
            ),

            chart_block(
                [
                    html.H4("1. Market Structure", className="insight-title"),
                    html.Div(id="p4-market-structure-row"),
                ]
            ),

            chart_block(
                [
                    html.H4("2. Category Composition", className="insight-title"),
                    html.Div(
                        [
                            html.Div("Top N for Pie Chart", className="kpi-card-title"),
                            dcc.Dropdown(
                                id="p4-pie-topn",
                                options=[
                                    {"label": "Top 10 + Others", "value": "10"},
                                    {"label": "Top 15 + Others", "value": "15"},
                                    {"label": "Top 20 + Others", "value": "20"},
                                    {"label": "All", "value": "All"},
                                ],
                                value="10",
                                clearable=False,
                            ),
                        ],
                        style={"maxWidth": "320px", "marginBottom": "16px"},
                    ),
                    html.Div(id="p4-composition-row"),
                ]
            ),



            chart_block(
                [
                    html.H4("3. Category Drill-down", className="insight-title"),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("Category", className="kpi-card-title"),
                                    dcc.Dropdown(
                                        id="p4-category",
                                        options=[{"label": c, "value": c} for c in category_options],
                                        value="All",
                                        clearable=False,
                                    ),
                                ],
                                style={"flex": "2"},
                            ),
                        ],
                        style={
                            "display": "flex",
                            "gap": "16px",
                            "marginBottom": "16px",
                            "flexWrap": "wrap",
                        },
                    ),
                    html.Div(id="p4-drilldown-row"),
                ]
            ),

            chart_block(
                [
                    html.H4("4. Heatmap Insight", className="insight-title"),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("Heatmap Type", className="kpi-card-title"),
                                    dcc.Dropdown(
                                        id="p4-heatmap-type",
                                        options=[
                                            {"label": "Department × Category", "value": "dept_category"},
                                            {"label": "Brand × Category (Department filter)", "value": "brand_category"},
                                        ],
                                        value="dept_category",
                                        clearable=False,
                                    ),
                                ],
                                style={"flex": "2"},
                            ),
                            html.Div(
                                [
                                    html.Div("Department Filter", className="kpi-card-title"),
                                    dcc.Dropdown(
                                        id="p4-heatmap-department",
                                        options=[{"label": d, "value": d} for d in department_options],
                                        value="All",
                                        clearable=False,
                                    ),
                                ],
                                style={"flex": "2"},
                            ),
                        ],
                        style={
                            "display": "flex",
                            "gap": "16px",
                            "marginBottom": "16px",
                            "flexWrap": "wrap",
                        },
                    ),
                    html.Div(id="p4-heatmap-row"),
                ]
            ),

            insight_box(
                "Interpretation",
                [
                    "판매액은 Complete 주문 품목의 판매가 합계입니다. 결제·환불을 반영한 순매출이 아니며, 성장 화면의 취소 제외 주문액과 모집단이 다릅니다.",
                    "Pareto, HHI, 상위 10개 비중은 판매액 기준 카테고리 집중도입니다. 판매 건수나 상품 수 기준 집중도와 다를 수 있습니다.",
                    "브랜드 비중은 선택한 카테고리 판매액 안에서의 비중입니다. 소수의 고가 품목이 큰 비중을 만들 수 있어 판매 건수 순위와 같다고 보지 않습니다.",
                    "히트맵은 각 디파트먼트(브랜드 모드에서는 각 브랜드) 판매액을 100%로 본 카테고리 비율입니다. 합성 데이터의 구성 차이를 실제 상품 전략의 성과로 일반화하지 않습니다.",
                ],
            ),
        ],
        className="page-shell",
    )


@callback(
    Output("p4-market-structure-row", "children"),
    Input("p4-start-year", "value"),
    Input("p4-start-month", "value"),
    Input("p4-end-year", "value"),
    Input("p4-end-month", "value"),
)
def update_p4_market_structure(start_year, start_month, end_year, end_month):
    df = load_product_mix_data()
    d = _filter_product_mix_period(
        df,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )

    return html.Div(
        [
            chart_grid(
                [
                    build_pareto_fig(d),
                    build_hhi_trend_fig(d),
                ],
                columns=2,
            ),
            html.Div(style={"height": "16px"}),
            chart_grid(
                [
                    build_topn_share_trend_fig(d, top_n=10),
                ],
                columns=1,
            ),
        ]
    )


@callback(
    Output("p4-composition-row", "children"),
    Input("p4-pie-topn", "value"),
    Input("p4-start-year", "value"),
    Input("p4-start-month", "value"),
    Input("p4-end-year", "value"),
    Input("p4-end-month", "value"),
)
def update_p4_composition(top_n, start_year, start_month, end_year, end_month):
    df = load_product_mix_data()

    d = _filter_product_mix_period(
        df,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )

    return chart_grid(
        [
            build_category_share_pie_fig(
                df,
                top_n=top_n,
                start_year=start_year,
                start_month=start_month,
                end_year=end_year,
                end_month=end_month,
            ),
            build_department_mix_trend_fig(d),
        ],
        columns=2,
    )


@callback(
    Output("p4-drilldown-row", "children"),
    Input("p4-category", "value"),
    Input("p4-start-year", "value"),
    Input("p4-start-month", "value"),
    Input("p4-end-year", "value"),
    Input("p4-end-month", "value"),
)
def update_p4_drilldown(category, start_year, start_month, end_year, end_month):
    df = load_product_mix_data()

    return chart_grid(
        [
            build_category_revenue_trend_fig(
                df,
                category=category,
                start_year=start_year,
                start_month=start_month,
                end_year=end_year,
                end_month=end_month,
            ),
            build_brand_share_within_category_fig(
                df,
                category=category,
                start_year=start_year,
                start_month=start_month,
                end_year=end_year,
                end_month=end_month,
                top_n=10,
            ),
        ],
        columns=2,
    )


@callback(
    Output("p4-heatmap-row", "children"),
    Input("p4-heatmap-type", "value"),
    Input("p4-heatmap-department", "value"),
    Input("p4-start-year", "value"),
    Input("p4-start-month", "value"),
    Input("p4-end-year", "value"),
    Input("p4-end-month", "value"),
)
def update_p4_heatmap(heatmap_type, department, start_year, start_month, end_year, end_month):
    df = load_product_mix_data()
    d = _filter_product_mix_period(
        df,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )

    if heatmap_type == "dept_category":
        fig = build_dept_category_heatmap_fig(d, top_n_x=12, top_n_y=12, ratio_mode="col")
    else:
        fig = build_brand_category_heatmap_fig(d, department=department, top_n_x=12, top_n_y=12, ratio_mode="col")

    return chart_grid([fig], columns=1)

@callback(
    Output("p4-kpis", "children"),
    Input("p4-start-year", "value"),
    Input("p4-start-month", "value"),
    Input("p4-end-year", "value"),
    Input("p4-end-month", "value"),
)
def update_product_kpis(start_year, start_month, end_year, end_month):
    d = _filter_product_mix_period(load_product_mix_data(), start_year, start_month, end_year, end_month)
    k = build_product_mix_kpi_summary(d)
    return kpi_row([kpi_card(label, value) for label, value in [("Complete Item Revenue", _format_number(k["total_revenue"])), ("# Categories", _format_number(k["n_categories"])), ("# Departments", _format_number(k["n_departments"])), ("Top Category Share", _format_percent(k["top_category_share"]))]])
