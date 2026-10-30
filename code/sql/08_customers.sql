-- Page 5: User Behavior


CREATE OR REPLACE TABLE `{{PROJECT}}.{{DATASET}}.mart_behavior_user_base` AS
WITH orders AS (
  SELECT
    u_id,
    COALESCE(category, 'Unknown') AS primary_category,
    COALESCE(department, 'Unknown') AS primary_department
  FROM `{{PROJECT}}.{{DATASET}}.df_oi`
  WHERE o_status = 'Complete' AND oi_status = 'Complete'
    AND o_created_at <= TIMESTAMP('2026-02-28 00:00:00+00')
    AND u_id IS NOT NULL
    AND o_created_at IS NOT NULL
),

breadth AS (
  SELECT
    u_id,
    COUNT(DISTINCT primary_category) AS unique_category_count,
    COUNT(DISTINCT primary_department) AS unique_department_count
  FROM orders
  GROUP BY u_id
),

buyers AS (
  SELECT
    d.u_id,
    d.has_order,
    d.first_order_date,
    d.second_order_date,
    d.days_to_2nd_order,
    d.last_order_date,
    d.total_orders_delivered,
    d.total_revenue_delivered,
    d.aov_delivered,
    d.eligible_90,
    d.repeat_90,
    d.eligible_180,
    d.repeat_180,
    d.eligible_365,
    d.repeat_365,
    d.first_order_revenue,
    d.first_primary_category,
    d.first_primary_brand,
    d.first_primary_department,
    d.first_item_count,
    COALESCE(d.first_traffic_source, 'Unknown') AS first_traffic_source
  FROM `{{PROJECT}}.{{DATASET}}.dim_user` d
  WHERE d.has_order = 1
)

SELECT
  b.*,
  br.unique_category_count,
  br.unique_department_count,

  CASE
    WHEN b.first_item_count IS NULL THEN NULL
    WHEN b.first_item_count <= 1 THEN '1 item'
    WHEN b.first_item_count = 2 THEN '2 items'
    ELSE '3+ items'
  END AS basket_size_seg,

  CASE
    WHEN b.total_orders_delivered IS NULL THEN NULL
    WHEN b.total_orders_delivered = 1 THEN '1 order'
    WHEN b.total_orders_delivered = 2 THEN '2 orders'
    ELSE '3+ orders'
  END AS purchase_freq_seg,

  CASE
    WHEN b.days_to_2nd_order IS NULL THEN 'No 2nd purchase'
    WHEN b.days_to_2nd_order = 0 THEN 'Within 24h'
    WHEN b.days_to_2nd_order BETWEEN 1 AND 30 THEN '1-30d'
    WHEN b.days_to_2nd_order BETWEEN 31 AND 90 THEN '31-90d'
    ELSE '90d+'
  END AS time_to_2nd_seg,

  CASE
    WHEN br.unique_category_count IS NULL THEN NULL
    WHEN br.unique_category_count = 1 THEN '1 category'
    WHEN br.unique_category_count = 2 THEN '2 categories'
    ELSE '3+ categories'
  END AS category_breadth_seg

FROM buyers b
LEFT JOIN breadth br
  ON b.u_id = br.u_id;