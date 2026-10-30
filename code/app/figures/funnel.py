import ast
from collections import Counter

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


def _make_period_label(start_year=None, start_month=None, end_year=None, end_month=None):
    s_y = start_year if start_year not in [None, "", "All"] else "Start"
    s_m = start_month if start_month not in [None, "", "All"] else "01"
    e_y = end_year if end_year not in [None, "", "All"] else "End"
    e_m = end_month if end_month not in [None, "", "All"] else "12"
    return f"{s_y}-{s_m} ~ {e_y}-{e_m}"


def _parse_event_array(value):
    if value is None:
        return []

    if isinstance(value, list):
        return [str(v).strip().lower() for v in value]

    if isinstance(value, (tuple, set)):
        return [str(v).strip().lower() for v in value]

    if hasattr(value, "tolist") and not isinstance(value, str):
        try:
            value = value.tolist()
            if isinstance(value, list):
                return [str(v).strip().lower() for v in value]
        except Exception:
            pass

    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return []

        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, list):
                return [str(v).strip().lower() for v in parsed]
        except Exception:
            pass

        text = text.replace("→", ",")
        return [v.strip().lower() for v in text.split(",") if v.strip()]

    return []


def load_funnel_session_data() -> pd.DataFrame:
    df = load_parquet("mart_funnel_session").copy()

    if "e_created_at" in df.columns:
        df["e_created_at"] = pd.to_datetime(df["e_created_at"], errors="coerce")

    if "month" in df.columns:
        df["month"] = pd.to_datetime(df["month"], errors="coerce")

    if "session_event_array" in df.columns:
        df["session_event_array_parsed"] = df["session_event_array"].apply(_parse_event_array)

    if "is_member" in df.columns:
        df["is_member"] = pd.to_numeric(df["is_member"], errors="coerce").fillna(0).astype(int)

    if "has_purchase" in df.columns:
        df["has_purchase"] = pd.to_numeric(df["has_purchase"], errors="coerce").fillna(0).astype(int)

    if "has_cancel" in df.columns:
        df["has_cancel"] = pd.to_numeric(df["has_cancel"], errors="coerce").fillna(0).astype(int)

    if "cart_count" in df.columns:
        df["cart_count"] = pd.to_numeric(df["cart_count"], errors="coerce").fillna(0).astype(int)

    if "cart_bucket" in df.columns:
        df["cart_bucket"] = df["cart_bucket"].astype(str)

    if "entry_event" in df.columns:
        df["entry_event"] = df["entry_event"].astype(str).str.lower()

    if "e_traffic_source" in df.columns:
        df["e_traffic_source"] = df["e_traffic_source"].astype(str)

    return df


def load_funnel_transition_data() -> pd.DataFrame:
    return load_parquet("mart_funnel_transition").copy()


def filter_funnel_session_data(
    df: pd.DataFrame,
    start_year=None,
    start_month=None,
    end_year=None,
    end_month=None,
    session_type="All",
    entry_event="All",
):
    d = df.copy()

    if "month" in d.columns:
        start_ts = _build_period_start(start_year, start_month)
        end_ts = _build_period_end(end_year, end_month)

        if start_ts is not None:
            d = d[d["month"] >= start_ts]
        if end_ts is not None:
            d = d[d["month"] < end_ts]

    if session_type in ("Member", "Identified"):
        d = d[d["is_member"] == 1]
    elif session_type in ("Guest", "Unidentified"):
        d = d[d["is_member"] == 0]

    if entry_event not in [None, "", "All"]:
        d = d[d["entry_event"] == str(entry_event).lower()]

    return d


def build_transition_table_from_session_df(df: pd.DataFrame):
    transitions = []
    for seq in df.get("session_event_array_parsed", []):
        if isinstance(seq, list) and len(seq) >= 2:
            for i in range(len(seq) - 1):
                transitions.append((seq[i], seq[i + 1]))

    if not transitions:
        return pd.DataFrame(columns=["source", "target", "value"])

    transition_counts = Counter(transitions)
    trans_df = pd.DataFrame(
        [(k[0], k[1], v) for k, v in transition_counts.items()],
        columns=["source", "target", "value"]
    ).sort_values("value", ascending=False)

    return trans_df


def build_entry_event_by_session_type_fig(df: pd.DataFrame, period_label=None):
    required = {"entry_event", "is_member", "session_id"}
    if not required.issubset(df.columns):
        return _empty_figure(f"Missing columns: {required - set(df.columns)}")

    plot_df = (
        df.groupby(["entry_event", "is_member"], as_index=False)["session_id"]
        .nunique()
        .rename(columns={"session_id": "sessions"})
    )
    plot_df["member_type"] = plot_df["is_member"].map({0: "Unidentified", 1: "Identified"})

    title = "Entry Event by Session Type"
    if period_label:
        title += f"<br><sup>{period_label}</sup>"

    fig = px.bar(
        plot_df,
        x="entry_event",
        y="sessions",
        color="member_type",
        barmode="stack",
        title=title
    )
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=70, b=20), height=420)
    fig.update_xaxes(title="Entry Event")
    fig.update_yaxes(title="Sessions")
    return fig


def build_top_session_paths_components(df: pd.DataFrame, top_n: int = 10):
    required = {"sequence"}
    if not required.issubset(df.columns):
        return _empty_figure("Missing sequence column"), _empty_figure("Missing sequence column")

    plot_df = (
        df["sequence"]
        .value_counts()
        .head(top_n)
        .reset_index()
    )
    plot_df.columns = ["sequence", "sessions"]

    if plot_df.empty:
        return _empty_figure("No session path data"), _empty_figure("No session path data")

    total = df["session_id"].nunique()
    plot_df["share"] = plot_df["sessions"] / total
    plot_df["path_id"] = [f"P{i}" for i in range(1, len(plot_df) + 1)]

    bar_df = plot_df.copy()
    bar_df["path_id"] = pd.Categorical(
        bar_df["path_id"],
        categories=plot_df["path_id"].tolist(),
        ordered=True
    )

    fig_bar = px.bar(
        bar_df,
        x="sessions",
        y="path_id",
        orientation="h",
        color="path_id",
        title=f"Top {top_n} Session Paths"
    )

    fig_bar.update_yaxes(
        categoryorder="array",
        categoryarray=plot_df["path_id"].tolist()[::-1]
    )
    
    fig_bar.update_layout(
        template="plotly_white",
        showlegend=False,
        margin=dict(l=20, r=20, t=70, b=20),
        height=460
    )
    fig_bar.update_xaxes(title="Sessions")
    fig_bar.update_yaxes(title="Path ID")

    table_df = plot_df[["path_id", "sequence", "sessions", "share"]].copy()
    table_df["share"] = (table_df["share"] * 100).round(1)

    fig_table = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=["Path ID", "Session Path", "Sessions", "Share (%)"],
                    fill_color="#EAF2F8",
                    align="left"
                ),
                cells=dict(
                    values=[
                        table_df["path_id"],
                        table_df["sequence"],
                        table_df["sessions"],
                        table_df["share"],
                    ],
                    fill_color="white",
                    align="left"
                )
            )
        ]
    )
    fig_table.update_layout(
        title="Top Session Paths Summary",
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=20),
        height=460
    )

    return fig_bar, fig_table


def build_transition_matrix_fig(df: pd.DataFrame, period_label=None):
    required = {"session_event_array_parsed"}
    if not required.issubset(df.columns):
        return _empty_figure(f"Missing columns: {required - set(df.columns)}")

    transitions = []
    for seq in df["session_event_array_parsed"]:
        if isinstance(seq, list) and len(seq) >= 2:
            for i in range(len(seq) - 1):
                transitions.append((seq[i], seq[i + 1]))

    if not transitions:
        return _empty_figure("No transition matrix data")

    transition_counts = Counter(transitions)
    trans_df = pd.DataFrame(
        [(k[0], k[1], v) for k, v in transition_counts.items()],
        columns=["from_event", "to_event", "count"]
    )

    pivot = trans_df.pivot(index="from_event", columns="to_event", values="count").fillna(0)
    pivot_ratio = pivot.div(pivot.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)

    title = "Next-event Distribution (excludes session ends)"
    if period_label:
        title += f"<br><sup>{period_label}</sup>"

    fig = px.imshow(
        pivot_ratio,
        text_auto=".2f",
        aspect="auto",
        title=title,
        color_continuous_scale=[
            [0.0, "#ffffff"],
            [0.2, "#fdeaea"],
            [0.4, "#f8c9c9"],
            [0.6, "#ee8f8f"],
            [0.8, "#dc4c4c"],
            [1.0, "#b91c1c"],
        ],
    )

    fig.update_layout(
    template="plotly_white",
    margin=dict(l=20, r=20, t=70, b=20),
    height=460,
    coloraxis_colorbar=dict(title="Prob.")
    )

    return fig


def build_cart_bucket_fig(df: pd.DataFrame, period_label=None):
    required = {"cart_bucket", "session_id", "is_member"}
    if not required.issubset(df.columns):
        return _empty_figure(f"Missing columns: {required - set(df.columns)}")

    plot_df = (
        df.groupby(["cart_bucket", "is_member"], as_index=False)["session_id"]
        .nunique()
        .rename(columns={"session_id": "sessions"})
    )
    plot_df["member_type"] = plot_df["is_member"].map({0: "Unidentified", 1: "Identified"})
    plot_df["cart_bucket"] = plot_df["cart_bucket"].astype(str)

    title = "Cart Count Bucket by Identification"
    if period_label:
        title += f"<br><sup>{period_label}</sup>"

    fig = px.bar(
        plot_df,
        x="cart_bucket",
        y="sessions",
        color="member_type",
        barmode="group",
        title=title
    )
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=70, b=20), height=420)
    fig.update_xaxes(title="Cart Count Bucket")
    fig.update_yaxes(title="Sessions")
    return fig


def build_cart_count_by_source_fig(df: pd.DataFrame, period_label=None):
    required = {"cart_count", "e_traffic_source"}
    if not required.issubset(df.columns):
        return _empty_figure(f"Missing columns: {required - set(df.columns)}")

    d = df.copy()
    d["cart_count_capped"] = d["cart_count"].apply(lambda x: "5+" if x >= 5 else str(x))

    plot_df = (
        d.groupby(["cart_count_capped", "e_traffic_source"], as_index=False)
        .size()
        .rename(columns={"size": "sessions"})
    )

    title = "Cart Count by Traffic Source"
    if period_label:
        title += f"<br><sup>{period_label}</sup>"

    fig = px.bar(
        plot_df,
        x="cart_count_capped",
        y="sessions",
        color="e_traffic_source",
        barmode="group",
        title=title
    )
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=70, b=20), height=420)
    fig.update_xaxes(title="Cart Count")
    fig.update_yaxes(title="Sessions")
    return fig


def build_cancel_rate_by_entry_event_fig(df: pd.DataFrame, period_label=None):
    required = {"entry_event", "has_cancel", "session_id"}
    if not required.issubset(df.columns):
        return _empty_figure(f"Missing columns: {required - set(df.columns)}")

    plot_df = (
        df.groupby("entry_event", as_index=False)
        .agg(
            sessions=("session_id", "nunique"),
            cancel=("has_cancel", "sum")
        )
    )
    plot_df["cancel_rate"] = plot_df["cancel"] / plot_df["sessions"]

    title = "Cancel Event Session Rate by Entry Event"
    if period_label:
        title += f"<br><sup>{period_label}</sup>"

    fig = px.bar(
        plot_df,
        x="entry_event",
        y="cancel_rate",
        title=title
    )
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=70, b=20), height=420)
    fig.update_xaxes(title="Entry Event")
    fig.update_yaxes(title="Cancel Rate", tickformat=".1%")
    return fig


def build_member_guest_purchase_fig(df: pd.DataFrame, period_label=None):
    required = {"is_member", "has_purchase", "session_id"}
    if not required.issubset(df.columns):
        return _empty_figure(f"Missing columns: {required - set(df.columns)}")

    plot_df = (
        df.groupby(["is_member", "has_purchase"], as_index=False)["session_id"]
        .nunique()
        .rename(columns={"session_id": "sessions"})
    )

    plot_df["member_type"] = plot_df["is_member"].map({0: "Unidentified", 1: "Identified"})
    plot_df["purchase_flag"] = plot_df["has_purchase"].map({0: "No Purchase", 1: "Purchase"})

    title = "Purchase Event Presence by Identification"
    if period_label:
        title += f"<br><sup>{period_label}</sup>"

    fig = px.bar(
        plot_df,
        x="member_type",
        y="sessions",
        color="purchase_flag",
        barmode="group",
        title=title
    )
    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=70, b=20), height=420)
    fig.update_xaxes(title="Session Type")
    fig.update_yaxes(title="Sessions")
    return fig


def build_sankey_fig(df: pd.DataFrame, period_label=None, top_n_links=10):
    required_cols = {"source", "target", "value"}
    if not required_cols.issubset(df.columns):
        return _empty_figure("transition table missing")

    d = df.copy().sort_values("value", ascending=False).head(top_n_links)

    if d.empty:
        return _empty_figure("No Sankey data")

    labels = pd.concat([d["source"], d["target"]]).unique().tolist()
    label_map = {v: i for i, v in enumerate(labels)}

    title = "Adjacent Event Transitions Sankey"
    if period_label:
        title += f"<br><sup>{period_label}</sup>"

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                label=labels,
                pad=22,
                thickness=18,
                line=dict(color="rgba(80,80,80,0.5)", width=0.6),
            ),
            link=dict(
                source=d["source"].map(label_map),
                target=d["target"].map(label_map),
                value=d["value"],
                color="rgba(150,150,150,0.45)"
            )
        )
    )

    fig.update_layout(
        template="plotly_white",
        title=title,
        height=500,
        margin=dict(l=40, r=40, t=80, b=30)
    )
    return fig


def _has_ordered_steps(events, steps):
    it = iter(events)
    return all(any(event == step for event in it) for step in steps)


def build_funnel_cone_fig(df: pd.DataFrame, period_label=None):
    if "session_id" not in df.columns or "session_event_array_parsed" not in df.columns:
        return _empty_figure("session funnel data missing")

    product_sessions = df["session_event_array_parsed"].apply(lambda x: "product" in x).sum()
    cart_sessions = df["session_event_array_parsed"].apply(lambda x: _has_ordered_steps(x, ["product", "cart"])).sum()
    purchase_sessions = df["session_event_array_parsed"].apply(lambda x: _has_ordered_steps(x, ["product", "cart", "purchase"])).sum()

    title = "Ordered Product → Cart → Purchase Event Funnel"
    if period_label:
        title += f"<br><sup>{period_label}</sup>"

    fig = go.Figure(
        go.Funnel(
            y=["Product View", "Cart", "Purchase"],
            x=[product_sessions, cart_sessions, purchase_sessions],
            textinfo="value+percent previous+percent initial"
        )
    )

    fig.update_layout(
        template="plotly_white",
        title=title,
        height=420,
        margin=dict(l=20, r=20, t=70, b=20)
    )
    return fig