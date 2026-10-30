"""Status sensitivity and fixed-population repeat comparisons; no mart mutation."""
from functools import lru_cache
import pandas as pd
from data_mart.parquet_loader import load_parquet
from data_mart.analysis_contract import OBSERVATION_END, PURCHASE_STATUS, GROWTH_STATUSES


def build_repeat_customers(orders, statuses, observation_end=OBSERVATION_END):
    """First and second DISTINCT orders within the snapshot, ordered by timestamp/id."""
    d=orders.copy()
    if d['o_id'].isna().any() or d['o_id'].duplicated().any():
        raise ValueError('fact_order requires unique non-null order ids')
    d['order_date']=pd.to_datetime(d['order_date'],utc=True,errors='coerce')
    d=d[d.order_status.isin(statuses) & d.order_date.le(observation_end)].dropna(subset=['u_id','order_date'])
    d=d.sort_values(['u_id','order_date','o_id'])
    d['rank']=d.groupby('u_id').cumcount()
    first=d[d['rank'].eq(0)].set_index('u_id').order_date
    second=d[d['rank'].eq(1)].set_index('u_id').order_date.reindex(first.index)
    out=pd.DataFrame({'first_order_date':first,'second_order_date':second}).reset_index()
    for w in [90,180,365]:
        out[f'eligible_{w}']=(observation_end-out.first_order_date).ge(pd.Timedelta(days=w))
        out[f'repeat_{w}']=(out[f'eligible_{w}'] & out.second_order_date.notna() &
            (out.second_order_date-out.first_order_date).le(pd.Timedelta(days=w))).astype(int)
    return out


@lru_cache(maxsize=2)
def load_status_customers(statuses):
    return build_repeat_customers(load_parquet('fact_order'),statuses)


def summarize_repeat(customers, common_window=None):
    rows=[]
    for w in [90,180,365]:
        eligible=customers[f'eligible_{common_window or w}'].fillna(False).astype(bool)
        n=int(eligible.sum());k=int(customers.loc[eligible,f'repeat_{w}'].sum())
        rows.append({'window_days':w,'eligible':n,'repeat':k,'rate':k/n if n else float('nan')})
    return pd.DataFrame(rows)


def status_comparison(start_year=None,start_month=None,end_year=None,end_month=None):
    rows=[]
    for label,statuses in [('Complete', (PURCHASE_STATUS,)),('Non-cancelled',GROWTH_STATUSES)]:
        d=load_status_customers(tuple(statuses)).copy()
        if start_year is not None:
            start=pd.Timestamp(int(start_year),int(start_month),1,tz='UTC')
            end=pd.Timestamp(int(end_year),int(end_month),1,tz='UTC')+pd.offsets.MonthBegin(1)
            d=d[d.first_order_date.ge(start)&d.first_order_date.lt(end)]
        t=summarize_repeat(d);t['status_basis']=label;rows.append(t)
    return pd.concat(rows,ignore_index=True)
