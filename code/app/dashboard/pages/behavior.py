import pandas as pd
from dash import html, dcc, Input, Output, callback

from figures.customers import (
    load_behavior_user_base_data,
    apply_period_filter_user,
    apply_behavior_filters,
    build_behavior_kpi_summary,
    build_customer_value_user_share_fig,
    build_customer_value_revenue_share_fig,
    build_customer_value_revenue_mix_donut_fig,
    build_customer_value_combo_fig,
    build_purchase_freq_revenue_index_lollipop_fig,
    build_purchase_freq_concentration_fig,
    build_category_breadth_repeat_dot_fig,
    build_category_breadth_index_heatmap_fig,
    build_basket_size_repeat_dot_fig,
    build_first_order_value_repeat_dot_fig,
)

from data_mart.analysis_contract import default_period
from dashboard.components.page_shell import (
    page_header,
    kpi_card,
    kpi_row,
    chart_block,
    insight_box,
)


DEFAULT_START_YEAR, DEFAULT_END_YEAR = default_period()


def _is_missing(value):
    return value is None or value != value


def _format_number(value):
    if _is_missing(value):
        return "-"
    try:
        return f"{value:,.0f}"
    except Exception:
        return str(value)


def _format_percent(value):
    if _is_missing(value):
        return "-"
    try:
        return f"{value:.1f}%"
    except Exception:
        return str(value)


def _graph_card(graph_id):
    return html.Div(
        dcc.Graph(id=graph_id, config={"displayModeBar": False}),
        style={"width": "100%", "padding": "0"},
    )


def _filter_block(children):
    return html.Div(
        children,
        style={
            "display": "grid",
            "gridTemplateColumns": "repeat(6, minmax(120px, 1fr))",
            "gap": "12px",
            "marginBottom": "20px",
            "alignItems": "end",
        },
    )


def get_layout():
    base_df = load_behavior_user_base_data()

    date_base = base_df["first_order_date"].dropna().sort_values()
    if date_base.empty:
        min_date = max_date = pd.Timestamp.now()
    else:
        min_date = date_base.min()
        max_date = date_base.max()

    year_options = [{"label": str(y), "value": int(y)} for y in range(min_date.year, max_date.year + 1)]
    month_options = [{"label": f"{m:02d}", "value": m} for m in range(1, 13)]

    traffic_options = []
    if "first_traffic_source" in base_df.columns:
        traffic_options = [
            {"label": x, "value": x}
            for x in sorted(base_df["first_traffic_source"].dropna().astype(str).unique().tolist())
        ]

    return html.Div(
        [
            page_header(
                "Page 5. Behavior Segmentation",
                "고객 행동 세그먼트 관점에서 repeat와 revenue 구조를 진단합니다.",
            ),

            html.Div(
                [
                    html.H4("Global Filter", style={"marginBottom": "10px"}),
                    _filter_block(
                        [
                            html.Div([
                                html.Label("Start Year"),
                                dcc.Dropdown(
                                    id="behavior-start-year",
                                    options=year_options,
                                    value=DEFAULT_START_YEAR if min_date.year <= DEFAULT_START_YEAR <= max_date.year else min_date.year,
                                    clearable=False,
                                ),
                            ]),
                            html.Div([
                                html.Label("Start Month"),
                                dcc.Dropdown(
                                    id="behavior-start-month",
                                    options=month_options,
                                    value=1 if min_date.year <= DEFAULT_START_YEAR <= max_date.year else min_date.month,
                                    clearable=False,
                                ),
                            ]),
                            html.Div([
                                html.Label("End Year"),
                                dcc.Dropdown(
                                    id="behavior-end-year",
                                    options=year_options,
                                    value=DEFAULT_END_YEAR if min_date.year <= DEFAULT_END_YEAR <= max_date.year else max_date.year,
                                    clearable=False,
                                ),
                            ]),
                            html.Div([
                                html.Label("End Month"),
                                dcc.Dropdown(
                                    id="behavior-end-month",
                                    options=month_options,
                                    value=12 if min_date.year <= DEFAULT_END_YEAR <= max_date.year else max_date.month,
                                    clearable=False,
                                ),
                            ]),
                            html.Div([
                                html.Label("Repeat Window"),
                                dcc.Dropdown(
                                    id="behavior-repeat-metric",
                                    options=[
                                        {"label": "Repeat 90D", "value": "repeat90"},
                                        {"label": "Repeat 180D", "value": "repeat180"},
                                    ],
                                    value="repeat90",
                                    clearable=False,
                                ),
                            ]),
                            html.Div([
                                html.Label("Traffic Source"),
                                dcc.Dropdown(
                                    id="behavior-traffic-source",
                                    options=traffic_options,
                                    multi=True,
                                    placeholder="All sources",
                                ),
                            ]),
                        ]
                    ),
                ],
                style={"marginBottom": "24px"},
            ),

            html.Div(id="behavior-kpi-row"),

            chart_block(
                [
                    html.H3("1. Segment Structure", className="section-title"),
                    html.P(
                        "첫 Complete 주문 금액의 공통 3분위(Low·Mid·High)로 고객을 분류합니다. 경계값은 전체 스냅샷에서 고정하며 기간·유입 필터를 바꿔도 같은 고객의 그룹은 유지됩니다.",
                        className="page-tab-desc",
                    ),
                    html.Div(
                        [
                            html.Div(_graph_card("behavior-user-share-fig"), style={"flex": 1}),
                            html.Div(_graph_card("behavior-revenue-share-fig"), style={"flex": 1}),
                            html.Div(_graph_card("behavior-revenue-mix-donut-fig"), style={"flex": 0.9}),
                        ],
                        style={"display": "flex", "gap": "16px", "marginBottom": "28px"},
                    ),
                ]
            ),

            chart_block(
                [
                    html.H3("2. Outcomes by First-order Amount", className="section-title"),
                    html.P(
                        "같은 첫 주문 금액 그룹의 Complete 누적매출(첫 주문 포함)과 적격 재구매율을 비교합니다. 매출은 관측 종료까지, 재구매율은 선택한 관측 완료 기간 기준이며 차이를 인과효과로 해석하지 않습니다.",
                        className="page-tab-desc",
                    ),
                    _graph_card("behavior-customer-value-combo-fig"),
                ]
            ),

            chart_block(
                [
                    html.H3("3. Observed Behavior Composition", className="section-title"),
                    html.P(
                        "관측기간 누적 구매 빈도·상품 구성별 매출과 재구매의 동시 분포를 확인합니다.",
                        className="page-tab-desc",
                    ),
                    html.Div(
                        [
                            html.Div(_graph_card("behavior-purchase-freq-revenue-index-fig"), style={"flex": 1}),
                            html.Div(_graph_card("behavior-purchase-freq-concentration-fig"), style={"flex": 1}),
                        ],
                        style={"display": "flex", "gap": "16px", "marginBottom": "16px"},
                    ),
                    html.Div(
                        [
                            html.Div(_graph_card("behavior-category-breadth-repeat-dot-fig"), style={"flex": 1}),
                            html.Div(_graph_card("behavior-category-breadth-heatmap-fig"), style={"flex": 1}),
                        ],
                        style={"display": "flex", "gap": "16px", "marginBottom": "28px"},
                    ),
                ]
            ),

            chart_block(
                [
                    html.H3("4. First-order Comparisons", className="section-title"),
                    html.P(
                        "첫 주문 품목 수·금액 구간별 적격 재구매율을 비교합니다.",
                        className="page-tab-desc",
                    ),
                    html.Div(
                        [
                            html.Div(_graph_card("behavior-basket-size-repeat-dot-fig"), style={"flex": 1}),
                            html.Div(_graph_card("behavior-first-order-value-repeat-dot-fig"), style={"flex": 1}),
                        ],
                        style={"display": "flex", "gap": "16px", "marginBottom": "28px"},
                    ),
                ]
            ),

            insight_box(
                "Interpretation",
                [
                    '기간 필터는 첫 Complete 구매 코호트를 선택합니다. 매출·주문 빈도·품목 카테고리 폭은 관측 종료까지의 누적 구성입니다.',
                    '누적 구매 빈도·카테고리 폭은 재구매 결과를 포함합니다. 원인이나 선행 예측 변수로 해석하지 않습니다.',
                    '첫 주문 금액 그룹은 재구매 이전 변수로 고정합니다. 그룹별 누적매출에는 첫 주문도 포함되므로 High의 큰 매출 비중을 재구매 성향의 근거로 쓰지 않습니다. 첫 주문 특성과 재구매율의 차이는 기술적 비교이며, 합성 데이터에서 실제 고객 행동이나 개선 효과를 추론할 수 없습니다.',
                    'AOV는 선택 고객의 Complete 매출 합/주문 수입니다. 지수100은 선택 모집단 전체 기준이며, 매출/고객 점유 지수는 두 점유율의 비입니다.',
                ],
            ),
        ],
        className="page-shell",
    )


@callback(
    Output("behavior-kpi-row", "children"),
    Output("behavior-user-share-fig", "figure"),
    Output("behavior-revenue-share-fig", "figure"),
    Output("behavior-revenue-mix-donut-fig", "figure"),
    Output("behavior-customer-value-combo-fig", "figure"),
    Output("behavior-purchase-freq-revenue-index-fig", "figure"),
    Output("behavior-purchase-freq-concentration-fig", "figure"),
    Output("behavior-category-breadth-repeat-dot-fig", "figure"),
    Output("behavior-category-breadth-heatmap-fig", "figure"),
    Output("behavior-basket-size-repeat-dot-fig", "figure"),
    Output("behavior-first-order-value-repeat-dot-fig", "figure"),
    Input("behavior-start-year", "value"),
    Input("behavior-start-month", "value"),
    Input("behavior-end-year", "value"),
    Input("behavior-end-month", "value"),
    Input("behavior-repeat-metric", "value"),
    Input("behavior-traffic-source", "value"),
)
def update_behavior_page(
    start_year,
    start_month,
    end_year,
    end_month,
    repeat_metric,
    traffic_sources,
):
    base_df = load_behavior_user_base_data()

    base_df = apply_period_filter_user(
        base_df,
        start_year, start_month,
        end_year, end_month
    )

    base_df = apply_behavior_filters(
        base_df,
        traffic_sources=traffic_sources
    )

    kpi = build_behavior_kpi_summary(base_df, repeat_metric=repeat_metric)

    repeat_label = kpi.get("repeat_label", "Repeat")
    kpi_children = kpi_row(
        [
            kpi_card("Total Users", _format_number(kpi["total_users"])),
            kpi_card("Total Revenue", _format_number(kpi["total_revenue"])),
            kpi_card(repeat_label, _format_percent(kpi["overall_repeat"])),
            kpi_card("Top Revenue First-order Segment", kpi["top_segment"] if kpi["top_segment"] is not None else "-"),
            kpi_card("Top Segment Revenue Share", _format_percent(kpi["top_segment_share"])),
        ]
    )

    return (
        kpi_children,
        build_customer_value_user_share_fig(base_df, repeat_metric=repeat_metric),
        build_customer_value_revenue_share_fig(base_df, repeat_metric=repeat_metric),
        build_customer_value_revenue_mix_donut_fig(base_df, repeat_metric=repeat_metric),
        build_customer_value_combo_fig(base_df, repeat_metric=repeat_metric),
        build_purchase_freq_revenue_index_lollipop_fig(base_df, repeat_metric=repeat_metric),
        build_purchase_freq_concentration_fig(base_df, repeat_metric=repeat_metric),
        build_category_breadth_repeat_dot_fig(base_df, repeat_metric=repeat_metric),
        build_category_breadth_index_heatmap_fig(base_df, repeat_metric=repeat_metric),
        build_basket_size_repeat_dot_fig(base_df, repeat_metric=repeat_metric),
        build_first_order_value_repeat_dot_fig(base_df, repeat_metric=repeat_metric),
    )
