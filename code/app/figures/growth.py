import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from data_mart.parquet_loader import load_parquet
from data_mart.analysis_contract import GROWTH_STATUSES


COUNTRY_TO_ISO3 = {
    "China": "CHN",
    "United States": "USA",
    "Brasil": "BRA",
    "South Korea": "KOR",
    "France": "FRA",
    "United Kingdom": "GBR",
    "Germany": "DEU",
    "Spain": "ESP",
    "Japan": "JPN",
    "Australia": "AUS",
    "Belgium": "BEL",
    "Poland": "POL",
    "Colombia": "COL",
    "Austria": "AUT",
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


def _filter_growth_period(df, start_year=None, start_month=None, end_year=None, end_month=None):
    d = df.copy()

    if "order_month" not in d.columns:
        return d

    start_ts = _build_period_start(start_year, start_month)
    end_ts = _build_period_end(end_year, end_month)

    if start_ts is not None:
        d = d[d["order_month"] >= start_ts]

    if end_ts is not None:
        d = d[d["order_month"] < end_ts]

    return d


def _make_period_label(start_year=None, start_month=None, end_year=None, end_month=None):
    s_y = start_year if start_year not in [None, "", "All"] else "Start"
    s_m = start_month if start_month not in [None, "", "All"] else "01"
    e_y = end_year if end_year not in [None, "", "All"] else "End"
    e_m = end_month if end_month not in [None, "", "All"] else "12"
    return f"{s_y}-{s_m} ~ {e_y}-{e_m}"


def load_growth_data() -> pd.DataFrame:
    df = load_parquet("mart_growth_kpi").copy()

    if "order_month" in df.columns:
        df["order_month"] = pd.to_datetime(df["order_month"], errors="coerce")

    return df


def load_growth_geo_inputs():
    fact_order = load_parquet("fact_order").copy()
    dim_user = load_parquet("dim_user").copy()

    if "order_month" in fact_order.columns:
        fact_order["order_month"] = pd.to_datetime(fact_order["order_month"], errors="coerce")

    if "u_id" in fact_order.columns:
        fact_order["u_id"] = pd.to_numeric(fact_order["u_id"], errors="coerce")

    if "o_id" in fact_order.columns:
        fact_order["o_id"] = pd.to_numeric(fact_order["o_id"], errors="coerce")

    if "order_revenue" in fact_order.columns:
        fact_order["order_revenue"] = pd.to_numeric(fact_order["order_revenue"], errors="coerce")

    if "u_id" in dim_user.columns:
        dim_user["u_id"] = pd.to_numeric(dim_user["u_id"], errors="coerce")

    if "country" in dim_user.columns:
        dim_user["country"] = dim_user["country"].astype("string").fillna("Unknown")

    return fact_order, dim_user


def build_kpi_summary(df: pd.DataFrame) -> dict:
    d = df.copy().sort_values("order_month")
    if d.empty:
        return {"revenue": None, "mau": None, "buyers": None, "conversion_rate": None}

    latest = d.iloc[-1]

    return {
        "revenue": latest["total_revenue"] if "total_revenue" in d.columns else None,
        "mau": latest["MAU"] if "MAU" in d.columns else None,
        "buyers": latest["buyers"] if "buyers" in d.columns else None,
        "conversion_rate": latest["conversion_rate"] if "conversion_rate" in d.columns else None,
    }


def build_revenue_area_fig(df: pd.DataFrame, period_label=None):
    d = df.copy().sort_values("order_month")

    if not {"order_month", "total_revenue"}.issubset(d.columns):
        return _empty_figure("Missing columns for revenue area")

    title = "Revenue Trend"
    if period_label:
        title += f"<br><sup>{period_label}</sup>"

    fig = px.area(
        d,
        x="order_month",
        y="total_revenue",
        title=title
    )
    fig.update_layout(margin=dict(l=20, r=20, t=70, b=20), template="plotly_white")
    fig.update_xaxes(title="Month")
    fig.update_yaxes(title="Non-cancelled Order Amount")
    return fig


def build_new_repeat_stacked_fig(df: pd.DataFrame, period_label=None):
    d = df.copy().sort_values("order_month")

    y_cols = [c for c in ["new_revenue", "repeat_revenue"] if c in d.columns]
    if not y_cols:
        return _empty_figure("Missing new/repeat revenue columns")

    title = "New vs Repeat Order Amount (non-cancelled)"
    if period_label:
        title += f"<br><sup>{period_label}</sup>"

    fig = px.bar(
        d,
        x="order_month",
        y=y_cols,
        title=title
    )
    fig.update_layout(margin=dict(l=20, r=20, t=70, b=20), template="plotly_white")
    fig.update_xaxes(title="Month")
    fig.update_yaxes(title="Non-cancelled Order Amount")
    return fig


def build_visitors_mau_fig(df: pd.DataFrame, period_label=None):
    d = df.copy().sort_values("order_month")

    if not {"order_month", "Visitors", "MAU"}.issubset(d.columns):
        return _empty_figure("Missing Visitors / MAU columns")

    title = "Sessions vs Identified MAU"
    if period_label:
        title += f"<br><sup>{period_label}</sup>"

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d["order_month"], y=d["Visitors"], mode="lines+markers", name="Visitors"))
    fig.add_trace(go.Scatter(x=d["order_month"], y=d["MAU"], mode="lines+markers", name="MAU"))

    fig.update_layout(
        title=title,
        margin=dict(l=20, r=20, t=70, b=20),
        template="plotly_white"
    )
    fig.update_xaxes(title="Month")
    fig.update_yaxes(title="Sessions / identified users")
    return fig


def build_traffic_vs_buyers_fig(df: pd.DataFrame, period_label=None):
    d = df.copy().sort_values("order_month")

    if not {"order_month", "MAU", "buyers"}.issubset(d.columns):
        return _empty_figure("Missing MAU / buyers columns")

    title = "Traffic vs Buyers Trend"
    if period_label:
        title += f"<br><sup>{period_label}</sup>"

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d["order_month"], y=d["MAU"], mode="lines+markers", name="MAU"))
    fig.add_trace(go.Scatter(x=d["order_month"], y=d["buyers"], mode="lines+markers", name="Buyers"))

    fig.update_layout(
        title=title,
        margin=dict(l=20, r=20, t=70, b=20),
        template="plotly_white"
    )
    fig.update_xaxes(title="Month")
    fig.update_yaxes(title="Sessions / identified users")
    return fig


def build_conversion_rate_fig(df: pd.DataFrame, period_label=None):
    d = df.copy().sort_values("order_month")

    if not {"order_month", "conversion_rate"}.issubset(d.columns):
        return _empty_figure("Missing conversion_rate column")

    title = "Purchase-event Share: Identification Proxy"
    if period_label:
        title += f"<br><sup>{period_label}</sup>"

    fig = px.line(
        d,
        x="order_month",
        y="conversion_rate",
        title=title
    )
    fig.update_yaxes(tickformat=".1%", title="Session Share (diagnostic)")
    fig.update_xaxes(title="Month")
    fig.update_layout(margin=dict(l=20, r=20, t=70, b=20), template="plotly_white")
    return fig


def build_aov_orders_fig(df: pd.DataFrame, period_label=None):
    d = df.copy().sort_values("order_month")

    if not {"order_month", "AOV", "orders"}.issubset(d.columns):
        return _empty_figure("Missing AOV / orders columns")

    title = "Orders and AOV"
    if period_label:
        title += f"<br><sup>{period_label}</sup>"

    fig = go.Figure()
    fig.add_trace(go.Bar(x=d["order_month"], y=d["orders"], name="Orders"))
    fig.add_trace(go.Scatter(x=d["order_month"], y=d["AOV"], mode="lines+markers", name="AOV", yaxis="y2"))

    fig.update_layout(
        title=title,
        yaxis=dict(title="Orders"),
        yaxis2=dict(title="Non-cancelled AOV", overlaying="y", side="right",rangemode="tozero"),
        margin=dict(l=20, r=20, t=70, b=20),
        template="plotly_white"
    )
    fig.update_xaxes(title="Month")
    return fig


def build_gauge_conversion_fig(df: pd.DataFrame, period_label=None):
    d = df.copy()

    if "conversion_rate" not in d.columns:
        return _empty_figure("Missing conversion_rate column")

    value = d["purchase_sessions"].sum() / d["Visitors"].sum() if d["Visitors"].sum() else float("nan")
    if pd.isna(value):
        return _empty_figure("No conversion_rate data")

    display_value = float(value) * 100

    title = "Period Purchase-event Share<br><sup>Identification proxy; not a conversion KPI</sup>"
    if period_label:
        title += f"<br><sup>{period_label}</sup>"

    fig = go.Figure(
        go.Indicator(
            mode="number",
            value=display_value,
            title={"text": title},
            number={"suffix": "%"},
        )
    )

    fig.update_layout(
        margin=dict(l=20, r=20, t=70, b=20),
        template="plotly_white",
        height=380
    )
    return fig


def build_gauge_penetration_fig(df: pd.DataFrame, period_label=None):
    d = df.copy()

    if "buyer_penetration_in_mau" not in d.columns:
        return _empty_figure("Missing buyer_penetration_in_mau column")

    value = d["buyers"].sum() / d["MAU"].sum() if d["MAU"].sum() else float("nan")
    if pd.isna(value):
        return _empty_figure("No buyer_penetration_in_mau data")

    display_value = float(value) * 100

    title = "Buyer-months / Identified User-months"
    if period_label:
        title += f"<br><sup>{period_label}</sup>"

    fig = go.Figure(
        go.Indicator(
            mode="number",
            value=display_value,
            title={"text": title},
            number={"suffix": "%"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "green"},
            }
        )
    )

    fig.update_layout(
        margin=dict(l=20, r=20, t=70, b=20),
        template="plotly_white",
        height=380
    )
    return fig

def build_country_base(fact_order, dim_user, delivered_statuses=GROWTH_STATUSES):
    fo = fact_order.copy()

    fo["o_id"] = pd.to_numeric(fo["o_id"], errors="coerce")
    fo["u_id"] = pd.to_numeric(fo["u_id"], errors="coerce")
    fo["order_revenue"] = pd.to_numeric(fo["order_revenue"], errors="coerce")
    fo["order_month"] = pd.to_datetime(fo["order_month"], errors="coerce")
    fo["order_status"] = fo["order_status"].astype("string")

    fo = fo[
        fo["order_status"].isin(delivered_statuses)
        & fo["order_revenue"].notna()
        & fo["o_id"].notna()
        & fo["u_id"].notna()
        & fo["order_month"].notna()
    ].copy()

    du = dim_user[["u_id", "country"]].copy()
    du["u_id"] = pd.to_numeric(du["u_id"], errors="coerce")
    du["country"] = du["country"].astype("string").fillna("Unknown")

    df_country = fo.merge(du, on="u_id", how="left")
    df_country["country"] = df_country["country"].fillna("Unknown")

    return df_country


def build_country_revenue_table(df_country, country_to_iso3=COUNTRY_TO_ISO3):
    country_table = (
        df_country.groupby("country", as_index=False)
        .agg(
            revenue=("order_revenue", "sum"),
            orders=("o_id", "nunique"),
            buyers=("u_id", "nunique")
        )
    )

    country_table["AOV"] = country_table["revenue"] / country_table["orders"]
    country_table["revenue_share"] = country_table["revenue"] / country_table["revenue"].sum()
    country_table["iso_alpha"] = country_table["country"].map(country_to_iso3)

    country_table = country_table.sort_values("revenue", ascending=False).reset_index(drop=True)
    return country_table


def build_geo_country_revenue_fig(fact_order, dim_user, start_year=None, start_month=None, end_year=None, end_month=None):
    fo = _filter_growth_period(
        fact_order,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )
    period_label = _make_period_label(start_year, start_month, end_year, end_month)

    df_country = build_country_base(fo, dim_user)
    country_table = build_country_revenue_table(df_country)

    d=country_table.sort_values('revenue',ascending=True)
    if d.empty:
        return _empty_figure("No country amount data")
    fig=px.bar(d,x='revenue',y='country',orientation='h',
        hover_data={'orders':True,'buyers':True,'AOV':':,.2f','revenue_share':':.1%'},
        title=f"Non-cancelled Order Amount by Country<br><sup>{period_label}</sup>")
    fig.update_layout(template='plotly_white',margin=dict(l=20,r=20,t=70,b=40),height=500)
    fig.update_xaxes(title='Non-cancelled Order Amount',rangemode='tozero')
    fig.update_yaxes(title='Country')
    return fig


def build_geo_country_table_fig(fact_order, dim_user, top_n=10, start_year=None, start_month=None, end_year=None, end_month=None):
    fo = _filter_growth_period(
        fact_order,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )
    period_label = _make_period_label(start_year, start_month, end_year, end_month)

    df_country = build_country_base(fo, dim_user)
    country_table = build_country_revenue_table(df_country)

    if top_n == "All":
        d = country_table.copy()
    else:
        d = country_table.head(int(top_n)).copy()

    if d.empty:
        return _empty_figure("No country table data")

    d["revenue"] = d["revenue"].round(0).astype(int)
    d["orders"] = d["orders"].astype(int)
    d["buyers"] = d["buyers"].astype(int)
    d["AOV"] = d["AOV"].round(2)
    d["revenue_share"] = (d["revenue_share"] * 100).round(1)

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=["Country", "Revenue", "Revenue Share (%)", "Orders", "Buyers", "AOV"],
                    fill_color="#EAF2F8",
                    align="left"
                ),
                cells=dict(
                    values=[
                        d["country"],
                        d["revenue"],
                        d["revenue_share"],
                        d["orders"],
                        d["buyers"],
                        d["AOV"]
                    ],
                    fill_color="white",
                    align="left"
                )
            )
        ]
    )

    fig.update_layout(
        title=f"Top Countries Summary<br><sup>{period_label}</sup>",
        template="plotly_white",
        margin=dict(l=20, r=20, t=70, b=20),
        height=500
    )
    return fig

def build_geo_country_trend_fig(fact_order, dim_user, selected_country="United States", start_year=None, start_month=None, end_year=None, end_month=None):
    fo = _filter_growth_period(
        fact_order,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )
    period_label = _make_period_label(start_year, start_month, end_year, end_month)

    df_country = build_country_base(fo, dim_user)

    d = df_country[df_country["country"].eq(selected_country)].copy()
    if d.empty:
        return _empty_figure(f"No data for country: {selected_country}")

    g = (
        d.groupby("order_month", as_index=False)["order_revenue"]
        .sum()
        .sort_values("order_month")
    )

    fig = px.line(
        g,
        x="order_month",
        y="order_revenue",
        markers=True,
        title=f"Revenue Trend: {selected_country}<br><sup>{period_label}</sup>"
    )

    fig.update_layout(
        template="plotly_white",
        xaxis_title="Month",
        yaxis_title="Non-cancelled Order Amount",
        margin=dict(l=20, r=20, t=70, b=20),
        height=500
    )
    return fig
