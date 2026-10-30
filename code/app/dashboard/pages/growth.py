import pandas as pd
from dash import html, dcc, Input, Output, callback

from figures.growth import (
    load_growth_data,
    load_growth_geo_inputs,
    _filter_growth_period,
    _make_period_label,
    build_kpi_summary,
    build_revenue_area_fig,
    build_new_repeat_stacked_fig,
    build_visitors_mau_fig,
    build_traffic_vs_buyers_fig,
    build_conversion_rate_fig,
    build_aov_orders_fig,
    build_gauge_conversion_fig,
    build_gauge_penetration_fig,
    build_geo_country_revenue_fig,
    build_geo_country_table_fig,
    build_geo_country_trend_fig,
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
        return f"{value:.2%}"
    except Exception:
        return str(value)


def get_layout():
    df = load_growth_data()
    fact_order, dim_user = load_growth_geo_inputs()

    years = sorted(df["order_month"].dt.year.dropna().astype(int).unique().tolist()) if "order_month" in df.columns else []
    year_options = ["All"] + years
    month_options = ["All"] + list(range(1, 13))

    countries = sorted(dim_user["country"].dropna().astype(str).unique().tolist()) if "country" in dim_user.columns else []
    default_country = "United States" if "United States" in countries else (countries[0] if countries else None)

    d0 = _filter_growth_period(
        df,
        start_year=str(DEFAULT_START_YEAR) if str(DEFAULT_START_YEAR) in [str(v) for v in year_options] else "All",
        start_month="1",
        end_year=str(DEFAULT_END_YEAR) if str(DEFAULT_END_YEAR) in [str(v) for v in year_options] else "All",
        end_month="12",
    )
    kpi = build_kpi_summary(d0)

    return html.Div(
        [
            page_header(
                "Page 1. Growth Structure",
                "성장 구조를 revenue, traffic, conversion, revenue efficiency, geography 관점에서 통합적으로 요약합니다.",
            ),

            html.Div(id="p1-kpis"),

            chart_block(
                [
                    html.H4("Global Period Filter", className="insight-title"),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("Start Year", className="kpi-card-title"),
                                    dcc.Dropdown(
                                        id="p1-start-year",
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
                                        id="p1-start-month",
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
                                        id="p1-end-year",
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
                                        id="p1-end-month",
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
                    html.H4("1. Growth Overview", className="insight-title"),
                    html.Div(id="p1-growth-overview-row"),
                ]
            ),

            chart_block(
                [
                    html.H4("2. Traffic & Event Diagnostics", className="insight-title"),
                    html.Div(id="p1-traffic-conversion-row"),
                ]
            ),

            chart_block(
                [
                    html.H4("3. Revenue Efficiency", className="insight-title"),
                    html.Div(id="p1-revenue-efficiency-row"),
                ]
            ),

            chart_block(
                [
                    html.H4("4. Geography", className="insight-title"),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("Selected Country", className="kpi-card-title"),
                                    dcc.Dropdown(
                                        id="p1-selected-country",
                                        options=[{"label": c, "value": c} for c in countries],
                                        value=default_country,
                                        clearable=False,
                                    ),
                                ],
                                style={"flex": "2"},
                            ),
                            html.Div(
                                [
                                    html.Div("Top N Countries", className="kpi-card-title"),
                                    dcc.Dropdown(
                                        id="p1-topn-countries",
                                        options=[
                                            {"label": "Top 5", "value": "5"},
                                            {"label": "Top 10", "value": "10"},
                                            {"label": "Top 15", "value": "15"},
                                            {"label": "Top 20", "value": "20"},
                                            {"label": "All", "value": "All"},
                                        ],
                                        value="10",
                                        clearable=False,
                                    ),
                                ],
                                style={"flex": "1"},
                            ),
                        ],
                        style={
                            "display": "flex",
                            "gap": "16px",
                            "marginBottom": "16px",
                            "flexWrap": "wrap",
                        },
                    ),
                    html.Div(id="p1-geo-row"),
                ]
            ),

            insight_box(
                "Interpretation",
                [
                    '카드는 선택기간의 마지막 관측월 값입니다. MAU는 식별 가능한 이벤트 사용자 수이며 월별 수를 합산한 기간 고유고객 수가 아닙니다.',
                    '주문액과 신규·반복 주문액은 Cancelled 제외(Complete·Shipped·Processing·Returned 포함) 기준입니다. 재구매 화면은 Complete 주문만 사용하므로 서로 다른 모집단입니다. 순매출이 아닙니다.',
                    '구매 이벤트 세션 비중은 데이터 진단 지표입니다. 식별 세션 비중과 같은 값으로 움직이면 구매 이벤트가 식별 여부를 따라 기록된 것이므로 전환 성과 KPI로 쓰지 않습니다. 주문과 연결한 거래 전환율은 이벤트에 주문 ID가 있어야 확인할 수 있습니다.',
                    '주문 구매자와 이벤트 사용자는 서로 다른 집합이라 구매자/MAU 비는 전환 확률이 아니며 100%를 넘을 수도 있습니다.',
                ],
            ),
        ],
        className="page-shell",
    )


@callback(
    Output("p1-growth-overview-row", "children"),
    Output("p1-traffic-conversion-row", "children"),
    Output("p1-revenue-efficiency-row", "children"),
    Input("p1-start-year", "value"),
    Input("p1-start-month", "value"),
    Input("p1-end-year", "value"),
    Input("p1-end-month", "value"),
)
def update_growth_sections(start_year, start_month, end_year, end_month):
    df = load_growth_data()
    d = _filter_growth_period(
        df,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )
    period_label = _make_period_label(start_year, start_month, end_year, end_month)

    overview = chart_grid(
        [
            build_revenue_area_fig(d, period_label=period_label),
            build_new_repeat_stacked_fig(d, period_label=period_label),
        ],
        columns=2,
    )

    traffic = html.Div(
        [
            chart_grid(
                [
                    build_visitors_mau_fig(d, period_label=period_label),
                    build_traffic_vs_buyers_fig(d, period_label=period_label),
                    build_conversion_rate_fig(d, period_label=period_label),
                ],
                columns=2,
            ),
            html.Div(style={"height": "16px"}),
            chart_grid(
                [
                    build_gauge_conversion_fig(d, period_label=period_label),
                    build_gauge_penetration_fig(d, period_label=period_label),
                ],
                columns=2,
            ),
        ]
    )

    efficiency = chart_grid(
        [
            build_aov_orders_fig(d, period_label=period_label),
        ],
        columns=1,
    )

    return overview, traffic, efficiency


@callback(
    Output("p1-geo-row", "children"),
    Input("p1-start-year", "value"),
    Input("p1-start-month", "value"),
    Input("p1-end-year", "value"),
    Input("p1-end-month", "value"),
    Input("p1-selected-country", "value"),
    Input("p1-topn-countries", "value"),
)
def update_geo_section(start_year, start_month, end_year, end_month, selected_country, top_n_countries):
    fact_order, dim_user = load_growth_geo_inputs()

    top_n_countries = "All" if top_n_countries == "All" else int(top_n_countries)
    
    return html.Div(
        [
            chart_grid(
                [
                    build_geo_country_revenue_fig(
                        fact_order,
                        dim_user,
                        start_year=start_year,
                        start_month=start_month,
                        end_year=end_year,
                        end_month=end_month,
                    ),
                    build_geo_country_table_fig(
                        fact_order,
                        dim_user,
                        top_n=top_n_countries,
                        start_year=start_year,
                        start_month=start_month,
                        end_year=end_year,
                        end_month=end_month,
                    ),
                ],
                columns=2,
            ),
            html.Div(style={"height": "16px"}),
            chart_grid(
                [
                    build_geo_country_trend_fig(
                        fact_order,
                        dim_user,
                        selected_country=selected_country,
                        start_year=start_year,
                        start_month=start_month,
                        end_year=end_year,
                        end_month=end_month,
                    ),
                ],
                columns=1,
            ),
        ]
    )

@callback(
    Output("p1-kpis", "children"),
    Input("p1-start-year", "value"),
    Input("p1-start-month", "value"),
    Input("p1-end-year", "value"),
    Input("p1-end-month", "value"),
)
def update_growth_kpis(start_year, start_month, end_year, end_month):
    d = _filter_growth_period(load_growth_data(), start_year, start_month, end_year, end_month)
    k = build_kpi_summary(d)
    orders = d.iloc[-1]["orders"] if not d.empty else None
    from data_mart.analysis_contract import OBSERVATION_END
    if d.empty:
        month_note = "latest month"
    else:
        latest_month = pd.Timestamp(d.iloc[-1]["order_month"]).tz_localize(None)
        partial = latest_month + pd.offsets.MonthBegin(1) > OBSERVATION_END.tz_localize(None)
        month_note = f"latest month: {latest_month:%Y-%m}" + (f", partial through {OBSERVATION_END:%Y-%m-%d %H:%M} UTC" if partial else "")
    return kpi_row([kpi_card(label, value) for label, value in [(f"Non-cancelled Order Amount ({month_note})", _format_number(k["revenue"])), (f"Identified MAU ({month_note})", _format_number(k["mau"])), (f"Buyers ({month_note})", _format_number(k["buyers"])), (f"Non-cancelled Orders ({month_note})", _format_number(orders))]])
