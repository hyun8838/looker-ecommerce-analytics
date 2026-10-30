"""One frozen first-Complete-order amount definition for all customer comparisons."""
from functools import lru_cache
import numpy as np
import pandas as pd
from data_mart.analysis_contract import OBSERVATION_END

LABELS = ["Low", "Mid", "High"]


def fit_definition(reference):
    buyers = reference.loc[reference.has_order.eq(1)].copy()
    if buyers.u_id.duplicated().any():
        raise ValueError("Duplicate customer IDs in segmentation reference")
    dates = pd.to_datetime(buyers.first_order_date, utc=True)
    if dates.isna().any() or (dates > OBSERVATION_END).any():
        raise ValueError("Reference must contain observed first Complete buyers only")
    amounts = pd.to_numeric(buyers.first_order_revenue, errors="coerce")
    if amounts.isna().any() or not np.isfinite(amounts).all():
        raise ValueError("Missing/non-finite first order amounts in reference")
    edges = amounts.quantile([1/3, 2/3]).tolist()
    if len(set(edges)) != 2:
        raise ValueError("Three distinct amount groups cannot be identified")
    return {"basis": "first_complete_order_amount", "reference_buyers": len(buyers),
            "observation_end_utc": str(OBSERVATION_END), "labels": LABELS,
            "cutpoints": edges, "boundary_rule": "Low <= c1; c1 < Mid <= c2; High > c2",
            "reference_min": float(amounts.min()), "reference_max": float(amounts.max()),
            "scope": "All Complete buyers in frozen snapshot; never refit after a UI filter",
            "ties": "Equal amounts stay together; group counts need not be equal"}


@lru_cache(maxsize=1)
def load_definition():
    """Fit once on the full local snapshot, before applying any UI filters."""
    from data_mart.parquet_loader import load_parquet

    return fit_definition(load_parquet("mart_behavior_user_base"))


def assign_segments(df, definition=None):
    definition = load_definition() if definition is None else definition
    if definition["basis"] != "first_complete_order_amount":
        raise ValueError("Unexpected segment definition")
    d = df.copy()
    amounts = pd.to_numeric(d.first_order_revenue, errors="coerce")
    if "has_order" in d:
        amounts = amounts.where(d.has_order.eq(1))
    amounts = amounts.where(np.isfinite(amounts))
    c1, c2 = definition["cutpoints"]
    d["first_order_value_seg"] = pd.cut(amounts, [-np.inf,c1,c2,np.inf], labels=LABELS, right=True)
    # Both views use the same first Complete order amount groups.
    d["customer_value_seg"] = d["first_order_value_seg"]
    return d
