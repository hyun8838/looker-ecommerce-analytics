import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from data_mart.parquet_loader import load_parquet
from data_mart.customer_segments import assign_segments


BAR_PALETTE = [
    "#5B6CFF", "#F45B3F", "#11C5A3", "#A56BEA", "#F5A25D",
    "#2EC7E6", "#F06595", "#A9D86E", "#FFB703", "#8E9AAF"
]

SEGMENT_ORDER = {
    "customer_value_seg": ["Low", "Mid", "High"],
    "first_order_value_seg": ["Low", "Mid", "High"],
    "basket_size_seg": ["1 item", "2 items", "3+ items"],
    "purchase_freq_seg": ["1 order", "2 orders", "3+ orders"],
    "category_breadth_seg": ["1 category", "2 categories", "3+ categories"],
    "time_to_2nd_seg": ["Within 24h", "1-30d", "31-90d", "90d+", "No 2nd purchase"],
}

REPEAT_COL_MAP = {
    "repeat90": ("eligible_90", "repeat_90", "Repeat 90D"),
    "repeat180": ("eligible_180", "repeat_180", "Repeat 180D"),
}


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


def _base_layout(fig, title: str, height: int = 380, showlegend: bool = False):
    fig.update_layout(
        title=title,
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=40),
        height=height,
        title_x=0.02,
        legend_title_text="",
        showlegend=showlegend,
    )
    return fig


def _to_naive_datetime(series: pd.Series) -> pd.Series:
    s = pd.to_datetime(series, errors="coerce", utc=True)
    return s.dt.tz_convert(None)


def _month_end(ts):
    return pd.Timestamp(ts) + pd.offsets.MonthBegin(1)


def _build_period_bounds(start_year, start_month, end_year, end_month):
    start_date = pd.Timestamp(int(start_year), int(start_month), 1)
    end_date = _month_end(pd.Timestamp(int(end_year), int(end_month), 1))
    return start_date, end_date


def _coerce_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    d = df.copy()
    for c in cols:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    return d


def _ordered_segment_table(plot_df: pd.DataFrame, segment_col: str) -> pd.DataFrame:
    d = plot_df.copy()
    order = SEGMENT_ORDER.get(segment_col)
    if order is not None:
        d[segment_col] = pd.Categorical(d[segment_col], categories=order, ordered=True)
        d = d.sort_values(segment_col)
        d[segment_col] = d[segment_col].astype(str)
    return d


def _index_series(s: pd.Series, baseline) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    mean_val = baseline
    if pd.isna(mean_val) or mean_val == 0:
        return pd.Series(np.nan, index=s.index)
    return (s / mean_val) * 100


def load_behavior_user_base_data() -> pd.DataFrame:
    df = load_parquet("mart_behavior_user_base").copy()

    date_cols = ["first_order_date", "second_order_date", "last_order_date"]
    for col in date_cols:
        if col in df.columns:
            df[col] = _to_naive_datetime(df[col])

    num_cols = [
        "days_to_2nd_order",
        "first_order_revenue",
        "aov_delivered",
        "total_revenue_delivered",
        "first_item_count",
        "total_orders_delivered",
        "repeat_90",
        "repeat_180",
        "repeat_365",
        "eligible_90",
        "eligible_180",
        "eligible_365",
        "has_order",
        "unique_category_count",
        "unique_department_count",
    ]
    df = _coerce_numeric(df, num_cols)
    df = enrich_behavior_segments(df)
    return df


def enrich_behavior_segments(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()

    if "basket_size_seg" not in d.columns and "first_item_count" in d.columns:
        def basket_size_segment(x):
            if pd.isna(x):
                return np.nan
            elif x <= 1:
                return "1 item"
            elif x == 2:
                return "2 items"
            else:
                return "3+ items"
        d["basket_size_seg"] = d["first_item_count"].apply(basket_size_segment)

    if "purchase_freq_seg" not in d.columns and "total_orders_delivered" in d.columns:
        def purchase_freq_segment(x):
            if pd.isna(x):
                return np.nan
            elif x == 1:
                return "1 order"
            elif x == 2:
                return "2 orders"
            else:
                return "3+ orders"
        d["purchase_freq_seg"] = d["total_orders_delivered"].apply(purchase_freq_segment)

    d = assign_segments(d)

    if "time_to_2nd_seg" not in d.columns and "days_to_2nd_order" in d.columns:
        def time_to_2nd_segment(x):
            if pd.isna(x):
                return "No 2nd purchase"
            elif x == 0:
                return "Within 24h"
            elif 1 <= x <= 30:
                return "1-30d"
            elif 31 <= x <= 90:
                return "31-90d"
            else:
                return "90d+"
        d["time_to_2nd_seg"] = d["days_to_2nd_order"].apply(time_to_2nd_segment)

    if "category_breadth_seg" not in d.columns and "unique_category_count" in d.columns:
        def category_breadth_segment(x):
            if pd.isna(x):
                return np.nan
            elif x == 1:
                return "1 category"
            elif x == 2:
                return "2 categories"
            else:
                return "3+ categories"
        d["category_breadth_seg"] = d["unique_category_count"].apply(category_breadth_segment)

    return d


def apply_period_filter_user(df: pd.DataFrame, start_year, start_month, end_year, end_month):
    d = df.copy()
    if "first_order_date" not in d.columns:
        return d

    d["first_order_date"] = _to_naive_datetime(d["first_order_date"])
    start_date, end_date = _build_period_bounds(start_year, start_month, end_year, end_month)

    return d[
        d["first_order_date"].notna() &
        (d["first_order_date"] >= start_date) &
        (d["first_order_date"] < end_date)
    ].copy()


def apply_behavior_filters(df: pd.DataFrame, traffic_sources=None):
    d = df.copy()

    if traffic_sources and "first_traffic_source" in d.columns:
        if isinstance(traffic_sources, str):
            traffic_sources = [traffic_sources]
        d = d[d["first_traffic_source"].isin(traffic_sources)].copy()

    return d


def build_segment_kpi_table(df: pd.DataFrame, segment_col: str, repeat_metric: str = "repeat90") -> pd.DataFrame:
    d = df.copy()
    d = d[d["has_order"] == 1].copy()

    if segment_col not in d.columns:
        return pd.DataFrame()

    eligible_col, repeat_col, _ = REPEAT_COL_MAP[repeat_metric]

    base_all = (
        d.groupby(segment_col, observed=False)
        .agg(
            users=("u_id", "nunique"),
            revenue_per_user=("total_revenue_delivered", "mean"),
            orders=("total_orders_delivered", "sum"),
            total_revenue=("total_revenue_delivered", "sum")
        )
        .reset_index()
    )

    if eligible_col in d.columns and repeat_col in d.columns:
        base_repeat = (
            d[d[eligible_col] == 1]
            .groupby(segment_col, observed=False)
            .agg(
                eligible_users=("u_id", "nunique"),
                repeat_rate=(repeat_col, "mean")
            )
            .reset_index()
        )
        out = base_all.merge(base_repeat, on=segment_col, how="left")
    else:
        out = base_all.copy()
        out["eligible_users"] = np.nan
        out["repeat_rate"] = np.nan

    out["aov"] = out["total_revenue"] / out["orders"].replace(0, np.nan)
    total_users = out["users"].sum()
    total_revenue = out["total_revenue"].sum()

    out["user_share"] = out["users"] / total_users * 100 if total_users > 0 else np.nan
    out["revenue_share"] = out["total_revenue"] / total_revenue * 100 if total_revenue > 0 else np.nan

    out["revenue_per_user"] = out["revenue_per_user"]
    out["aov"] = out["aov"]
    out["repeat_rate"] = out["repeat_rate"] * 100

    out = _ordered_segment_table(out, segment_col)
    return out


def build_behavior_kpi_summary(base_df: pd.DataFrame, repeat_metric: str = "repeat90") -> dict:
    d = base_df.copy()
    d = d[d["has_order"] == 1].copy()

    eligible_col, repeat_col, label = REPEAT_COL_MAP[repeat_metric]

    total_users = d["u_id"].nunique() if "u_id" in d.columns else None
    total_revenue = d["total_revenue_delivered"].sum() if "total_revenue_delivered" in d.columns else None

    overall_repeat = None
    if eligible_col in d.columns and repeat_col in d.columns:
        eligible_base = d[d[eligible_col] == 1].copy()
        if len(eligible_base) > 0:
            overall_repeat = eligible_base[repeat_col].mean() * 100

    seg_tbl = build_segment_kpi_table(d, "customer_value_seg", repeat_metric=repeat_metric)

    top_segment = None
    top_segment_share = None
    if not seg_tbl.empty and "revenue_share" in seg_tbl.columns:
        top_row = seg_tbl.sort_values("revenue_share", ascending=False).iloc[0]
        top_segment = top_row["customer_value_seg"]
        top_segment_share = top_row["revenue_share"]

    return {
        "total_users": total_users,
        "total_revenue": total_revenue,
        "overall_repeat": overall_repeat,
        "repeat_label": label,
        "top_segment": top_segment,
        "top_segment_share": top_segment_share,
    }


def build_customer_value_user_share_fig(base_df: pd.DataFrame, repeat_metric: str = "repeat90"):
    plot_df = build_segment_kpi_table(base_df, "customer_value_seg", repeat_metric=repeat_metric)
    if plot_df.empty:
        return _empty_figure("No first-order amount segment data")

    plot_df["color_key"] = plot_df["customer_value_seg"]

    fig = px.bar(
        plot_df,
        x="customer_value_seg",
        y="user_share",
        color="color_key",
        color_discrete_sequence=BAR_PALETTE,
        text=plot_df["user_share"].map(lambda x: f"{x:.1f}%")
    )
    fig.update_yaxes(title="User Share (%)")
    fig.update_xaxes(title="")
    fig.update_traces(textposition="outside", cliponaxis=False)
    return _base_layout(fig, "Customer Share<br><sup>First-order Amount Segments</sup>")


def build_customer_value_revenue_share_fig(base_df: pd.DataFrame, repeat_metric: str = "repeat90"):
    plot_df = build_segment_kpi_table(base_df, "customer_value_seg", repeat_metric=repeat_metric)
    if plot_df.empty:
        return _empty_figure("No first-order amount segment data")

    plot_df["color_key"] = plot_df["customer_value_seg"]

    fig = px.bar(
        plot_df,
        x="customer_value_seg",
        y="revenue_share",
        color="color_key",
        color_discrete_sequence=BAR_PALETTE,
        text=plot_df["revenue_share"].map(lambda x: f"{x:.1f}%")
    )
    fig.update_yaxes(title="Revenue Share (%)")
    fig.update_xaxes(title="")
    fig.update_traces(textposition="outside", cliponaxis=False)
    return _base_layout(fig, "Cumulative Revenue Share<br><sup>First-order Amount Segments</sup>")


def build_customer_value_revenue_mix_donut_fig(base_df: pd.DataFrame, repeat_metric: str = "repeat90"):
    plot_df = build_segment_kpi_table(base_df, "customer_value_seg", repeat_metric=repeat_metric)
    if plot_df.empty:
        return _empty_figure("No first-order amount segment data")

    fig = px.pie(
        plot_df,
        names="customer_value_seg",
        values="revenue_share",
        color="customer_value_seg",
        color_discrete_sequence=BAR_PALETTE,
        hole=0.58,
    )
    fig.update_traces(
        textinfo="percent+label",
        textposition="outside"
    )
    return _base_layout(fig, "Cumulative Revenue Mix<br><sup>First-order Amount Segments</sup>", height=360, showlegend=False)


def build_customer_value_combo_fig(base_df: pd.DataFrame, repeat_metric: str = "repeat90"):
    plot_df = build_segment_kpi_table(base_df, "customer_value_seg", repeat_metric=repeat_metric)
    if plot_df.empty:
        return _empty_figure("No first-order amount segment data")

    _, _, repeat_label = REPEAT_COL_MAP[repeat_metric]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=plot_df["customer_value_seg"],
            y=plot_df["revenue_per_user"],
            name="Revenue per User",
            marker_color=BAR_PALETTE[0],
            text=[f"{v:,.0f}" if pd.notna(v) else "-" for v in plot_df["revenue_per_user"]],
            textposition="outside", cliponaxis=False,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=plot_df["customer_value_seg"],
            y=plot_df["repeat_rate"],
            name=repeat_label,
            mode="lines+markers+text",
            marker=dict(color=BAR_PALETTE[1], size=8),
            line=dict(color=BAR_PALETTE[1], width=2),
            text=[f"{v:.1f}%" if pd.notna(v) else "-" for v in plot_df["repeat_rate"]],
            textposition="top center",
            yaxis="y2",
        )
    )

    # 막대는 아래쪽, 재구매율 선은 위쪽에 두어 두 라벨이 겹치지 않게 축 범위를 나눈다.
    max_revenue = plot_df["revenue_per_user"].max()
    max_repeat = plot_df["repeat_rate"].max()
    fig.update_layout(
        yaxis=dict(title="Revenue per User", range=[0, max_revenue * 1.7] if pd.notna(max_revenue) else None),
        yaxis2=dict(
            title=f"{repeat_label} (%)",
            overlaying="y",
            side="right",
            rangemode="tozero",
            range=[0, max_repeat * 1.2] if pd.notna(max_repeat) and max_repeat > 0 else None,
            dtick=0.5,
            showgrid=False,
        ),
    )
    fig = _base_layout(fig, "First-order Amount Segment: Observed Revenue & Repeat", showlegend=True)
    fig.update_layout(legend=dict(orientation="h", x=1, xanchor="right", y=1.02, yanchor="bottom"))
    return fig


def build_purchase_freq_revenue_index_lollipop_fig(base_df: pd.DataFrame, repeat_metric: str = "repeat90"):
    plot_df = build_segment_kpi_table(base_df, "purchase_freq_seg", repeat_metric=repeat_metric)
    if plot_df.empty:
        return _empty_figure("No purchase frequency segment data")

    plot_df["revenue_per_user_index"] = _index_series(plot_df["revenue_per_user"], base_df["total_revenue_delivered"].sum() / base_df["u_id"].nunique())

    fig = go.Figure()

    for i, row in plot_df.iterrows():
        fig.add_trace(
            go.Scatter(
                x=[100, row["revenue_per_user_index"]],
                y=[row["purchase_freq_seg"], row["purchase_freq_seg"]],
                mode="lines",
                line=dict(color=BAR_PALETTE[0], width=3),
                showlegend=False,
                hoverinfo="skip"
            )
        )

    fig.add_trace(
        go.Scatter(
            x=plot_df["revenue_per_user_index"],
            y=plot_df["purchase_freq_seg"],
            mode="markers+text",
            marker=dict(size=16, color=BAR_PALETTE[1]),
            text=[f"{v:.0f}" if pd.notna(v) else "-" for v in plot_df["revenue_per_user_index"]],
            textposition="middle right",
            name="Revenue per User Index"
        )
    )

    fig.update_yaxes(type="category")
    fig.add_vline(x=100, line_dash="dot", line_color="gray")
    fig.update_xaxes(title="Revenue per User Index (Overall Avg = 100)")
    fig.update_yaxes(title="")
    return _base_layout(fig, "Revenue per User Index by Purchase Frequency", showlegend=False)


def build_purchase_freq_concentration_fig(base_df: pd.DataFrame, repeat_metric: str = "repeat90"):
    plot_df = build_segment_kpi_table(base_df, "purchase_freq_seg", repeat_metric=repeat_metric)
    if plot_df.empty:
        return _empty_figure("No purchase frequency segment data")

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=plot_df["purchase_freq_seg"],
            y=plot_df["revenue_share"],
            name="Revenue Share",
            marker_color=BAR_PALETTE[0],
            text=[f"{v:.1f}%" if pd.notna(v) else "-" for v in plot_df["revenue_share"]],
            textposition="outside", cliponaxis=False,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=plot_df["purchase_freq_seg"],
            y=plot_df["user_share"],
            name="User Share",
            mode="lines+markers+text",
            marker=dict(color=BAR_PALETTE[1], size=8),
            line=dict(color=BAR_PALETTE[1], width=2),
            text=[f"{v:.1f}%" if pd.notna(v) else "-" for v in plot_df["user_share"]],
            textposition="top center",
            yaxis="y2",
        )
    )

    fig.update_layout(
        yaxis=dict(title="Revenue Share (%)",range=[0,100]),
        yaxis2=dict(
            title="User Share (%)",
            overlaying="y",
            side="right",
            range=[0,100]
        ),
    )
    return _base_layout(fig, "Revenue Concentration by Purchase Frequency", showlegend=True)


def build_category_breadth_repeat_dot_fig(base_df: pd.DataFrame, repeat_metric: str = "repeat90"):
    plot_df = build_segment_kpi_table(base_df, "category_breadth_seg", repeat_metric=repeat_metric)
    if plot_df.empty:
        return _empty_figure("No category breadth segment data")

    _, _, repeat_label = REPEAT_COL_MAP[repeat_metric]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=plot_df["category_breadth_seg"],
            y=plot_df["repeat_rate"],
            mode="lines+markers+text",
            line=dict(color=BAR_PALETTE[0], width=3),
            marker=dict(color=BAR_PALETTE[1], size=10),
            text=[f"{v:.1f}%" if pd.notna(v) else "-" for v in plot_df["repeat_rate"]],
            textposition="top center",
            name=repeat_label
        )
    )

    fig.update_yaxes(title=f"{repeat_label} (%)", rangemode="tozero")
    fig.update_xaxes(title="")
    return _base_layout(fig, "Observed Repeat Composition by Cumulative Category Breadth", showlegend=False)


def build_category_breadth_index_heatmap_fig(base_df: pd.DataFrame, repeat_metric: str = "repeat90"):
    plot_df = build_segment_kpi_table(base_df, "category_breadth_seg", repeat_metric=repeat_metric)
    if plot_df.empty:
        return _empty_figure("No category breadth segment data")

    heatmap_tbl = plot_df[[
        "category_breadth_seg",
        "repeat_rate",
        "revenue_per_user",
        "aov",
        "revenue_share"
    ]].copy()

    eligible, repeat, _ = REPEAT_COL_MAP[repeat_metric]
    repeat_base = base_df.loc[base_df[eligible] == 1, repeat].mean() * 100
    heatmap_tbl["repeat_index"] = _index_series(heatmap_tbl["repeat_rate"], repeat_base)
    heatmap_tbl["revenue_per_user_index"] = _index_series(heatmap_tbl["revenue_per_user"], base_df["total_revenue_delivered"].sum() / base_df["u_id"].nunique())
    heatmap_tbl["aov_index"] = _index_series(heatmap_tbl["aov"], base_df["total_revenue_delivered"].sum() / base_df["total_orders_delivered"].sum())
    heatmap_tbl["revenue_share_index"] = heatmap_tbl["revenue_share"] / plot_df["user_share"].replace(0, np.nan) * 100

    heatmap_tbl = heatmap_tbl[[
        "category_breadth_seg",
        "repeat_index",
        "revenue_per_user_index",
        "aov_index",
        "revenue_share_index"
    ]].copy()

    heatmap_tbl = heatmap_tbl.set_index("category_breadth_seg")
    z = heatmap_tbl.to_numpy(dtype=float)

    fig = px.imshow(
        z,
        x=["Repeat", "Revenue/User", "AOV", "Revenue/User share"],
        y=heatmap_tbl.index.tolist(),
        aspect="auto",
        color_continuous_scale="Blues",
        text_auto=".0f"
    )
    fig.update_xaxes(title="")
    fig.update_yaxes(title="")
    fig.update_layout(
        coloraxis_colorbar=dict(
            title="Index",
        )
    )
    return _base_layout(fig, "Cumulative Category Breadth: Outcome Composition (Avg = 100)", height=420)

def build_basket_size_repeat_dot_fig(base_df: pd.DataFrame, repeat_metric: str = "repeat90"):
    plot_df = build_segment_kpi_table(base_df, "basket_size_seg", repeat_metric=repeat_metric)
    if plot_df.empty:
        return _empty_figure("No basket size segment data")

    _, _, repeat_label = REPEAT_COL_MAP[repeat_metric]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=plot_df["basket_size_seg"],
            y=plot_df["repeat_rate"],
            mode="markers+lines+text",
            marker=dict(size=11, color=BAR_PALETTE[2]),
            line=dict(color=BAR_PALETTE[0], width=2),
            text=[f"{v:.1f}%" if pd.notna(v) else "-" for v in plot_df["repeat_rate"]],
            textposition="top center",
            name=repeat_label
        )
    )
    fig.update_yaxes(title=f"{repeat_label} (%)", tickformat=".1f", rangemode="tozero")
    fig.update_xaxes(title="")
    return _base_layout(fig, "Repeat Rate by Basket Size", showlegend=False)


def build_first_order_value_repeat_dot_fig(base_df: pd.DataFrame, repeat_metric: str = "repeat90"):
    plot_df = build_segment_kpi_table(base_df, "first_order_value_seg", repeat_metric=repeat_metric)
    if plot_df.empty:
        return _empty_figure("No first order value segment data")

    _, _, repeat_label = REPEAT_COL_MAP[repeat_metric]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=plot_df["first_order_value_seg"],
            y=plot_df["repeat_rate"],
            mode="markers+lines+text",
            marker=dict(size=11, color=BAR_PALETTE[3]),
            line=dict(color=BAR_PALETTE[0], width=2),
            text=[f"{v:.1f}%" if pd.notna(v) else "-" for v in plot_df["repeat_rate"]],
            textposition="top center",
            name=repeat_label,
            customdata=plot_df[["eligible_users"]],
            hovertemplate="%{x}: %{y:.2f}%<br>Eligible customers: %{customdata[0]}<extra></extra>"
        )
    )
    fig.update_yaxes(title=f"{repeat_label} (%)", tickformat=".1f", rangemode="tozero")
    fig.update_xaxes(title="")
    return _base_layout(fig, "Repeat Rate by First Order Value", showlegend=False)
