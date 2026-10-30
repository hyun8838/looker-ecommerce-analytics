"""* 목적: README 적용 아이디어의 추가 분석 표를 Parquet 마트에서 재생성
* 실행: python analyze_ideas.py [--parquet-dir 경로] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
* 기본 기간: 대시보드와 동일한 default_period() 기준
* 결과: 같은 폴더의 tables/*.csv 저장
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent / "app"))
from data_mart.analysis_contract import GROWTH_STATUSES, OBSERVATION_END, PURCHASE_STATUS, default_period  # noqa: E402

OUT_DIR = BASE_DIR / "tables"


# =========================================================
# 1. 성장: 연도별 첫 주문·반복 주문 건수와 금액
# =========================================================
def growth_order_type(parquet_dir, start, end):
    f = pd.read_parquet(parquet_dir / "fact_order.parquet", columns=["o_id", "u_id", "order_date", "order_status", "order_revenue"])
    f["order_date"] = pd.to_datetime(f["order_date"], utc=True)
    f = f[f["order_status"].isin(GROWTH_STATUSES) & f["order_date"].le(OBSERVATION_END)].copy()

    # 대시보드 성장 마트(02_growth.sql)와 같은 기준:
    # Cancelled를 뺀 주문 안에서 고객별 순번을 다시 매겨 1번만 첫 주문으로 본다.
    f = f.sort_values(["u_id", "order_date", "o_id"])
    f["order_type"] = (f.groupby("u_id").cumcount() == 0).map({True: "first", False: "repeat"})

    d = f[f["order_date"].ge(start) & f["order_date"].lt(end)].copy()
    d["year"] = d["order_date"].dt.year
    t = d.pivot_table(index="year", columns="order_type", values="o_id", aggfunc="count").reset_index()
    amt = d.pivot_table(index="year", columns="order_type", values="order_revenue", aggfunc="sum").reset_index(drop=True)
    t["orders"] = t["first"] + t["repeat"]
    t["repeat_share_pct"] = t["repeat"] / t["orders"] * 100
    # 금액 기준 비중(대시보드 New vs Repeat Order Amount)과 건수 기준 비중 비교
    t["repeat_amount_share_pct"] = amt["repeat"] / (amt["first"] + amt["repeat"]) * 100
    t["first_amount_per_order"] = amt["first"] / t["first"]
    t["repeat_amount_per_order"] = amt["repeat"] / t["repeat"]
    return t[["year", "orders", "first", "repeat", "repeat_share_pct",
              "repeat_amount_share_pct", "first_amount_per_order", "repeat_amount_per_order"]]


# =========================================================
# 2. 퍼널: 구매 경로 유형과 세션 내 ID 유지 여부
# =========================================================
def funnel_paths(parquet_dir, start, end):
    m = pd.read_parquet(parquet_dir / "mart_funnel_session.parquet", columns=["session_id", "e_created_at", "has_purchase", "sequence"])
    m["e_created_at"] = pd.to_datetime(m["e_created_at"], utc=True)
    p = m[m["e_created_at"].ge(start) & m["e_created_at"].lt(end) & m["has_purchase"].eq(1)]

    loop = "department → product → cart"
    home = "home → department → product → cart → purchase"
    repeated = {" → ".join([loop] * n + ["purchase"]) for n in (2, 3, 4)}
    path_type = p["sequence"].map(lambda s: "home_once" if s == home else ("repeat_loop_2_4" if s in repeated else "other"))
    t = path_type.value_counts().rename_axis("path_type").reset_index(name="sessions")
    t["purchase_session_share_pct"] = t["sessions"] / len(p) * 100
    return t


def session_identity(parquet_dir, start, end):
    e = pd.read_parquet(parquet_dir / "df_e.parquet", columns=["session_id", "u_id", "e_created_at"])
    e["e_created_at"] = pd.to_datetime(e["e_created_at"], utc=True)
    e = e[e["session_id"].notna() & e["e_created_at"].le(OBSERVATION_END)]

    g = e.groupby("session_id").agg(first_at=("e_created_at", "min"), events=("e_created_at", "size"),
                                    id_events=("u_id", "count"), ids=("u_id", "nunique"))
    g = g[g["first_at"].ge(start) & g["first_at"].lt(end)]
    shape = pd.Series("mixed", index=g.index)
    shape[g["id_events"].eq(0)] = "id_missing_all_events"
    shape[g["id_events"].eq(g["events"]) & g["ids"].eq(1)] = "same_id_all_events"
    return shape.value_counts().rename_axis("session_id_shape").reset_index(name="sessions")


def event_order_link(parquet_dir):
    # purchase 이벤트를 주문과 이을 열(주문 ID)이 이벤트 원본에 있는지 확인한다.
    cols = pq.read_schema(parquet_dir / "df_e.parquet").names
    linked = [c for c in cols if "order" in c.lower() or c.lower() == "o_id"]
    return pd.DataFrame([{"event_columns": " ".join(cols), "order_id_columns": " ".join(linked) or "none"}])


# =========================================================
# 3. 상품: 아우터 브랜드의 판매액과 판매 건수
# =========================================================
def outerwear_brands(parquet_dir, start, end, category="Outerwear & Coats", brands=("The North Face", "Carhartt")):
    m = pd.read_parquet(parquet_dir / "mart_product_mix_base.parquet",
                        columns=["oi_id", "order_date", "item_revenue", "category", "brand", "order_status"])
    m["order_date"] = pd.to_datetime(m["order_date"], utc=True)
    c = m[m["order_status"].eq(PURCHASE_STATUS) & m["order_date"].ge(start) & m["order_date"].lt(end)
          & m["order_date"].le(OBSERVATION_END) & m["category"].eq(category)]

    t = c.groupby("brand").agg(sales=("item_revenue", "sum"), items=("oi_id", "size"), mean_sale_price=("item_revenue", "mean"))
    t["sales_share_pct"] = t["sales"] / c["item_revenue"].sum() * 100
    t["item_share_pct"] = t["items"] / len(c) * 100
    t = t.loc[list(brands)].reset_index()

    # The North Face는 판매가 구성까지 본다: 가장 많이 반복된 판매가와 그 판매액 비중
    tnf = c[c["brand"].eq("The North Face")]
    top_price = tnf["item_revenue"].round(2).value_counts().idxmax()
    top = tnf[tnf["item_revenue"].round(2).eq(top_price)]
    price = pd.DataFrame([{"brand": "The North Face", "sale_price": top_price, "items": len(top),
                           "sales_share_pct": top["item_revenue"].sum() / tnf["item_revenue"].sum() * 100}])
    return t[["brand", "sales_share_pct", "items", "item_share_pct", "mean_sale_price"]], price


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet-dir", default=str(BASE_DIR.parent / "app" / "data" / "parquet"))
    start_year, end_year = default_period()
    parser.add_argument("--start", default=f"{start_year}-01-01")
    parser.add_argument("--end", default=f"{end_year + 1}-01-01", help="이 날짜 미만까지 포함")
    a = parser.parse_args()
    parquet_dir = Path(a.parquet_dir)
    start, end = pd.Timestamp(a.start, tz="UTC"), pd.Timestamp(a.end, tz="UTC")
    OUT_DIR.mkdir(exist_ok=True)

    brands, price = outerwear_brands(parquet_dir, start, end)
    tables = {
        "growth_order_type": growth_order_type(parquet_dir, start, end),
        "funnel_purchase_paths": funnel_paths(parquet_dir, start, end),
        "funnel_session_identity": session_identity(parquet_dir, start, end),
        "funnel_event_order_link": event_order_link(parquet_dir),
        "outerwear_brands": brands,
        "outerwear_tnf_top_price": price,
    }
    for name, t in tables.items():
        t.to_csv(OUT_DIR / f"{name}.csv", index=False)
        print(f"\n[{name}]\n{t.round(2).to_string(index=False)}")


if __name__ == "__main__":
    main()
