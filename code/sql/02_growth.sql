-- Page 1: Growth Structure

CREATE OR REPLACE TABLE `{{PROJECT}}.{{DATASET}}.mart_growth_kpi` AS
WITH fact AS (
  SELECT
    o_id,
    u_id,
    order_date,
    DATE_TRUNC(DATE(order_date), MONTH) AS order_month,
    order_revenue,
    order_sequence_number,
    order_status
  FROM `{{PROJECT}}.{{DATASET}}.fact_order`
  WHERE order_status != 'Cancelled'
    AND order_date <= TIMESTAMP('2026-02-28 00:00:00+00')
),

-- Cancelled를 제외한 주문을 고객별로 정렬해 신규·재구매 매출을 구분한다.
fact_ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY u_id
      ORDER BY order_date, o_id
    ) AS local_order_rank
  FROM fact
),

revenue_monthly AS (
  SELECT
    order_month,
    SUM(order_revenue) AS total_revenue
  FROM fact_ranked
  GROUP BY order_month
),

rev_type_monthly AS (
  SELECT
    order_month,
    CASE WHEN local_order_rank = 1 THEN 'new' ELSE 'repeat' END AS customer_type,
    SUM(order_revenue) AS revenue
  FROM fact_ranked
  GROUP BY 1, 2
),

rev_type_pivot AS (
  SELECT
    order_month,
    SUM(CASE WHEN customer_type = 'new' THEN revenue ELSE 0 END) AS new_revenue,
    SUM(CASE WHEN customer_type = 'repeat' THEN revenue ELSE 0 END) AS repeat_revenue
  FROM rev_type_monthly
  GROUP BY order_month
),

orders_monthly AS (
  SELECT
    order_month,
    COUNT(DISTINCT o_id) AS orders
  FROM fact_ranked
  GROUP BY order_month
),

buyers AS (
  SELECT
    order_month,
    COUNT(DISTINCT u_id) AS buyers
  FROM fact_ranked
  GROUP BY order_month
),

repeat_buyers AS (
  SELECT
    order_month,
    COUNT(DISTINCT u_id) AS repeat_buyers
  FROM fact_ranked
  WHERE local_order_rank >= 2
  GROUP BY order_month
),

events_base AS (
 SELECT DATE_TRUNC(DATE(e_created_at), MONTH) AS event_month, session_id, u_id
 FROM `{{PROJECT}}.{{DATASET}}.df_e`
 WHERE e_created_at <= TIMESTAMP('2026-02-28 00:00:00+00')
),
session_base AS (
 SELECT session_id, DATE_TRUNC(DATE(MIN(e_created_at)), MONTH) AS event_month,
 MAX(IF(event_type = 'purchase', 1, 0)) AS has_purchase
 FROM `{{PROJECT}}.{{DATASET}}.df_e`
 WHERE e_created_at <= TIMESTAMP('2026-02-28 00:00:00+00') AND session_id IS NOT NULL
 GROUP BY session_id
),
visitors AS (
 SELECT event_month, COUNT(*) AS Visitors, SUM(has_purchase) AS purchase_sessions
 FROM session_base GROUP BY event_month
),
mau AS (
 SELECT event_month, COUNT(DISTINCT u_id) AS MAU
 FROM events_base WHERE u_id IS NOT NULL GROUP BY event_month
),
months AS (
 SELECT order_month FROM revenue_monthly UNION DISTINCT SELECT event_month FROM visitors
)

SELECT
  z.order_month,
  COALESCE(r.total_revenue, 0) AS total_revenue,
  COALESCE(tp.new_revenue, 0) AS new_revenue,
  COALESCE(tp.repeat_revenue, 0) AS repeat_revenue,
  SAFE_DIVIDE(COALESCE(tp.repeat_revenue, 0), r.total_revenue) AS repeat_share,

  COALESCE(v.Visitors, 0) AS Visitors,
  COALESCE(v.purchase_sessions, 0) AS purchase_sessions,
  COALESCE(m.MAU, 0) AS MAU,
  COALESCE(b.buyers, 0) AS buyers,
  COALESCE(rb.repeat_buyers, 0) AS repeat_buyers,
  COALESCE(o.orders, 0) AS orders,

  SAFE_DIVIDE(COALESCE(v.purchase_sessions, 0), v.Visitors) AS conversion_rate,
  SAFE_DIVIDE(COALESCE(b.buyers, 0), v.Visitors) AS buyers_per_session,
  SAFE_DIVIDE(COALESCE(b.buyers, 0), m.MAU) AS buyer_penetration_in_mau,
  SAFE_DIVIDE(COALESCE(rb.repeat_buyers, 0), b.buyers) AS repeat_buyer_rate,

  SAFE_DIVIDE(COALESCE(r.total_revenue, 0), o.orders) AS AOV,
  SAFE_DIVIDE(COALESCE(r.total_revenue, 0), m.MAU) AS revenue_per_active_user,
  SAFE_DIVIDE(COALESCE(r.total_revenue, 0), v.Visitors) AS revenue_per_visitor

FROM months z
LEFT JOIN revenue_monthly r ON z.order_month = r.order_month
LEFT JOIN rev_type_pivot tp ON z.order_month = tp.order_month
LEFT JOIN visitors v ON z.order_month = v.event_month
LEFT JOIN mau m ON z.order_month = m.event_month
LEFT JOIN buyers b ON z.order_month = b.order_month
LEFT JOIN repeat_buyers rb ON z.order_month = rb.order_month
LEFT JOIN orders_monthly o ON z.order_month = o.order_month
ORDER BY z.order_month;