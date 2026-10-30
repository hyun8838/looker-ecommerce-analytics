import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from data_mart.parquet_loader import load_parquet


def _empty_figure(message: str):
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=16),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=20),
        height=400,
    )
    return fig


def load_product_mix_data() -> pd.DataFrame:
    df = load_parquet("mart_product_mix_base").copy()

    if "order_month" in df.columns:
        df["order_month"] = pd.to_datetime(df["order_month"], errors="coerce")

    if "item_revenue" in df.columns:
        df["item_revenue"] = pd.to_numeric(df["item_revenue"], errors="coerce")

    for col in [
        "category",
        "brand",
        "department",
        "dominant_browser",
        "dominant_traffic_source",
    ]:
        if col in df.columns:
            df[col] = df[col].astype("string").fillna("Unknown")

    df = df[
        df["order_month"].notna()
        & df["item_revenue"].notna()
        & df["category"].notna()
    ].copy()

    return df.sort_values("order_month").reset_index(drop=True)


def _build_period_start(year, month):
    if year in [None, "", "All"]:
        return None
    if month in [None, "", "All"]:
        return pd.Timestamp(int(year), 1, 1)
    return pd.Timestamp(int(year), int(month), 1)


def _build_period_end(year, month):
    if year in [None, "", "All"]:
        return None
    if month in [None, "", "All"]:
        return pd.Timestamp(int(year) + 1, 1, 1)
    return pd.Timestamp(int(year), int(month), 1) + pd.offsets.MonthBegin(1)


def _filter_product_mix_period(df: pd.DataFrame, start_year=None, start_month=None, end_year=None, end_month=None):
    d = df.copy()

    start_ts = _build_period_start(start_year, start_month)
    end_ts = _build_period_end(end_year, end_month)

    if start_ts is not None:
        d = d[d["order_month"] >= start_ts]

    if end_ts is not None:
        d = d[d["order_month"] < end_ts]

    return d


def _topn_share(df: pd.DataFrame, dim_col="category", value_col="item_revenue", top_n=10):
    g = (
        df.groupby(dim_col, as_index=False)[value_col]
        .sum()
        .sort_values(value_col, ascending=False)
    )
    total = g[value_col].sum()
    if total <= 0:
        return np.nan
    return float(g.head(top_n)[value_col].sum() / total)


def _hhi(df: pd.DataFrame, dim_col="category", value_col="item_revenue"):
    g = df.groupby(dim_col, as_index=False)[value_col].sum()
    total = g[value_col].sum()
    if total <= 0:
        return np.nan
    share = g[value_col] / total
    return float((share ** 2).sum())


def build_product_mix_kpi_summary(df: pd.DataFrame) -> dict:
    total_revenue = float(df["item_revenue"].sum()) if not df.empty else 0.0
    n_categories = int(df["category"].nunique()) if "category" in df.columns else 0
    n_departments = int(df["department"].nunique()) if "department" in df.columns else 0

    cat_rev = (
        df.groupby("category", as_index=False)["item_revenue"]
        .sum()
        .sort_values("item_revenue", ascending=False)
    )
    top_category_share = (
        float(cat_rev["item_revenue"].iloc[0] / cat_rev["item_revenue"].sum())
        if len(cat_rev) > 0 and cat_rev["item_revenue"].sum() > 0
        else np.nan
    )

    return {
        "total_revenue": total_revenue,
        "n_categories": n_categories,
        "n_departments": n_departments,
        "top_category_share": top_category_share,
    }


def build_category_share_pie_fig(
    df: pd.DataFrame,
    top_n=10,
    start_year=None,
    start_month=None,
    end_year=None,
    end_month=None,
):
    d = _filter_product_mix_period(
        df,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )

    g = (
        d.groupby("category", as_index=False)["item_revenue"]
        .sum()
        .sort_values("item_revenue", ascending=False)
    )

    if g.empty:
        return _empty_figure("No category data")

    g["revenue_share"] = g["item_revenue"] / g["item_revenue"].sum() * 100

    if top_n == "All":
        pie_data = g.copy()
        top_n_label = "All"
    else:
        top_n = int(top_n)
        top_n_label = f"Top {top_n} + Others"

        top_part = g.head(top_n).copy()
        other_share = g["revenue_share"].iloc[top_n:].sum()

        if other_share > 0:
            others = pd.DataFrame({
                "category": ["Others"],
                "item_revenue": [g["item_revenue"].iloc[top_n:].sum()],
                "revenue_share": [other_share],
            })
            pie_data = pd.concat([top_part, others], ignore_index=True)
        else:
            pie_data = top_part

    period_label = f"{start_year}-{start_month} ~ {end_year}-{end_month}"

    fig = px.pie(
        pie_data,
        values="revenue_share",
        names="category",
        title=f"Category Revenue Share ({top_n_label})<br><sup>{period_label}</sup>",
    )

    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=20, r=20, t=70, b=20),
        height=420
    )
    return fig


def build_department_share_fig(df: pd.DataFrame):
    g = (
        df.groupby("department", as_index=False)["item_revenue"]
        .sum()
        .sort_values("item_revenue", ascending=False)
    )

    if g.empty:
        return _empty_figure("No department data")

    fig = px.bar(
        g,
        x="department",
        y="item_revenue",
        title="Department Item Revenue"
    )
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=60, b=20), height=420)
    return fig


def build_pareto_fig(df: pd.DataFrame, top_k=50, threshold=0.8):
    g = (
        df.groupby("category", as_index=False)["item_revenue"]
        .sum()
        .rename(columns={"item_revenue": "revenue"})
        .sort_values("revenue", ascending=False)
        .head(top_k)
        .copy()
    )

    if g.empty:
        return _empty_figure("No pareto data")

    total = df["item_revenue"].sum()
    g["cum_share"] = np.where(total > 0, g["revenue"].cumsum() / total, np.nan)
    g["rank"] = np.arange(1, len(g) + 1)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=g["rank"],
            y=g["cum_share"],
            mode="lines+markers",
            name="Cumulative Share"
        )
    )
    fig.add_hline(y=threshold, line_dash="dash")

    cross_idx = np.argmax(g["cum_share"].values >= threshold)
    if len(g) > 0 and g["cum_share"].iloc[cross_idx] >= threshold:
        cross_x = int(cross_idx + 1)
        cross_y = float(g["cum_share"].iloc[cross_idx])
        fig.add_vline(x=cross_x, line_dash="dash")
        fig.add_annotation(x=cross_x, y=cross_y, text=f"Top {cross_x}", showarrow=True)

    fig.update_layout(
        template="plotly_white",
        title=f"Pareto Curve (Top {top_k} Categories)",
        xaxis_title="Top category rank",
        yaxis_title="Cumulative revenue share",
        yaxis_tickformat=".0%",
        margin=dict(l=20, r=20, t=60, b=20),
        height=400,
    )
    return fig


def build_hhi_trend_fig(df: pd.DataFrame):
    rows = []
    for m, sub in df.groupby("order_month"):
        rows.append((m, _hhi(sub, dim_col="category", value_col="item_revenue")))

    trend = pd.DataFrame(rows, columns=["order_month", "hhi"]).sort_values("order_month")

    if trend.empty:
        return _empty_figure("No HHI trend data")

    fig = px.line(
        trend,
        x="order_month",
        y="hhi",
        markers=True,
        title="HHI Trend (Item Category Concentration)"
    )
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=60, b=20), height=400)
    return fig


def build_topn_share_trend_fig(df: pd.DataFrame, top_n=10):
    rows = []
    for m, sub in df.groupby("order_month"):
        rows.append((m, _topn_share(sub, dim_col="category", value_col="item_revenue", top_n=top_n)))

    trend = pd.DataFrame(rows, columns=["order_month", "topn_share"]).sort_values("order_month")

    if trend.empty:
        return _empty_figure("No Top N share trend data")

    fig = px.line(
        trend,
        x="order_month",
        y="topn_share",
        markers=True,
        title=f"Top {top_n} Share Trend (Item Category)"
    )
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=60, b=20), height=400)
    return fig


def build_category_revenue_trend_fig(df: pd.DataFrame, category: str, start_year=None, start_month=None, end_year=None, end_month=None):
    d = _filter_product_mix_period(df, start_year=start_year, start_month=start_month, end_year=end_year, end_month=end_month)

    if category not in [None, "", "All"]:
        d = d[d["category"] == category].copy()

    if d.empty:
        label = "All Categories" if category in [None, "", "All"] else category
        return _empty_figure(f"No data for category: {label}")

    g = (
        d.groupby("order_month", as_index=False)["item_revenue"]
        .sum()
        .sort_values("order_month")
    )

    title = "Category Revenue Trend: All Categories" if category in [None, "", "All"] else f"Category Revenue Trend: {category}"

    fig = px.line(
        g,
        x="order_month",
        y="item_revenue",
        markers=True,
        title=title
    )
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=60, b=20), height=420)
    return fig


def build_brand_share_within_category_fig(df: pd.DataFrame, category: str, start_year=None, start_month=None, end_year=None, end_month=None, top_n=10):
    d = _filter_product_mix_period(df, start_year=start_year, start_month=start_month, end_year=end_year, end_month=end_month)

    if category not in [None, "", "All"]:
        d = d[d["category"] == category].copy()

    if d.empty:
        label = "All Categories" if category in [None, "", "All"] else category
        return _empty_figure(f"No brand data for category: {label}")

    g = (
        d.groupby("brand", as_index=False)["item_revenue"]
        .sum()
        .rename(columns={"item_revenue": "revenue"})
        .sort_values("revenue", ascending=False)
    )

    total = g["revenue"].sum()
    g["share"] = np.where(total > 0, g["revenue"] / total, np.nan)
    g_top = g.head(top_n).copy().sort_values("share", ascending=True)

    title = "Top 10 Brand Share | All Categories" if category in [None, "", "All"] else f"Top 10 Brand Share in Category: {category}"

    fig = px.bar(
        g_top,
        x="share",
        y="brand",
        orientation="h",
        title=title
    )
    fig.update_xaxes(tickformat=".0%")
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=60, b=20), height=420)
    return fig


def build_dept_category_heatmap_fig(df: pd.DataFrame, top_n_x=12, top_n_y=12, ratio_mode="col"):
    d = df.copy()

    top_x = (
        d.groupby("department")["item_revenue"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n_x)
        .index
    )
    top_y = (
        d.groupby("category")["item_revenue"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n_y)
        .index
    )



    mat = d.pivot_table(
        index="category",
        columns="department",
        values="item_revenue",
        aggfunc="sum",
        fill_value=0
    ).astype(float)

    if ratio_mode == "all":
        denom = mat.to_numpy().sum()
        ratio = (mat / denom * 100) if denom > 0 else mat * np.nan
    elif ratio_mode == "row":
        denom = mat.sum(axis=1).replace(0, np.nan)
        ratio = mat.div(denom, axis=0) * 100
    else:
        denom = mat.sum(axis=0).replace(0, np.nan)
        ratio = mat.div(denom, axis=1) * 100

    ratio = ratio.reindex(index=top_y, columns=top_x)
    fig = px.imshow(
        ratio,
        text_auto=".1f",
        aspect="auto",
        title="Department × Category Heatmap (Revenue Ratio %)"
    )
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=60, b=20), height=550)
    return fig


def build_brand_category_heatmap_fig(df: pd.DataFrame, department="All", top_n_x=12, top_n_y=12, ratio_mode="col"):
    d = df.copy()

    if department not in [None, "", "All"]:
        d = d[d["department"] == department].copy()

    if d.empty:
        return _empty_figure("No data for selected department")

    top_x = (
        d.groupby("brand")["item_revenue"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n_x)
        .index
    )
    top_y = (
        d.groupby("category")["item_revenue"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n_y)
        .index
    )



    mat = d.pivot_table(
        index="category",
        columns="brand",
        values="item_revenue",
        aggfunc="sum",
        fill_value=0
    ).astype(float)

    if ratio_mode == "all":
        denom = mat.to_numpy().sum()
        ratio = (mat / denom * 100) if denom > 0 else mat * np.nan
    elif ratio_mode == "row":
        denom = mat.sum(axis=1).replace(0, np.nan)
        ratio = mat.div(denom, axis=0) * 100
    else:
        denom = mat.sum(axis=0).replace(0, np.nan)
        ratio = mat.div(denom, axis=1) * 100

    title = "Brand × Category Heatmap (Revenue Ratio %)"
    if department not in [None, "", "All"]:
        title += f" | Department: {department}"

    ratio = ratio.reindex(index=top_y, columns=top_x)
    fig = px.imshow(
        ratio,
        text_auto=".1f",
        aspect="auto",
        title=title
    )
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=60, b=20), height=550)
    return fig

def build_department_mix_trend_fig(df: pd.DataFrame):

    g = (
        df.groupby(["order_month", "department"], as_index=False)["item_revenue"]
        .sum()
        .sort_values("order_month")
    )

    if g.empty:
        return _empty_figure("No department mix data")

    fig = px.area(
        g,
        x="order_month",
        y="item_revenue",
        color="department",
        title="Monthly Revenue Mix by Department",
    )

    fig.update_layout(
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=20),
        height=420,
        legend_title="Department"
    )

    return fig