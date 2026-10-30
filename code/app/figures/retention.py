from functools import lru_cache

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from data_mart.parquet_loader import load_parquet
from data_mart.customer_segments import assign_segments
from data_mart.analysis_contract import OBSERVATION_END, PURCHASE_STATUS
from data_mart.repeat_comparison import summarize_repeat, status_comparison


BAR_PALETTE = [
    "#5B6CFF", "#F45B3F", "#11C5A3", "#A56BEA", "#F5A25D",
    "#2EC7E6", "#F06595", "#A9D86E", "#FFB703", "#8E9AAF"
]


def _to_naive_datetime(series: pd.Series) -> pd.Series:
    """
    tz-aware / tz-naive 혼재 컬럼을 안전하게 naive datetime으로 통일
    """
    s = pd.to_datetime(series, errors="coerce", utc=True)
    return s.dt.tz_convert(None)

def _empty_figure(message: str):
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=16)
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=20),
        height=380
    )
    return fig


def _base_layout(fig, title: str, height: int = 380):
    fig.update_layout(
        title=title,
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=40),
        height=height,
        title_x=0.02,
        legend_title_text="",
        showlegend=False,
    )
    return fig


def _month_end(ts):
    # 마지막 날 자정(00:00:00)이 아니라 그날의 마지막 순간을 반환 -
    # 그렇지 않으면 <= end_date 비교에서 마지막 날 자정 이후 시각을 가진 행이 누락된다.
    return (pd.Timestamp(ts) + pd.offsets.MonthEnd(0)).normalize() + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)


def _build_period_bounds(start_year, start_month, end_year, end_month):
    start_date = pd.Timestamp(int(start_year), int(start_month), 1)
    end_date = _month_end(pd.Timestamp(int(end_year), int(end_month), 1))
    return start_date, end_date



def apply_period_filter_user(df: pd.DataFrame, start_year, start_month, end_year, end_month):
    d = df.copy()
    if "first_order_date" not in d.columns:
        return d

    d["first_order_date"] = _to_naive_datetime(d["first_order_date"])
    start_date, end_date = _build_period_bounds(start_year, start_month, end_year, end_month)

    return d[
        d["first_order_date"].notna() &
        (d["first_order_date"] >= start_date) &
        (d["first_order_date"] <= end_date)
    ].copy()


def apply_period_filter_cohort(df: pd.DataFrame, start_year, start_month, end_year, end_month, period_col="first_order_period"):
    d = df.copy()
    if period_col not in d.columns:
        return d

    d[period_col] = _to_naive_datetime(d[period_col])
    start_date, end_date = _build_period_bounds(start_year, start_month, end_year, end_month)

    return d[
        d[period_col].notna() &
        (d[period_col] >= start_date) &
        (d[period_col] <= end_date)
    ].copy()


def load_retention_user_data() -> pd.DataFrame:
    df = assign_segments(load_parquet("mart_retention_user"))

    date_cols = ["first_order_date", "second_order_date", "last_order_date"]
    for col in date_cols:
        if col in df.columns:
            df[col] = _to_naive_datetime(df[col])

    return df


def load_retention_cohort_data() -> pd.DataFrame:
    df = load_parquet("mart_retention_cohort").copy()

    if "first_order_month" in df.columns:
        df["first_order_month"] = _to_naive_datetime(df["first_order_month"])

    return df


GRANULARITY_LABELS = {"day": "Day", "week": "Week", "month": "Month"}


def _truncate_period(series: pd.Series, granularity: str) -> pd.Series:
    if granularity == "day":
        return series.dt.normalize()
    elif granularity == "week":
        return series.dt.to_period("W-MON").dt.start_time
    elif granularity == "month":
        return series.dt.to_period("M").dt.to_timestamp()
    raise ValueError(f"Unknown granularity: {granularity}")


def _period_diff(later: pd.Series, earlier: pd.Series, granularity: str) -> pd.Series:
    if granularity == "day":
        return (later - earlier).dt.days
    elif granularity == "week":
        return (later - earlier).dt.days // 7
    elif granularity == "month":
        return (later.dt.year - earlier.dt.year) * 12 + (later.dt.month - earlier.dt.month)
    raise ValueError(f"Unknown granularity: {granularity}")


@lru_cache(maxsize=8)
def build_cohort_table(granularity: str = "month") -> pd.DataFrame:
    """
    granularity: "day" / "week" / "month".
    month은 사전집계된 mart_retention_cohort를 그대로 쓰고(성능),
    day/week는 fact_order에서 직접 재계산한다(delivered/complete 주문만, mart_retention_cohort와 동일 필터).
    반환 컬럼: first_order_period(datetime), cohort_index(int), users(int)
    day/week 결과는 granularity별로 캐시되므로(fact_order는 런타임 중 불변 가정),
    Global Filter 등 다른 입력이 바뀌어도 같은 granularity를 다시 고르면 재계산하지 않는다.
    """
    if granularity == "month":
        df = load_retention_cohort_data()
        return df.rename(columns={"first_order_month": "first_order_period"})

    order_df = load_parquet("fact_order").copy()
    required = {"u_id", "order_date", "order_status"}
    if not required.issubset(order_df.columns):
        return pd.DataFrame(columns=["first_order_period", "cohort_index", "users"])

    order_df["order_date"] = _to_naive_datetime(order_df["order_date"])

    d = order_df[order_df["order_status"].isin([PURCHASE_STATUS])].copy()
    d = d.dropna(subset=["u_id", "order_date"])
    d = d[d["order_date"] <= OBSERVATION_END.tz_localize(None)]

    d["order_period"] = _truncate_period(d["order_date"], granularity)

    first_period = (
        d.groupby("u_id", as_index=False)["order_period"]
        .min()
        .rename(columns={"order_period": "first_order_period"})
    )

    d = d.merge(first_period, on="u_id", how="left")
    d["cohort_index"] = _period_diff(d["order_period"], d["first_order_period"], granularity)

    return (
        d.groupby(["first_order_period", "cohort_index"], as_index=False)["u_id"]
        .nunique()
        .rename(columns={"u_id": "users"})
    )


def load_order_count_data() -> pd.DataFrame:
    candidates = ["fact_order", "mart_order", "orders"]

    for name in candidates:
        try:
            df = load_parquet(name).copy()
            print(f"[Retention] loaded order source: {name}, columns={df.columns.tolist()}")
            return df
        except FileNotFoundError as e:
            # 이 후보 이름의 parquet이 아예 없는 정상 케이스만 넘어간다.
            # 그 외 예외(스키마 손상 등)는 후보 탐색으로 숨기지 않고 그대로 올린다.
            print(f"[Retention] no parquet for candidate {name}: {e}")
            continue

    print("[Retention] no order source found")
    return pd.DataFrame()


def enrich_user_df_with_order_count(user_df: pd.DataFrame) -> pd.DataFrame:
    d = user_df.copy()

    if "order_count" in d.columns:
        return d

    order_df = load_order_count_data()
    if order_df.empty:
        return d

    if "order_date" in order_df.columns:
        order_df["order_date"] = _to_naive_datetime(order_df["order_date"])

    if "order_status" in order_df.columns:
        delivered_statuses = {PURCHASE_STATUS}
        order_df = order_df[order_df["order_status"].isin(delivered_statuses)].copy()

    required_cols = {"u_id", "order_date"}
    if not required_cols.issubset(order_df.columns):
        return d

    order_df = order_df[order_df["order_date"] <= OBSERVATION_END.tz_localize(None)]
    order_count = (
        order_df.dropna(subset=["u_id", "order_date"])
        .groupby("u_id", as_index=False)["order_date"]
        .count()
        .rename(columns={"order_date": "order_count"})
    )

    d = d.merge(order_count, on="u_id", how="left")
    return d


def build_retention_kpi_summary(df: pd.DataFrame) -> dict:
    empty_summary = {
        "repeat90": None,
        "repeat180": None,
        "repeat365": None,
        "median_days_to_2nd": None,
        "same_day_second_ratio": None,
        "no_2nd_purchase_ratio": None,
        "single_purchase_ratio": None,
    }

    d = df.copy()
    if "has_order" not in d.columns:
        return empty_summary

    buyers = d[d["has_order"] == 1].copy()

    def _rate(eligible_col, repeat_col):
        if eligible_col not in buyers.columns or repeat_col not in buyers.columns:
            return None

        denom = buyers[eligible_col].fillna(False).sum()
        if denom == 0:
            return None

        num = buyers.loc[buyers[eligible_col].fillna(False), repeat_col].fillna(0).sum()
        return num / denom

    if "days_to_2nd_order" in buyers.columns:
        median_days = buyers["days_to_2nd_order"].dropna()
        median_days = float(median_days.median()) if len(median_days) > 0 else None

        non_null_second = buyers["days_to_2nd_order"].notna().sum()
        same_day_second_ratio = (
            (buyers["days_to_2nd_order"] == 0).sum() / non_null_second
            if non_null_second > 0 else None
        )

        no_2nd_purchase_ratio = buyers["days_to_2nd_order"].isna().mean() if len(buyers) > 0 else None
    else:
        median_days = None
        same_day_second_ratio = None
        no_2nd_purchase_ratio = None

    single_purchase_ratio = None
    if "order_count" in buyers.columns:
        single_purchase_ratio = buyers["order_count"].fillna(0).eq(1).mean()

    return {
        "repeat90": _rate("eligible_90", "repeat_90"),
        "repeat180": _rate("eligible_180", "repeat_180"),
        "repeat365": _rate("eligible_365", "repeat_365"),
        "median_days_to_2nd": median_days,
        "same_day_second_ratio": same_day_second_ratio,
        "no_2nd_purchase_ratio": no_2nd_purchase_ratio,
        "single_purchase_ratio": single_purchase_ratio,
    }


def build_repeat_rate_fig(df: pd.DataFrame):
    d = df.copy()
    buyers = d[d["has_order"] == 1].copy()

    metrics = []
    for label, eligible_col, repeat_col in [
        ("Repeat 90D", "eligible_90", "repeat_90"),
        ("Repeat 180D", "eligible_180", "repeat_180"),
        ("Repeat 365D", "eligible_365", "repeat_365"),
    ]:
        if eligible_col not in buyers.columns or repeat_col not in buyers.columns:
            rate = np.nan
        else:
            eligible_mask = buyers[eligible_col].fillna(False)
            denom = eligible_mask.sum()
            rate = np.nan if denom == 0 else buyers.loc[eligible_mask, repeat_col].fillna(0).sum() / denom

        metrics.append({"metric": label, "rate": rate, "eligible": int(denom) if eligible_col in buyers.columns and repeat_col in buyers.columns else 0})

    plot_df = pd.DataFrame(metrics)
    plot_df["metric_color"] = plot_df["metric"]

    fig = px.bar(
        plot_df,
        x="metric",
        y="rate",
        color="metric_color",
        color_discrete_sequence=BAR_PALETTE,
        text=plot_df["rate"].map(lambda x: f"{x:.1%}" if pd.notna(x) else "-"),
        hover_data={"eligible": True},
    )
    fig.update_yaxes(tickformat=".1%", title="")
    fig.update_xaxes(title="")
    fig.update_traces(textposition="outside", cliponaxis=False)
    return _base_layout(fig, "Complete Repeat Rate — Window-specific Eligible Customers")


def build_order_frequency_fig(df: pd.DataFrame):
    d = df.copy()

    if "order_count" not in d.columns:
        return _empty_figure("order_count not found in mart. Please enrich from fact_order.")

    buyers = d[d["has_order"] == 1].copy()
    if buyers.empty:
        return _empty_figure("No buyer data available")

    buyers["order_count"] = pd.to_numeric(buyers["order_count"], errors="coerce")

    buyers["order_count_bucket"] = buyers["order_count"].apply(
        lambda x: "4+" if pd.notna(x) and x >= 4 else str(int(x)) if pd.notna(x) and x >= 1 else "Unknown"
    )

    order = ["1", "2", "3", "4+"]
    if "Unknown" in buyers["order_count_bucket"].unique():
        # order_count가 NaN인(예: 마트/fact_order 상태 필터 불일치로 매칭 안 된) 구매자를
        # 조용히 누락시키지 않고 별도 버킷으로 노출한다.
        order = order + ["Unknown"]

    plot_df = (
        buyers["order_count_bucket"]
        .value_counts(normalize=True)
        .reindex(order, fill_value=0)
        .reset_index()
    )
    plot_df.columns = ["order_count_bucket", "ratio"]
    plot_df["bucket_color"] = plot_df["order_count_bucket"]

    fig = px.bar(
        plot_df,
        x="order_count_bucket",
        y="ratio",
        color="bucket_color",
        color_discrete_sequence=BAR_PALETTE,
        text=plot_df["ratio"].map(lambda x: f"{x:.1%}")
    )
    fig.update_yaxes(tickformat=".1%", title="")
    fig.update_xaxes(title="Number of Orders")
    fig.update_traces(textposition="outside", cliponaxis=False)
    return _base_layout(fig, "Order Frequency Distribution")


def build_time_to_second_fig(df: pd.DataFrame, include_same_day=True):
    d = df.copy()

    required_cols = {"has_order", "days_to_2nd_order"}
    if not required_cols.issubset(d.columns):
        return _empty_figure(f"Missing columns: {required_cols - set(d.columns)}")

    buyers = d[(d["has_order"] == 1) & (d["days_to_2nd_order"].notna())].copy()

    if buyers.empty:
        return _empty_figure("No second-order data available")

    buyers["days_to_2nd_order"] = pd.to_numeric(buyers["days_to_2nd_order"], errors="coerce")
    buyers = buyers.dropna(subset=["days_to_2nd_order"])

    if not include_same_day:
        buyers = buyers[buyers["days_to_2nd_order"] > 0].copy()

    if {"first_order_date", "second_order_date"}.issubset(buyers.columns):
        elapsed = (pd.to_datetime(buyers["second_order_date"], utc=True) - pd.to_datetime(buyers["first_order_date"], utc=True)).dt.total_seconds() / 86400
        buyers = buyers[elapsed <= 365].copy()
    else:
        buyers = buyers[buyers["days_to_2nd_order"] <= 365].copy()

    if buyers.empty:
        return _empty_figure("No second-order data available after filter")

    fig = px.histogram(
        buyers,
        x="days_to_2nd_order",
        nbins=40,
    )

    if include_same_day:
        fig.add_vline(
            x=0,
            line_dash="dash",
            annotation_text="Within 24h",
            annotation_position="top right"
        )

    fig.update_xaxes(title="Days to 2nd Purchase")
    fig.update_yaxes(title="Users")
    return _base_layout(fig, "Days to 2nd Purchase Distribution (<=365 Days)")


def classify_repeat_window(x):
    if pd.isna(x):
        return "No 2nd Purchase"
    elif x < 1:
        return "Within 24h"
    elif x <= 30:
        return "1-30d"
    elif x <= 60:
        return "(30,60]d"
    elif x <= 90:
        return "(60,90]d"
    elif x <= 180:
        return "(90,180]d"
    elif x <= 365:
        return "(180,365]d"
    else:
        return ">365d"


def build_repeat_window_fig(df: pd.DataFrame, include_same_day=True):
    d = df.copy()

    required_cols = {"has_order", "days_to_2nd_order"}
    if not required_cols.issubset(d.columns):
        return _empty_figure(f"Missing columns: {required_cols - set(d.columns)}")

    buyers = d[d["has_order"] == 1].copy()
    if buyers.empty:
        return _empty_figure("No buyer data available")

    if not include_same_day:
        # within-24h 2차 구매 유저를 모수에서 제거하고 나머지 구간 비율을 다시 계산한다.
        # (제거하지 않으면 Within 24h만 안 보일 뿐 나머지 막대 %가 그대로 남아 잘못된 비율로 보임)
        # days_to_2nd_order는 nullable Int64라 `!= 0`만 쓰면 NA(No 2nd Purchase)가
        # <NA>로 평가돼 boolean indexing에서 함께 사라진다 - isna()를 명시적으로 살려준다.
        days_col = buyers["days_to_2nd_order"]
        buyers = buyers[days_col.isna() | (days_col != 0)].copy()
        if buyers.empty:
            return _empty_figure("No data after excluding within-24h repeat buyers")

    elapsed = (pd.to_datetime(buyers["second_order_date"], utc=True) - pd.to_datetime(buyers["first_order_date"], utc=True)).dt.total_seconds() / 86400
    buyers["repeat_window"] = elapsed.apply(classify_repeat_window)

    order = [
        "Within 24h", "1-30d", "(30,60]d", "(60,90]d",
        "(90,180]d", "(180,365]d", ">365d", "No 2nd Purchase"
    ]
    if not include_same_day:
        order = [w for w in order if w != "Within 24h"]

    plot_df = (
        buyers["repeat_window"]
        .value_counts(normalize=True)
        .reindex(order, fill_value=0)
        .reset_index()
    )
    plot_df.columns = ["repeat_window", "ratio"]
    plot_df["window_color"] = plot_df["repeat_window"]

    fig = px.bar(
        plot_df,
        x="repeat_window",
        y="ratio",
        color="window_color",
        color_discrete_sequence=BAR_PALETTE,
        text=plot_df["ratio"].map(lambda x: f"{x:.1%}")
    )
    fig.update_yaxes(tickformat=".1%", title="")
    fig.update_xaxes(title="")
    fig.update_traces(textposition="outside", cliponaxis=False)
    return _base_layout(fig, "Share of Buyers by Time to 2nd Purchase")


def build_cohort_heatmap_fig(
    df: pd.DataFrame,
    max_cohorts: int = 12,
    max_periods: int = 12,
    y_tick_step: int = 1,
    granularity: str = "month",
):
    d = df.copy()

    period_col = "first_order_period" if "first_order_period" in d.columns else "first_order_month"
    required_cols = {period_col, "cohort_index", "users"}
    if not required_cols.issubset(d.columns):
        return _empty_figure(f"Missing columns: {required_cols - set(d.columns)}")

    cohort_base = (
        d[d["cohort_index"] == 0][[period_col, "users"]]
        .rename(columns={"users": "cohort_size"})
    )

    plot_df = d.merge(cohort_base, on=period_col, how="left")
    plot_df["retention_rate"] = plot_df["users"] / plot_df["cohort_size"]

    pivot = (
        plot_df.pivot_table(
            index=period_col,
            columns="cohort_index",
            values="retention_rate",
            aggfunc="sum"
        )
        .sort_index()
    )

    # Completed periods without purchases are zero; partial/future periods are NA.
    limit = max_periods if max_periods is not None else int(pivot.columns.max())
    pivot = pivot.reindex(columns=range(limit + 1))
    cutoff = OBSERVATION_END.tz_localize(None)
    for cohort in pivot.index:
        for index in pivot.columns:
            start = pd.Timestamp(cohort)
            if granularity == "month":
                period_end = start + pd.DateOffset(months=int(index) + 1)
            else:
                period_end = start + pd.Timedelta(days=(int(index) + 1) * (7 if granularity == "week" else 1))
            if period_end > cutoff:
                pivot.loc[cohort, index] = np.nan
            elif pd.isna(pivot.loc[cohort, index]):
                pivot.loc[cohort, index] = 0.0
    if max_cohorts is not None:
        pivot = pivot.iloc[-max_cohorts:]

    if max_periods is not None:
        valid_cols = [c for c in pivot.columns if c <= max_periods]
        pivot = pivot[valid_cols]

    if pivot.empty:
        return _empty_figure("No cohort data available")

    pivot = pivot.apply(pd.to_numeric, errors="coerce").astype(float)

    date_format = "%Y-%m" if granularity == "month" else "%Y-%m-%d"
    pivot.index = pd.to_datetime(pivot.index).strftime(date_format)

    vals = pivot.to_numpy(dtype=float)
    finite_vals = vals[np.isfinite(vals)]
    zmax = float(finite_vals.max()) if finite_vals.size > 0 and finite_vals.max() > 0 else 1.0

    fig = px.imshow(
        pivot,
        aspect="auto",
        color_continuous_scale="Blues",
        zmin=0,
        zmax=zmax,
    )

    fig.update_traces(text=[[f"{v:.1%}" if np.isfinite(v) else "" for v in row] for row in vals], texttemplate="%{text}")

    granularity_label = GRANULARITY_LABELS.get(granularity, "Month")

    fig.update_traces(
        hovertemplate=f"Cohort=%{{y}}<br>{granularity_label} Index=%{{x}}<br>Purchase rate=%{{z:.1%}}<extra></extra>"
    )

    # y축 라벨 간격 조절
    y_labels = list(pivot.index)
    tick_indices = [i for i in range(len(y_labels)) if i % y_tick_step == 0]
    tickvals = [y_labels[i] for i in tick_indices]
    ticktext = tickvals

    fig.update_yaxes(
        title=f"First Purchase {granularity_label}",
        tickmode="array",
        tickvals=tickvals,
        ticktext=ticktext,
        autorange="reversed",
    )

    fig.update_xaxes(title=f"{granularity_label}s Since First Purchase")

    fig.update_layout(
        coloraxis_colorbar=dict(
            title="Purchase rate",
            tickformat=".0%"
        )
    )

    period_unit = {"day": "D", "week": "W", "month": "M"}.get(granularity, "M")

    return _base_layout(
        fig,
        f"Calendar-period Purchase Rate (partial periods blank) ({granularity_label}, Recent {max_cohorts} Cohorts, 0-{max_periods}{period_unit})",
        height=520
    )

def build_retention_by_source_fig(df: pd.DataFrame):
    d = df.copy()
    buyers = d[d["has_order"] == 1].copy()

    required_cols = {"first_traffic_source", "eligible_90", "repeat_90"}
    if not required_cols.issubset(buyers.columns):
        return _empty_figure(f"Missing columns: {required_cols - set(buyers.columns)}")

    buyers["first_traffic_source"] = buyers["first_traffic_source"].fillna("Unknown")
    plot_df = (
        buyers[buyers["eligible_90"].fillna(False)]
        .groupby("first_traffic_source", as_index=False)
        .agg(
            users=("u_id", "nunique"),
            repeat90=("repeat_90", "mean")
        )
        .sort_values("users", ascending=False)
        .head(10)
    )

    if plot_df.empty:
        return _empty_figure("No eligible 90-day source data")

    plot_df["color_key"] = plot_df["first_traffic_source"]

    fig = px.bar(
        plot_df,
        x="first_traffic_source",
        y="repeat90",
        color="color_key",
        color_discrete_sequence=BAR_PALETTE,
        text=plot_df["repeat90"].map(lambda x: f"{x:.1%}"),
        hover_data=["users"],
    )
    fig.update_yaxes(tickformat=".1%", title="")
    fig.update_xaxes(title="")
    fig.update_traces(textposition="outside", cliponaxis=False)
    return _base_layout(fig, "Repeat 90D by Traffic Source")


def build_retention_by_first_order_value_fig(df: pd.DataFrame):
    d = df.copy()
    buyers = d[(d["has_order"] == 1) & (d["eligible_90"].fillna(False))].copy()

    required_cols = {"first_order_revenue", "repeat_90"}
    if not required_cols.issubset(buyers.columns):
        return _empty_figure(f"Missing columns: {required_cols - set(buyers.columns)}")

    buyers = buyers[buyers["first_order_revenue"].notna()].copy()
    if buyers.empty:
        return _empty_figure("No first order revenue data")

    buyers = assign_segments(buyers)
    buyers["first_order_value_bucket"] = buyers["first_order_value_seg"]

    plot_df = (
        buyers.groupby("first_order_value_bucket", as_index=False, observed=True)
        .agg(
            users=("u_id", "nunique"),
            repeat90=("repeat_90", "mean")
        )
    )

    plot_df["color_key"] = plot_df["first_order_value_bucket"].astype(str)

    fig = px.bar(
        plot_df,
        x="first_order_value_bucket",
        y="repeat90",
        color="color_key",
        color_discrete_sequence=BAR_PALETTE,
        text=plot_df["repeat90"].map(lambda x: f"{x:.1%}"),
        hover_data=["users"],
    )
    fig.update_yaxes(tickformat=".1%", title="")
    fig.update_xaxes(title="")
    fig.update_traces(textposition="outside", cliponaxis=False)
    return _base_layout(fig, "Repeat 90D<br><sup>First-order Amount Segment</sup>")


def build_retention_by_first_order_size_fig(df: pd.DataFrame):
    d = df.copy()
    buyers = d[(d["has_order"] == 1) & (d["eligible_90"].fillna(False))].copy()

    required_cols = {"first_item_count", "repeat_90"}
    if not required_cols.issubset(buyers.columns):
        return _empty_figure(f"Missing columns: {required_cols - set(buyers.columns)}")

    buyers = buyers[buyers["first_item_count"].notna()].copy()
    if buyers.empty:
        return _empty_figure("No first item count data")

    buyers["first_order_size_bucket"] = pd.cut(
        buyers["first_item_count"],
        bins=[0, 1, 2, 3, 5, np.inf],
        labels=["1", "2", "3", "4-5", "6+"],
        include_lowest=True
    )

    plot_df = (
        buyers.groupby("first_order_size_bucket", as_index=False, observed=True)
        .agg(
            users=("u_id", "nunique"),
            repeat90=("repeat_90", "mean")
        )
    )

    plot_df["color_key"] = plot_df["first_order_size_bucket"].astype(str)

    fig = px.bar(
        plot_df,
        x="first_order_size_bucket",
        y="repeat90",
        color="color_key",
        color_discrete_sequence=BAR_PALETTE,
        text=plot_df["repeat90"].map(lambda x: f"{x:.1%}"),
        hover_data=["users"],
    )
    fig.update_yaxes(tickformat=".1%", title="")
    fig.update_xaxes(title="First Order Item Count")
    fig.update_traces(textposition="outside", cliponaxis=False)
    return _base_layout(fig, "Repeat 90D by First Order Size")


def build_cohort_acquisition_trend_fig(df: pd.DataFrame, window: str = "90"):
    """
    코호트(첫 구매 분기)별 재구매율 추세.
    window: "90" / "180" / "365" - dim_user에 이미 계산된 eligible_X/repeat_X를 그대로 토글.
    """
    d = df.copy()

    eligible_col = f"eligible_{window}"
    repeat_col = f"repeat_{window}"
    required_cols = {"has_order", "first_order_date", eligible_col, repeat_col}
    if not required_cols.issubset(d.columns):
        return _empty_figure(f"Missing columns: {required_cols - set(d.columns)}")

    buyers = d[d["has_order"] == 1].copy()
    buyers = buyers[buyers["first_order_date"].notna() & buyers[eligible_col].fillna(False)].copy()
    if buyers.empty:
        return _empty_figure("No eligible buyers for this window")

    buyers["cohort"] = buyers["first_order_date"].dt.to_period("Q").astype(str)

    plot_df = (
        buyers.groupby("cohort", as_index=False)
        .agg(users=("u_id", "nunique"), repeat_rate=(repeat_col, "mean"))
        .sort_values("cohort")
    )

    fig = px.line(
        plot_df,
        x="cohort",
        y="repeat_rate",
        markers=True,
        text=plot_df["repeat_rate"].map(lambda x: f"{x:.1%}"),
        hover_data={"users": True},
    )
    fig.update_traces(
        textposition="top center",
        line=dict(color=BAR_PALETTE[0], width=3),
        marker=dict(size=7),
    )
    fig.update_yaxes(tickformat=".0%", title=f"Repeat {window}D Rate", rangemode="tozero")
    fig.update_xaxes(title="Cohort (First Purchase Quarter)")

    return _base_layout(
        fig,
        f"Cohort Acquisition Trend — Repeat {window}D Rate by First-Purchase Cohort",
        height=420,
    )

def build_common_repeat_fig(df):
    t=summarize_repeat(df[df.has_order.eq(1)],common_window=365)
    if t.eligible.max()==0:
        return _empty_figure("No 365-day eligible Complete customers in selected cohort")
    fig=go.Figure(go.Scatter(x=t.window_days,y=t.rate,mode='lines+markers+text',
        text=[f'{r:.1%}' for r in t.rate],textposition='top center',
        customdata=t[['repeat','eligible']],
        hovertemplate='%{x} days: %{y:.2%}<br>Repeat %{customdata[0]} / eligible %{customdata[1]}<extra></extra>'))
    fig.update_yaxes(title='Cumulative second-order share',tickformat='.0%',rangemode='tozero')
    fig.update_xaxes(title='Elapsed days since first Complete order',tickvals=[90,180,365])
    return _base_layout(fig,f'Complete Repeat<br><sup>Same 365-day Eligible Customers (n={int(t.eligible.iloc[0]):,})</sup>')


def build_status_sensitivity_fig(start_year,start_month,end_year,end_month):
    t=status_comparison(start_year,start_month,end_year,end_month)
    fig=px.bar(t,x='window_days',y='rate',color='status_basis',barmode='group',
        text=t.rate.map(lambda v: f'{v:.1%}' if pd.notna(v) else '-'),
        hover_data={'repeat':True,'eligible':True},color_discrete_sequence=BAR_PALETTE)
    fig.update_yaxes(title='Second-order share',tickformat='.0%',rangemode='tozero')
    fig.update_xaxes(title='Elapsed days; each status uses its own first-order cohort',type='category')
    fig=_base_layout(fig,'Order-status Sensitivity — Different Eligible Populations')
    fig.update_layout(showlegend=True,legend=dict(orientation='h',y=-0.25))
    return fig
