from dash import html, dcc, Input, Output, callback
import pandas as pd

from figures.funnel import (
    load_funnel_session_data,
    filter_funnel_session_data,
    build_transition_table_from_session_df,
    _make_period_label,
    build_entry_event_by_session_type_fig,
    build_top_session_paths_components,
    build_transition_matrix_fig,
    build_cart_bucket_fig,
    build_cart_count_by_source_fig,
    build_cancel_rate_by_entry_event_fig,
    build_member_guest_purchase_fig,
    build_sankey_fig,
    build_funnel_cone_fig,
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
        return f"{int(value):,}"
    except Exception:
        return str(value)


def _format_percent(value):
    if value is None:
        return "-"
    try:
        return f"{value:.1%}"
    except Exception:
        return str(value)


def _build_funnel_kpis(session_df: pd.DataFrame) -> dict:
    total_sessions = session_df["session_id"].nunique() if "session_id" in session_df.columns else 0
    member_rate = session_df["is_member"].mean() if "is_member" in session_df.columns and len(session_df) > 0 else None
    purchase_rate = session_df["has_purchase"].mean() if "has_purchase" in session_df.columns and len(session_df) > 0 else None
    cancel_rate = session_df["has_cancel"].mean() if "has_cancel" in session_df.columns and len(session_df) > 0 else None

    return {
        "total_sessions": total_sessions,
        "member_rate": member_rate,
        "purchase_rate": purchase_rate,
        "cancel_rate": cancel_rate,
    }


def get_layout():
    session_df = load_funnel_session_data()

    years = []
    if "month" in session_df.columns:
        years = sorted(session_df["month"].dt.year.dropna().astype(int).unique().tolist())

    year_options = ["All"] + years
    month_options = ["All"] + list(range(1, 13))

    entry_options = ["All"]
    if "entry_event" in session_df.columns:
        entry_options += sorted(session_df["entry_event"].dropna().astype(str).unique().tolist())

    d0 = filter_funnel_session_data(
        session_df,
        start_year=str(DEFAULT_START_YEAR) if str(DEFAULT_START_YEAR) in [str(v) for v in year_options] else "All",
        start_month="1",
        end_year=str(DEFAULT_END_YEAR) if str(DEFAULT_END_YEAR) in [str(v) for v in year_options] else "All",
        end_month="12",
        session_type="All",
        entry_event="All",
    )
    kpi = _build_funnel_kpis(d0)

    return html.Div(
        [
            page_header(
                "Page 2. Funnel Analysis",
                "Session과 event 기반으로 탐색 흐름과 구매 흐름을 분리해 사용자 여정의 병목을 해석합니다.",
            ),

            html.Div(id="p2-kpis"),

            chart_block(
                [
                    html.H4("Global Filter", className="insight-title"),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("Start Year", className="kpi-card-title"),
                                    dcc.Dropdown(
                                        id="p2-start-year",
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
                                        id="p2-start-month",
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
                                        id="p2-end-year",
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
                                        id="p2-end-month",
                                        options=[{"label": str(v), "value": str(v)} for v in month_options],
                                        value="12",
                                        clearable=False,
                                    ),
                                ],
                                style={"flex": "1"},
                            ),
                            html.Div(
                                [
                                    html.Div("Session Type", className="kpi-card-title"),
                                    dcc.Dropdown(
                                        id="p2-session-type",
                                        options=[
                                            {"label": "All", "value": "All"},
                                            {"label": "Identified", "value": "Member"},
                                            {"label": "Unidentified", "value": "Guest"},
                                        ],
                                        value="All",
                                        clearable=False,
                                    ),
                                ],
                                style={"flex": "1.2"},
                            ),
                            html.Div(
                                [
                                    html.Div("Entry Event", className="kpi-card-title"),
                                    dcc.Dropdown(
                                        id="p2-entry-event",
                                        options=[{"label": v, "value": v} for v in entry_options],
                                        value="All",
                                        clearable=False,
                                    ),
                                ],
                                style={"flex": "1.2"},
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
                    html.H4("1. Funnel Overview", className="insight-title"),
                    html.Div(id="p2-overview-row"),
                ]
            ),

            chart_block(
                [
                    html.H4("2. Entry & Session Path", className="insight-title"),
                    html.Div(id="p2-entry-path-row"),
                ]
            ),

            chart_block(
                [
                    html.H4("3. Cart & Purchase Behavior", className="insight-title"),
                    html.Div(id="p2-cart-row"),
                ]
            ),

            chart_block(
                [
                    html.H4("4. Cancel Events & Identified Sessions", className="insight-title"),
                    html.Div(id="p2-cancel-row"),
                ]
            ),

            insight_box(
                "Interpretation",
                [
                    '세션은 시작월에 귀속하고 이벤트는 관측 종료시각까지만 사용합니다. 종료시각에 진행중인 세션의 후속 행동은 미관측입니다.',
                    '구매·취소율은 purchase·cancel 이벤트가 있는 세션 비율이며, 주문 완료·취소율이 아닙니다.',
                    '식별 세션은 세션 안에 user_id가 있는지로 분류하며 로그인 여부를 뜻하지 않습니다. Purchase Event Presence by Identification에서 구매 이벤트가 식별 세션에만 있으면 구매 이벤트 비중은 식별 비중의 대리값이므로 전환 성과나 회원 효과로 읽지 않습니다. 관측 종료 직전에 시작한 세션은 구매 전에 잘렸을 수 있습니다.',
                    '퍼널은 Product→Cart→Purchase 순차 발생을 확인합니다. Sankey는 인접 이벤트 횟수이며 전이 행렬은 세션 종료를 제외한 다음 이벤트 분포입니다.',
                ],
            ),
        ],
        className="page-shell",
    )


@callback(
    Output("p2-overview-row", "children"),
    Output("p2-entry-path-row", "children"),
    Output("p2-cart-row", "children"),
    Output("p2-cancel-row", "children"),
    Input("p2-start-year", "value"),
    Input("p2-start-month", "value"),
    Input("p2-end-year", "value"),
    Input("p2-end-month", "value"),
    Input("p2-session-type", "value"),
    Input("p2-entry-event", "value"),
)
def update_funnel_sections(start_year, start_month, end_year, end_month, session_type, entry_event):
    session_df = load_funnel_session_data()
    d = filter_funnel_session_data(
        session_df,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
        session_type=session_type,
        entry_event=entry_event,
    )
    period_label = _make_period_label(start_year, start_month, end_year, end_month)
    transition_df = build_transition_table_from_session_df(d)

    fig_path_bar, fig_path_table = build_top_session_paths_components(d, top_n=10)

    overview = chart_grid(
        [
            build_funnel_cone_fig(d, period_label=period_label),
            build_sankey_fig(transition_df, period_label=period_label, top_n_links=10),
        ],
        columns=2,
    )

    entry_path = html.Div(
        [
            chart_grid(
                [
                    build_entry_event_by_session_type_fig(d, period_label=period_label),
                    fig_path_bar,
                ],
                columns=2,
            ),
            html.Div(style={"height": "16px"}),
            chart_grid(
                [
                    build_transition_matrix_fig(d, period_label=period_label),
                    fig_path_table,
                ],
                columns=2,
            ),
        ]
    )

    cart = chart_grid(
        [
            build_cart_bucket_fig(d, period_label=period_label),
            build_cart_count_by_source_fig(d, period_label=period_label),
        ],
        columns=2,
    )

    cancel = chart_grid(
        [
            build_cancel_rate_by_entry_event_fig(d, period_label=period_label),
            build_member_guest_purchase_fig(d, period_label=period_label),
        ],
        columns=2,
    )

    return overview, entry_path, cart, cancel

@callback(
    Output("p2-kpis", "children"),
    Input("p2-start-year", "value"),
    Input("p2-start-month", "value"),
    Input("p2-end-year", "value"),
    Input("p2-end-month", "value"),
    Input("p2-session-type", "value"),
    Input("p2-entry-event", "value"),
)
def update_funnel_kpis(start_year, start_month, end_year, end_month, session_type, entry_event):
    d = filter_funnel_session_data(load_funnel_session_data(), start_year, start_month, end_year, end_month, session_type, entry_event)
    k = _build_funnel_kpis(d)
    return kpi_row([kpi_card(label, value) for label, value in [("Total Sessions (period)", _format_number(k["total_sessions"])), ("Identified Session Share (period)", _format_percent(k["member_rate"])), ("Purchase-event Share (period; proxy)", _format_percent(k["purchase_rate"])), ("Cancel Event Session Rate (period)", _format_percent(k["cancel_rate"]))]])
