"""Export BigQuery marts and aggregate fixed first-order customer groups locally."""
import os
from pathlib import Path
import sys

import pandas as pd
import pandas_gbq

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from data_mart.customer_segments import assign_segments, fit_definition

PROJECT = os.environ.get("BQ_PROJECT", "thelooker-ecommerce")
DATASET = os.environ.get("BQ_DATASET", "data_mart")
SAVE_DIR = Path(__file__).resolve().parents[1] / "app" / "data" / "parquet"
CORE_MARTS = ["df_oi", "df_e", "fact_order", "dim_user"]
PAGE_MARTS = [
    "mart_growth_kpi",
    "mart_funnel_session",
    "mart_funnel_transition",
    "mart_retention_cohort",
    "mart_retention_user",
    "mart_product_mix_base",
    "mart_behavior_user_base",
    "mart_behavior_segment",
]
ALL_TABLES = CORE_MARTS + PAGE_MARTS


def normalize_bq_dtypes(df):
    d = df.copy()
    for col in d.columns:
        dtype = str(d[col].dtype).lower()
        if "dbdate" in dtype or "dbtimestamp" in dtype or "datetime" in dtype:
            d[col] = pd.to_datetime(d[col], errors="coerce")
        elif "dbtime" in dtype:
            d[col] = d[col].astype("string")
    return d


def load_table(table_name):
    query = f"SELECT * FROM `{PROJECT}.{DATASET}.{table_name}`"
    df = pandas_gbq.read_gbq(query, project_id=PROJECT, dialect="standard")
    print(f"[LOAD] {table_name:<30} shape={df.shape}")
    return df


def save_parquet(df, table_name):
    path = SAVE_DIR / f"{table_name}.parquet"
    normalize_bq_dtypes(df).to_parquet(path, engine="pyarrow", index=False)
    print(f"[SAVE] {table_name:<30} → {path.name}")


def build_segments(reference, definition=None):
    """Use all observed buyers to fix the amount boundaries before aggregation."""
    definition = fit_definition(reference) if definition is None else definition
    d = assign_segments(reference.loc[reference.has_order.eq(1)], definition)
    g = d.groupby("customer_value_seg", observed=True).agg(
        users=("u_id", "nunique"),
        total_revenue=("total_revenue_delivered", "sum"),
        orders=("total_orders_delivered", "sum"),
    )
    eligible = d.loc[d.eligible_90.fillna(False)]
    rep = eligible.groupby("customer_value_seg", observed=True).agg(
        eligible_users=("u_id", "nunique"), repeat_users=("repeat_90", "sum")
    )
    g = g.join(rep)
    g["revenue_per_user"] = g.total_revenue / g.users
    g["aov"] = g.total_revenue / g.orders
    g["repeat90"] = 100 * g.repeat_users / g.eligible_users
    g["revenue_share"] = 100 * g.total_revenue / g.total_revenue.sum()
    g = g.reset_index()
    g["first_order_value_seg"] = g.customer_value_seg
    return g


def main():
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    for table in ALL_TABLES:
        if table == "mart_behavior_segment":
            # The full customer reference supplies both the export and group boundaries.
            df = build_segments(reference)
        else:
            df = load_table(table)
            if table == "mart_behavior_user_base":
                reference = df
        save_parquet(df, table)
    print("전체 Parquet export 완료")


if __name__ == "__main__":
    main()
