"""* 노트북 분석용 고정 스냅샷 필터로 Dash 페이지 함수 실행"""
from pathlib import Path
import sys

import pandas as pd
from plotly.graph_objects import Figure

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from dashboard.pages import growth, funnel, retention, product_mix, behavior
from data_mart.parquet_loader import load_parquet
from figures.customers import load_behavior_user_base_data, build_segment_kpi_table

# Snapshot filters are fixed so saved notebook charts remain reproducible.
# Retention/customer dates cover all available first-order dates in this snapshot.
PERIOD = ('2023', '1', '2025', '12')
PAGE_CALLBACKS = {
    'growth': (
        (growth.update_growth_sections, PERIOD),
        (growth.update_geo_section, (*PERIOD, 'United States', '10')),
        (growth.update_growth_kpis, PERIOD),
    ),
    'funnel': (
        (funnel.update_funnel_sections, (*PERIOD, 'All', 'All')),
        (funnel.update_funnel_kpis, (*PERIOD, 'All', 'All')),
    ),
    'retention': (
        (retention.update_retention_page,
         (2019, 1, 2026, 2, 'month', 12, 1, 'include', '90')),
    ),
    'product_mix': (
        (product_mix.update_p4_market_structure, PERIOD),
        (product_mix.update_p4_composition, ('10', *PERIOD)),
        (product_mix.update_p4_drilldown, ('All', *PERIOD)),
        (product_mix.update_p4_heatmap, ('dept_category', 'All', *PERIOD)),
        (product_mix.update_product_kpis, PERIOD),
    ),
    'behavior': (
        (behavior.update_behavior_page, (2019, 1, 2026, 2, 'repeat90', None)),
    ),
}


def _figures(value):
    """* 중첩된 Dash 콜백 출력에서 표시 순서대로 그래프 추출"""
    if isinstance(value, Figure):
        yield value
    elif isinstance(value, (tuple, list)):
        for child in value:
            yield from _figures(child)
    elif hasattr(value, 'to_plotly_json'):
        figure = getattr(value, 'figure', None)
        if figure is not None:
            yield Figure(figure)
        yield from _figures(getattr(value, 'children', None))


def _cards(value):
    """* 그래프와 동일한 콜백 결과에서 KPI 제목·값 추출"""
    if isinstance(value, (tuple, list)):
        for child in value:
            yield from _cards(child)
    elif hasattr(value, 'to_plotly_json'):
        if getattr(value, 'className', '') in ('kpi-card-title', 'kpi-card-value'):
            yield value.children
        children = getattr(value, 'children', None)
        if children is not None:
            yield from _cards(children)


def analyze_page(page):
    chart_list = []
    cards = []
    for callback, inputs in PAGE_CALLBACKS[page]:
        output = callback(*inputs)
        chart_list.extend(_figures(output))
        cards.extend(_cards(output))

    if page == 'growth':
        summary = load_parquet('mart_growth_kpi').tail(12)
    elif page == 'funnel':
        data = load_parquet('mart_funnel_session')
        summary = pd.DataFrame({
            'sessions': [len(data)],
            'purchase_event_sessions': [int(data.has_purchase.sum())],
            'cancel_event_sessions': [int(data.has_cancel.sum())],
        })
    elif page == 'retention':
        from data_mart.repeat_comparison import summarize_repeat, status_comparison
        data = load_parquet('mart_retention_user')
        summary = summarize_repeat(data)
        summary['comparison'] = 'Complete: per-window eligible'
        common = summarize_repeat(data, common_window=365)
        common['comparison'] = 'Complete: fixed 365-day eligible'
        sensitivity = status_comparison()
        sensitivity['comparison'] = 'Status sensitivity: ' + sensitivity.status_basis
        summary = pd.concat([summary, common, sensitivity], ignore_index=True)
    elif page == 'product_mix':
        data = load_parquet('mart_product_mix_base')
        summary = data.groupby('category').item_revenue.sum().sort_values(ascending=False).to_frame()
        summary['share'] = summary.item_revenue / summary.item_revenue.sum()
    else:
        summary = build_segment_kpi_table(load_behavior_user_base_data(), 'customer_value_seg')
    return {'summary': summary, 'figures': chart_list, 'cards': cards}
