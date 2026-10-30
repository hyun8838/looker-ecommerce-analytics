-- Page 3: Retention & Cohorts


CREATE OR REPLACE TABLE `{{PROJECT}}.{{DATASET}}.mart_retention_user` AS
SELECT
  u_id,
  has_order,
  first_order_date,
  second_order_date,
  days_to_2nd_order,
  last_order_date,
  total_orders_delivered,
  total_revenue_delivered,
  aov_delivered,

  eligible_90,
  repeat_90,
  eligible_180,
  repeat_180,
  eligible_365,
  repeat_365,

  first_order_revenue,
  first_item_count,
  first_primary_category,
  first_primary_brand,
  first_primary_department,

  first_browser,
  dominant_browser,
  last_browser,
  first_traffic_source,
  dominant_traffic_source,
  last_traffic_source,

  CASE
    WHEN first_primary_category IN ('Underwear','Socks & Hosiery','Tops & Tees','Swim','Sleep & Lounge','Leggings','Socks','Intimates')
      THEN 'Consumable'
    WHEN first_primary_category IN ('Outerwear & Coats','Suits & Sport Coats','Blazers & Jackets','Fashion Hoodies & Sweatshirts','Sweaters','Suits','Dresses','Jumpsuits & Rompers','Plus')
      THEN 'Non-Consumable'
    WHEN first_primary_category IN ('Pants','Pants & Capris','Jeans','Shorts','Skirts','Clothing Sets','Accessories','Maternity','Active')
      THEN 'Neutral'
    WHEN first_primary_category IS NULL THEN NULL
    ELSE 'Other'
  END AS first_category_group

FROM `{{PROJECT}}.{{DATASET}}.dim_user`;