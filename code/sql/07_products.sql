-- Grain: one sold item, not one representative-category order.
-- Complete order AND Complete item, snapshot cutoff in UTC.
CREATE OR REPLACE TABLE `{{PROJECT}}.{{DATASET}}.mart_product_mix_base` AS
SELECT i.oi_id, i.o_id, i.u_id, i.p_id,
  i.o_created_at AS order_date,
  DATE_TRUNC(DATE(i.o_created_at), MONTH) AS order_month,
  i.sale_price AS item_revenue,
  COALESCE(i.category, 'Unknown') AS category,
  COALESCE(i.brand, 'Unknown') AS brand,
  COALESCE(i.department, 'Unknown') AS department,
  i.o_status AS order_status, i.oi_status,
  i.age, i.gender, i.country
FROM `{{PROJECT}}.{{DATASET}}.df_oi` i
WHERE i.o_status = 'Complete' AND i.oi_status = 'Complete'
  AND i.o_created_at <= TIMESTAMP('2026-02-28 00:00:00+00');
