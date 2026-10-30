import pandas as pd
from dash import html, dcc, Input, Output, callback

from figures.retention import (
    load_retention_user_data,
    build_cohort_table,
    enrich_user_df_with_order_count,
    apply_period_filter_user,
    apply_period_filter_cohort,
    build_retention_kpi_summary,
    build_repeat_rate_fig,
    build_common_repeat_fig,
    build_status_sensitivity_fig,
    build_order_frequency_fig,
    build_time_to_second_fig,
    build_repeat_window_fig,
    build_cohort_heatmap_fig,
    build_retention_by_source_fig,
    build_retention_by_first_order_value_fig,
    build_retention_by_first_order_size_fig,
    build_cohort_acquisition_trend_fig,
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
    # value != value는 float NaN에서만 True (None은 별도 체크) - pandas/math 의존성 없이 NaN 판별
    return value is None or value != value


def _format_percent(value):
    if _is_missing(value):
        return "-"
    try:
        return f"{value:.1%}"
    except Exception:
        return str(value)


def _format_number(value):
    if _is_missing(value):
        return "-"
    try:
        return f"{value:,.0f}"
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
            "gridTemplateColumns": "repeat(4, minmax(120px, 1fr))",
            "gap": "12px",
            "marginBottom": "20px",
            "alignItems": "end",
        },
    )


def get_layout():
    user_df = load_retention_user_data()

    date_base = user_df["first_order_date"].dropna().sort_values()
    if date_base.empty:
        min_date = max_date = pd.Timestamp.now()
    else:
        min_date = date_base.min()
        max_date = date_base.max()

    year_options = [{"label": str(y), "value": int(y)} for y in range(min_date.year, max_date.year + 1)]
    month_options = [{"label": f"{m:02d}", "value": m} for m in range(1, 13)]

    return html.Div(
        [
            page_header(
                "Page 3. Repeat Loop Diagnosis",
                "Complete 상태 주문 기준의 재구매와 관측기간·주문 상태 선택에 따른 차이를 확인합니다."
            ),

            html.Div(
                [
                    html.H4("Global Filter", style={"marginBottom": "10px"}),

                    _filter_block(
                        [
                            html.Div([
                                html.Label("Start Year"),
                                dcc.Dropdown(
                                    id="retention-start-year",
                                    options=year_options,
                                    value=DEFAULT_START_YEAR if min_date.year <= DEFAULT_START_YEAR <= max_date.year else min_date.year,
                                    clearable=False,
                                ),
                            ]),
                            html.Div([
                                html.Label("Start Month"),
                                dcc.Dropdown(
                                    id="retention-start-month",
                                    options=month_options,
                                    value=1 if min_date.year <= DEFAULT_START_YEAR <= max_date.year else min_date.month,
                                    clearable=False,
                                ),
                            ]),
                            html.Div([
                                html.Label("End Year"),
                                dcc.Dropdown(
                                    id="retention-end-year",
                                    options=year_options,
                                    value=DEFAULT_END_YEAR if min_date.year <= DEFAULT_END_YEAR <= max_date.year else max_date.year,
                                    clearable=False,
                                ),
                            ]),
                            html.Div([
                                html.Label("End Month"),
                                dcc.Dropdown(
                                    id="retention-end-month",
                                    options=month_options,
                                    value=12 if min_date.year <= DEFAULT_END_YEAR <= max_date.year else max_date.month,
                                    clearable=False,
                                ),
                            ]),
                            html.Div([
                                html.Label("Cohort Granularity"),
                                dcc.Dropdown(
                                    id="retention-cohort-granularity",
                                    options=[
                                        {"label": "Day", "value": "day"},
                                        {"label": "Week", "value": "week"},
                                        {"label": "Month", "value": "month"},
                                    ],
                                    value="month",
                                    clearable=False,
                                ),
                            ]),
                            html.Div([
                                html.Label("Cohort Window"),
                                dcc.Dropdown(
                                    id="retention-cohort-window",
                                    options=[
                                        {"label": "Recent 6 Cohorts", "value": 6},
                                        {"label": "Recent 12 Cohorts", "value": 12},
                                        {"label": "Recent 18 Cohorts", "value": 18},
                                        {"label": "Recent 24 Cohorts", "value": 24},
                                    ],
                                    value=12,
                                    clearable=False,
                                ),
                            ]),
                            html.Div([
                                html.Label("Y-axis Label Step"),
                                dcc.Dropdown(
                                    id="retention-cohort-y-step",
                                    options=[
                                        {"label": "Every 1 row", "value": 1},
                                        {"label": "Every 2 rows", "value": 2},
                                        {"label": "Every 3 rows", "value": 3},
                                        {"label": "Every 4 rows", "value": 4},
                                        {"label": "Every 6 rows", "value": 6},
                                    ],
                                    value=1,
                                    clearable=False,
                                ),
                            ]),
                            html.Div([
                                html.Label("Include Within 24h 2nd"),
                                dcc.Dropdown(
                                    id="retention-include-sameday",
                                    options=[
                                        {"label": "Include", "value": "include"},
                                        {"label": "Exclude", "value": "exclude"},
                                    ],
                                    value="include",
                                    clearable=False,
                                ),
                            ]),
                        ]
                    ),
                ],
                style={"marginBottom": "24px"},
            ),

            html.Div(id="retention-kpi-row"),

            chart_block(
                [
                    html.H3("1. Retention Structure", className="section-title"),
                    html.P("반복 구매율 자체와 실제 다회 구매 구조를 함께 확인합니다.", className="page-tab-desc"),
                    html.Div(
                        [
                            _graph_card("retention-repeat-rate-fig"),
                            _graph_card("retention-order-frequency-fig"),
                        ],
                        className="chart-grid chart-grid-2",
                        style={"marginBottom": "28px"},
                    ),
                ]
            ),

            chart_block(
                [
                    html.H3("2. Repeat Timing Quality", className="section-title"),
                    html.P("2차 구매가 언제 발생하는지, 그리고 그것이 장기 retention인지 점검합니다.", className="page-tab-desc"),
                    html.Div(
                        [
                            _graph_card("retention-time-to-second-fig"),
                            _graph_card("retention-repeat-window-fig"),
                        ],
                        className="chart-grid chart-grid-2",
                        style={"marginBottom": "28px"},
                    ),
                ]
            ),

            chart_block(
                [
                    html.H3("3. Cohort Retention", className="section-title"),
                    html.P("첫 Complete 구매 코호트의 달력 기간별 구매율을 확인합니다.", className="page-tab-desc"),
                    html.Div(
                        "0은 관측을 마친 기간에 구매가 없었다는 뜻입니다. 빈칸은 아직 관측을 마치지 못한 기간입니다. "
                        "90일 재구매율·두 번째 구매의 중앙 경과일·24시간 미만 비중은 위 카드에서 선택 코호트 기준으로 확인합니다.",
                        className="caveat-note",
                    ),
                    _graph_card("retention-cohort-heatmap-fig"),
                ]
            ),

            chart_block(
                [
                    html.H3("4. First-order Group Comparisons", className="section-title"),
                    html.P("첫 주문 금액·품목 수·유입별 관측 차이를 비교합니다. 재구매 원인이나 실제 고객 행동을 식별하지 않습니다.", className="page-tab-desc"),
                    html.Div(
                        [
                            _graph_card("retention-driver-source-fig"),
                            _graph_card("retention-driver-value-fig"),
                            _graph_card("retention-driver-size-fig"),
                        ],
                        className="chart-grid chart-grid-3",
                        style={"marginBottom": "28px"},
                    ),
                ]
            ),

            chart_block(
                [
                    html.H3("5. Cohort Acquisition Trend", className="section-title"),
                    html.P(
                        "선택 기간에 첫 Complete 구매를 한 분기 코호트의 적격 재구매율을 비교합니다. "
                        "코호트 간 차이는 합성 데이터의 관찰값이며, 실제 사업의 회복·개선이나 원인을 입증하지 않습니다.",
                        className="page-tab-desc",
                    ),
                    html.Div(
                        [
                            html.Div([
                                html.Label("Repeat Window"),
                                dcc.Dropdown(
                                    id="retention-trend-window",
                                    options=[
                                        {"label": "90 Days", "value": "90"},
                                        {"label": "180 Days", "value": "180"},
                                        {"label": "365 Days", "value": "365"},
                                    ],
                                    value="90",
                                    clearable=False,
                                ),
                            ], style={"maxWidth": "220px", "marginBottom": "16px"}),
                        ]
                    ),
                    _graph_card("retention-cohort-trend-fig"),
                ]
            ),

            chart_block([
                html.H3("6. Comparable Windows & Status Sensitivity", className="section-title"),
                html.P("왼쪽은 365일 관찰을 마친 동일 Complete 고객의 누적 재구매율입니다. 오른쪽은 구매 인정 상태를 넓혔을 때의 계산 차이이며 고객 집단과 첫 주문일도 달라집니다. 취소 주문은 두 기준 모두 제외합니다.", className="page-tab-desc"),
                html.Div([_graph_card("retention-common-repeat-fig"), _graph_card("retention-status-sensitivity-fig")], className="chart-grid chart-grid-2"),
            ]),
            insight_box(
                "Interpretation",
                [
                    '주요 지표는 Complete 상태 기준입니다. 실제 결제·배송 완료 여부와 상태 생성 원리는 이 데이터만으로 확인되지 않습니다.',
                    '기간별 적격 고객 지표는 분모가 달라 하나의 증가 곡선이 아닙니다. 기간 비교 곡선은 365일 적격 고객으로 고정합니다. 날짜 필터는 각 상태 기준의 첫 구매 코호트입니다.',
                    '관측 종료까지 두 번째 주문이 없는 고객은 미관측 상태이며 이탈이 확정된 고객이 아닙니다.',
                    '24시간 미만 비율과 중앙 경과일은 두 번째 구매가 관측된 고객의 요약입니다. 동일 세션 여부는 판단할 수 없습니다.',
                    '코호트 히트맵은 달력 기간별 구매율입니다. 관측 완료된 0과 아직 완료되지 않은 기간의 빈칸을 구별합니다.',
                    '첫 구매 시점별 추이는 선택 기간 안의 적격 코호트를 비교합니다. 합성 데이터의 차이를 실제 사업 성과로 일반화하지 않습니다.',
                ],
            ),
        ],
        className="page-shell",
    )


@callback(
    Output("retention-kpi-row", "children"),
    Output("retention-repeat-rate-fig", "figure"),
    Output("retention-order-frequency-fig", "figure"),
    Output("retention-time-to-second-fig", "figure"),
    Output("retention-repeat-window-fig", "figure"),
    Output("retention-cohort-heatmap-fig", "figure"),
    Output("retention-driver-source-fig", "figure"),
    Output("retention-driver-value-fig", "figure"),
    Output("retention-driver-size-fig", "figure"),
    Output("retention-cohort-trend-fig", "figure"),
    Output("retention-common-repeat-fig", "figure"),
    Output("retention-status-sensitivity-fig", "figure"),
    Input("retention-start-year", "value"),
    Input("retention-start-month", "value"),
    Input("retention-end-year", "value"),
    Input("retention-end-month", "value"),
    Input("retention-cohort-granularity", "value"),
    Input("retention-cohort-window", "value"),
    Input("retention-cohort-y-step", "value"),
    Input("retention-include-sameday", "value"),
    Input("retention-trend-window", "value"),
)
def update_retention_page(
    start_year,
    start_month,
    end_year,
    end_month,
    cohort_granularity,
    cohort_window,
    cohort_y_step,
    include_sameday_value,
    trend_window,
):
    include_same_day = include_sameday_value == "include"

    user_df_full = load_retention_user_data()
    user_df_full = enrich_user_df_with_order_count(user_df_full)

    cohort_df = build_cohort_table(granularity=cohort_granularity)

    user_df = apply_period_filter_user(
        user_df_full,
        start_year, start_month,
        end_year, end_month
    )

    cohort_df = apply_period_filter_cohort(
        cohort_df,
        start_year, start_month,
        end_year, end_month
    )

    kpi = build_retention_kpi_summary(user_df)

    kpi_children = kpi_row(
        [
            kpi_card("Complete Repeat 90D", _format_percent(kpi["repeat90"])),
            kpi_card("Complete Repeat 365D", _format_percent(kpi["repeat365"])),
            kpi_card("No 2nd Purchase", _format_percent(kpi["no_2nd_purchase_ratio"])),
            kpi_card("Median Days to 2nd", _format_number(kpi["median_days_to_2nd"])),
            kpi_card("Within 24h 2nd Share", _format_percent(kpi["same_day_second_ratio"])),
            kpi_card("Single Purchase Ratio", _format_percent(kpi["single_purchase_ratio"])),
        ]
    )

    repeat_rate_fig = build_repeat_rate_fig(user_df)
    order_frequency_fig = build_order_frequency_fig(user_df)
    time_to_second_fig = build_time_to_second_fig(user_df, include_same_day=include_same_day)
    repeat_window_fig = build_repeat_window_fig(user_df, include_same_day=include_same_day)

    cohort_heatmap_fig = build_cohort_heatmap_fig(
        cohort_df,
        max_cohorts=cohort_window,
        y_tick_step=cohort_y_step,
        max_periods=12,
        granularity=cohort_granularity,
    )

    source_fig = build_retention_by_source_fig(user_df)
    value_fig = build_retention_by_first_order_value_fig(user_df)
    size_fig = build_retention_by_first_order_size_fig(user_df)

    cohort_trend_fig = build_cohort_acquisition_trend_fig(user_df, window=trend_window)

    return (
        kpi_children,
        repeat_rate_fig,
        order_frequency_fig,
        time_to_second_fig,
        repeat_window_fig,
        cohort_heatmap_fig,
        source_fig,
        value_fig,
        size_fig,
        cohort_trend_fig,
        build_common_repeat_fig(user_df),
        build_status_sensitivity_fig(start_year,start_month,end_year,end_month),
    )