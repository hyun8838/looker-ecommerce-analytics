-- Page 3: Retention & Cohorts


CREATE OR REPLACE TABLE `{{PROJECT}}.{{DATASET}}.mart_retention_cohort` AS
WITH orders AS (
  SELECT
    u_id,
    DATE(order_date) AS order_date,
    DATE_TRUNC(DATE(order_date), MONTH) AS order_month
  FROM `{{PROJECT}}.{{DATASET}}.fact_order`
  WHERE order_status = 'Complete'
    AND order_date <= TIMESTAMP('2026-02-28 00:00:00+00')
    AND u_id IS NOT NULL
    AND order_date IS NOT NULL
),

first_order AS (
  SELECT
    u_id,
    MIN(order_date) AS first_order_date
  FROM orders
  GROUP BY u_id
),

orders_with_first AS (
  SELECT
    o.u_id,
    o.order_date,
    o.order_month,
    DATE_TRUNC(f.first_order_date, MONTH) AS first_order_month,
    DATE_DIFF(o.order_month, DATE_TRUNC(f.first_order_date, MONTH), MONTH) AS cohort_index
  FROM orders o
  LEFT JOIN first_order f
    ON o.u_id = f.u_id
)

SELECT
  first_order_month,
  cohort_index,
  COUNT(DISTINCT u_id) AS users
FROM orders_with_first
GROUP BY 1, 2
ORDER BY 1, 2;