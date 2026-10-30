--df_oi
--order_items + orders + users + products + distribution_centers
--grain: order_item_id
--Page4, Page5에서 카테고리/브랜드/부서 분석에 쓰는 기본 테이블

CREATE OR REPLACE TABLE `{{PROJECT}}.{{DATASET}}.df_oi` AS
SELECT
  -- order_item
  oi.id AS oi_id,
  oi.order_id AS o_id,
  o.user_id AS u_id,
  oi.product_id AS p_id,
  oi.status AS oi_status,
  TIMESTAMP(oi.created_at) AS oi_created_at,
  TIMESTAMP(oi.shipped_at) AS oi_shipped_at,
  TIMESTAMP(oi.delivered_at) AS oi_delivered_at,
  TIMESTAMP(oi.returned_at) AS oi_returned_at,
  oi.sale_price,

  -- order
  o.status AS o_status,
  TIMESTAMP(o.created_at) AS o_created_at,
  TIMESTAMP(o.shipped_at) AS o_shipped_at,
  TIMESTAMP(o.delivered_at) AS o_delivered_at,
  TIMESTAMP(o.returned_at) AS o_returned_at,
  o.num_of_item,

  -- user
  u.age,
  u.gender,
  u.country,
  u.latitude AS u_latitude,
  u.longitude AS u_longitude,
  u.traffic_source AS u_traffic_source,
  TIMESTAMP(u.created_at) AS u_created_at,

  -- product
  p.cost,
  p.category,
  p.brand,
  p.retail_price,
  p.department,

  -- distribution
  d.id AS d_id,
  d.latitude AS d_latitude,
  d.longitude AS d_longitude

FROM `{{PROJECT}}.{{DATASET}}.order_items` oi
LEFT JOIN `{{PROJECT}}.{{DATASET}}.orders` o
  ON oi.order_id = o.order_id
LEFT JOIN `{{PROJECT}}.{{DATASET}}.users` u
  ON o.user_id = u.id
LEFT JOIN `{{PROJECT}}.{{DATASET}}.products` p
  ON oi.product_id = p.id
LEFT JOIN `{{PROJECT}}.{{DATASET}}.distribution_centers` d
  ON p.distribution_center_id = d.id;


-- df_e
-- events + users
-- grain: event_id
-- Page2 funnel용

CREATE OR REPLACE TABLE `{{PROJECT}}.{{DATASET}}.df_e` AS
SELECT
  -- event
  e.id AS e_id,
  e.user_id AS u_id,
  e.session_id,
  e.sequence_number,
  TIMESTAMP(e.created_at) AS e_created_at,
  e.browser,
  e.traffic_source AS e_traffic_source,
  e.uri,
  e.event_type,

  -- user
  u.age,
  u.gender,
  u.country,
  u.latitude AS u_latitude,
  u.longitude AS u_longitude,
  u.traffic_source AS u_traffic_source,
  TIMESTAMP(u.created_at) AS u_created_at

FROM `{{PROJECT}}.{{DATASET}}.events` e
LEFT JOIN `{{PROJECT}}.{{DATASET}}.users` u
  ON e.user_id = u.id;


-- fact_order
-- df_oi 기반 order level table
-- grain: order_id
-- Page1, Page3, Page4, Page5의 공통 기반

CREATE OR REPLACE TABLE `{{PROJECT}}.{{DATASET}}.fact_order` AS
WITH order_revenue AS (
  SELECT
    o_id,
    SUM(sale_price) AS order_revenue
  FROM `{{PROJECT}}.{{DATASET}}.df_oi`
  GROUP BY o_id
),

order_cost AS (
  SELECT
    o_id,
    SUM(cost) AS order_cost
  FROM `{{PROJECT}}.{{DATASET}}.df_oi`
  GROUP BY o_id
),

item_count AS (
  SELECT
    o_id,
    COUNT(oi_id) AS item_count
  FROM `{{PROJECT}}.{{DATASET}}.df_oi`
  GROUP BY o_id
),

order_base AS (
  SELECT DISTINCT
    o_id,
    u_id,
    o_status AS order_status,
    o_created_at,
    o_shipped_at,
    o_delivered_at,
    o_returned_at
  FROM `{{PROJECT}}.{{DATASET}}.df_oi`
),

cat_rev AS (
  SELECT
    o_id,
    category,
    SUM(sale_price) AS sale_price_sum
  FROM `{{PROJECT}}.{{DATASET}}.df_oi`
  GROUP BY o_id, category
),

primary_category AS (
  SELECT
    o_id,
    category AS primary_category
  FROM (
    SELECT
      o_id,
      category,
      sale_price_sum,
      ROW_NUMBER() OVER (
        PARTITION BY o_id
        ORDER BY sale_price_sum DESC, category
      ) AS rn
    FROM cat_rev
  )
  WHERE rn = 1
),

brand_rev AS (
  SELECT
    o_id,
    brand,
    SUM(sale_price) AS sale_price_sum
  FROM `{{PROJECT}}.{{DATASET}}.df_oi`
  GROUP BY o_id, brand
),

primary_brand AS (
  SELECT
    o_id,
    brand AS primary_brand
  FROM (
    SELECT
      o_id,
      brand,
      sale_price_sum,
      ROW_NUMBER() OVER (
        PARTITION BY o_id
        ORDER BY sale_price_sum DESC, brand
      ) AS rn
    FROM brand_rev
  )
  WHERE rn = 1
),

dept_rev AS (
  SELECT
    o_id,
    department,
    SUM(sale_price) AS sale_price_sum
  FROM `{{PROJECT}}.{{DATASET}}.df_oi`
  GROUP BY o_id, department
),

primary_department AS (
  SELECT
    o_id,
    department AS primary_department
  FROM (
    SELECT
      o_id,
      department,
      sale_price_sum,
      ROW_NUMBER() OVER (
        PARTITION BY o_id
        ORDER BY sale_price_sum DESC, department
      ) AS rn
    FROM dept_rev
  )
  WHERE rn = 1
),

unique_category AS (
  SELECT
    o_id,
    COUNT(DISTINCT category) AS unique_category_count
  FROM `{{PROJECT}}.{{DATASET}}.df_oi`
  GROUP BY o_id
),

unique_brand AS (
  SELECT
    o_id,
    COUNT(DISTINCT brand) AS unique_brand_count
  FROM `{{PROJECT}}.{{DATASET}}.df_oi`
  GROUP BY o_id
),

fact_order_base AS (
  SELECT
    ob.o_id,
    ob.u_id,
    ob.order_status,
    ob.o_created_at,
    ob.o_shipped_at,
    ob.o_delivered_at,
    ob.o_returned_at,
    r.order_revenue,
    c.order_cost,
    ic.item_count,
    uc.unique_category_count,
    ub.unique_brand_count,
    pc.primary_category,
    pb.primary_brand,
    pd.primary_department
  FROM order_base ob
  LEFT JOIN order_revenue r ON ob.o_id = r.o_id
  LEFT JOIN order_cost c ON ob.o_id = c.o_id
  LEFT JOIN item_count ic ON ob.o_id = ic.o_id
  LEFT JOIN unique_category uc ON ob.o_id = uc.o_id
  LEFT JOIN unique_brand ub ON ob.o_id = ub.o_id
  LEFT JOIN primary_category pc ON ob.o_id = pc.o_id
  LEFT JOIN primary_brand pb ON ob.o_id = pb.o_id
  LEFT JOIN primary_department pd ON ob.o_id = pd.o_id
),

fact_order_seq AS (
  SELECT
    *,
    TIMESTAMP(o_created_at) AS order_date,
    DATE_TRUNC(DATE(o_created_at), MONTH) AS order_month,
    (order_revenue - order_cost) AS order_margin,
    CASE WHEN o_returned_at IS NOT NULL THEN 1 ELSE 0 END AS is_returned,
    TIMESTAMP_DIFF(o_shipped_at, o_created_at, DAY) AS ship_delay_days,
    TIMESTAMP_DIFF(o_delivered_at, o_shipped_at, DAY) AS delivery_days,

    ROW_NUMBER() OVER (
      PARTITION BY u_id
      ORDER BY o_created_at, o_id
    ) AS order_sequence_number,

    LAG(TIMESTAMP(o_created_at)) OVER (
      PARTITION BY u_id
      ORDER BY o_created_at, o_id
    ) AS previous_order_date,

    MIN(TIMESTAMP(o_created_at)) OVER (
      PARTITION BY u_id
    ) AS first_order_date
  FROM fact_order_base
)

SELECT
  o_id,
  u_id,
  order_date,
  order_month,
  order_revenue,
  order_cost,
  order_margin,
  item_count,
  unique_category_count,
  unique_brand_count,
  primary_category,
  primary_brand,
  primary_department,
  order_status,
  is_returned,
  ship_delay_days,
  delivery_days,
  order_sequence_number,
  TIMESTAMP_DIFF(order_date, previous_order_date, DAY) AS days_since_previous_order,
  TIMESTAMP_DIFF(order_date, first_order_date, DAY) AS days_since_first_order
FROM fact_order_seq
WHERE order_date <= TIMESTAMP('2026-02-28 00:00:00+00');



-- dim_user
-- users + fact_order(Delivered + Complete) + df_e
-- grain: user_id
-- Page3 retention / Page5 segmentation

CREATE OR REPLACE TABLE `{{PROJECT}}.{{DATASET}}.dim_user` AS
WITH user_base AS (
  SELECT
    id AS u_id,
    age,
    gender,
    country,
    traffic_source AS u_traffic_source,
    TIMESTAMP(created_at) AS u_created_at
  FROM `{{PROJECT}}.{{DATASET}}.users`
),

fo_del AS (
  SELECT *
  FROM `{{PROJECT}}.{{DATASET}}.fact_order`
  WHERE order_status = 'Complete'
    AND order_date <= TIMESTAMP('2026-02-28 00:00:00+00')
),

u_total_orders AS (
  SELECT
    u_id,
    COUNT(DISTINCT o_id) AS total_orders_delivered
  FROM fo_del
  GROUP BY u_id
),

u_total_rev AS (
  SELECT
    u_id,
    SUM(order_revenue) AS total_revenue_delivered
  FROM fo_del
  GROUP BY u_id
),

u_first AS (
  SELECT
    u_id,
    MIN(order_date) AS first_order_date
  FROM fo_del
  GROUP BY u_id
),

u_last AS (
  SELECT
    u_id,
    MAX(order_date) AS last_order_date
  FROM fo_del
  GROUP BY u_id
),

-- Complete 주문을 고객별로 정렬해 첫 구매와 두 번째 구매를 정의한다.
fo_del_ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY u_id
      ORDER BY order_date, o_id
    ) AS complete_order_rank
  FROM fo_del
),

u_second AS (
  SELECT
    u_id,
    order_date AS second_order_date
  FROM fo_del_ranked
  WHERE complete_order_rank = 2
),

u_first_order_row AS (
  SELECT *
  FROM fo_del_ranked
  WHERE complete_order_rank = 1
),

u_first_feats AS (
  SELECT
    u_id,
    order_revenue AS first_order_revenue,
    primary_category AS first_primary_category,
    primary_brand AS first_primary_brand,
    primary_department AS first_primary_department,
    item_count AS first_item_count,
    order_margin AS first_order_margin,
    ship_delay_days AS first_ship_delay_days,
    delivery_days AS first_delivery_days,
    is_returned AS first_is_returned
  FROM u_first_order_row
),

u_repeat_base AS (
  SELECT
    f.u_id,
    f.first_order_date,
    s.second_order_date,
    TIMESTAMP_DIFF(s.second_order_date, f.first_order_date, DAY) AS days_to_2nd_order,

    TIMESTAMP_DIFF(TIMESTAMP('2026-02-28'), f.first_order_date, DAY) >= 90 AS eligible_90,
    TIMESTAMP_DIFF(TIMESTAMP('2026-02-28'), f.first_order_date, DAY) >= 180 AS eligible_180,
    TIMESTAMP_DIFF(TIMESTAMP('2026-02-28'), f.first_order_date, DAY) >= 365 AS eligible_365
  FROM u_first f
  LEFT JOIN u_second s
    ON f.u_id = s.u_id
),

u_repeat_final AS (
  SELECT
    u_id,
    second_order_date,
    days_to_2nd_order,
    eligible_90,
    eligible_180,
    eligible_365,

    CASE
      WHEN eligible_90 AND second_order_date <= TIMESTAMP_ADD(first_order_date, INTERVAL 90 DAY) THEN 1
      ELSE 0
    END AS repeat_90,

    CASE
      WHEN eligible_180 AND second_order_date <= TIMESTAMP_ADD(first_order_date, INTERVAL 180 DAY) THEN 1
      ELSE 0
    END AS repeat_180,

    CASE
      WHEN eligible_365 AND second_order_date <= TIMESTAMP_ADD(first_order_date, INTERVAL 365 DAY) THEN 1
      ELSE 0
    END AS repeat_365
  FROM u_repeat_base
),

u_has_event AS (
  SELECT
    u_id,
    1 AS has_event
  FROM (
    SELECT
      u_id,
      COUNT(*) AS event_cnt
    FROM `{{PROJECT}}.{{DATASET}}.df_e`
    WHERE e_created_at <= TIMESTAMP('2026-02-28 00:00:00+00')
    GROUP BY u_id
  )
),

e_sorted AS (
  SELECT *
  FROM `{{PROJECT}}.{{DATASET}}.df_e`
  WHERE e_created_at <= TIMESTAMP('2026-02-28 00:00:00+00')
),

u_first_touch AS (
  SELECT
    u_id,
    browser AS first_browser,
    e_traffic_source AS first_traffic_source
  FROM (
    SELECT
      *,
      ROW_NUMBER() OVER (
        PARTITION BY u_id
        ORDER BY e_created_at ASC, e_id ASC
      ) AS rn
    FROM e_sorted e
    WHERE EXISTS (SELECT 1 FROM u_first f WHERE f.u_id = e.u_id AND e.e_created_at <= f.first_order_date)
  )
  WHERE rn = 1
),

u_last_touch AS (
  SELECT
    u_id,
    browser AS last_browser,
    e_traffic_source AS last_traffic_source
  FROM (
    SELECT
      *,
      ROW_NUMBER() OVER (
        PARTITION BY u_id
        ORDER BY e_created_at DESC, e_id DESC
      ) AS rn
    FROM e_sorted
  )
  WHERE rn = 1
),

browser_cnt AS (
  SELECT
    u_id,
    browser,
    COUNT(*) AS cnt
  FROM e_sorted
  GROUP BY u_id, browser
),

u_dom_browser AS (
  SELECT
    u_id,
    browser AS dominant_browser
  FROM (
    SELECT
      *,
      ROW_NUMBER() OVER (
        PARTITION BY u_id
        ORDER BY cnt DESC, browser
      ) AS rn
    FROM browser_cnt
  )
  WHERE rn = 1
),

source_cnt AS (
  SELECT
    u_id,
    e_traffic_source,
    COUNT(*) AS cnt
  FROM e_sorted
  GROUP BY u_id, e_traffic_source
),

u_dom_source AS (
  SELECT
    u_id,
    e_traffic_source AS dominant_traffic_source
  FROM (
    SELECT
      *,
      ROW_NUMBER() OVER (
        PARTITION BY u_id
        ORDER BY cnt DESC, e_traffic_source
      ) AS rn
    FROM source_cnt
  )
  WHERE rn = 1
)

SELECT
  ub.u_id,

  ub.age,
  ub.gender,
  ub.country,
  ub.u_traffic_source,
  ub.u_created_at,

  COALESCE(eh.has_event, 0) AS has_event,
  CASE WHEN COALESCE(uto.total_orders_delivered, 0) > 0 THEN 1 ELSE 0 END AS has_order,
  CASE
    WHEN COALESCE(eh.has_event, 0) = 0
     AND COALESCE(uto.total_orders_delivered, 0) = 0
    THEN 1 ELSE 0
  END AS is_inactive,
  CASE
    WHEN COALESCE(eh.has_event, 0) = 1
     AND COALESCE(uto.total_orders_delivered, 0) = 0
    THEN 1 ELSE 0
  END AS is_browser_only,

  ft.first_browser,
  db.dominant_browser,
  lt.last_browser,

  ft.first_traffic_source,
  ds.dominant_traffic_source,
  lt.last_traffic_source,

  uf.first_order_date,
  DATE_TRUNC(DATE(uf.first_order_date), MONTH) AS first_order_month,
  ff.first_order_revenue,

  rf.second_order_date,
  rf.days_to_2nd_order,
  ul.last_order_date,

  COALESCE(uto.total_orders_delivered, 0) AS total_orders_delivered,
  COALESCE(utr.total_revenue_delivered, 0) AS total_revenue_delivered,
  CASE
    WHEN COALESCE(uto.total_orders_delivered, 0) > 0
    THEN COALESCE(utr.total_revenue_delivered, 0) / uto.total_orders_delivered
    ELSE NULL
  END AS aov_delivered,

  COALESCE(rf.eligible_90, FALSE) AS eligible_90,
  COALESCE(rf.repeat_90, 0) AS repeat_90,
  COALESCE(rf.eligible_180, FALSE) AS eligible_180,
  COALESCE(rf.repeat_180, 0) AS repeat_180,
  COALESCE(rf.eligible_365, FALSE) AS eligible_365,
  COALESCE(rf.repeat_365, 0) AS repeat_365,

  ff.first_primary_category,
  ff.first_primary_brand,
  ff.first_primary_department,
  ff.first_item_count,
  ff.first_order_margin,
  ff.first_ship_delay_days,
  ff.first_delivery_days,
  ff.first_is_returned

FROM user_base ub
LEFT JOIN u_total_orders uto ON ub.u_id = uto.u_id
LEFT JOIN u_total_rev utr ON ub.u_id = utr.u_id
LEFT JOIN u_first uf ON ub.u_id = uf.u_id
LEFT JOIN u_last ul ON ub.u_id = ul.u_id
LEFT JOIN u_repeat_final rf ON ub.u_id = rf.u_id
LEFT JOIN u_first_feats ff ON ub.u_id = ff.u_id
LEFT JOIN u_has_event eh ON ub.u_id = eh.u_id
LEFT JOIN u_first_touch ft ON ub.u_id = ft.u_id
LEFT JOIN u_last_touch lt ON ub.u_id = lt.u_id
LEFT JOIN u_dom_browser db ON ub.u_id = db.u_id
LEFT JOIN u_dom_source ds ON ub.u_id = ds.u_id;





-- df_oi check
SELECT 
  COUNT(*) AS n_rows, 
  COUNT(DISTINCT oi_id) AS n_distinct_oi_id
FROM `{{PROJECT}}.{{DATASET}}.df_oi`;


-- df_e check
SELECT 
  COUNT(*) AS n_rows, 
  COUNT(DISTINCT e_id) AS n_distinct_e_id
FROM `{{PROJECT}}.{{DATASET}}.df_e`;


-- fact_order check
SELECT 
  COUNT(*) AS n_rows, 
  COUNT(DISTINCT o_id) AS n_distinct_o_id
FROM `{{PROJECT}}.{{DATASET}}.fact_order`;


-- dim_user check
SELECT 
  COUNT(*) AS n_rows, 
  COUNT(DISTINCT u_id) AS n_distinct_u_id
FROM `{{PROJECT}}.{{DATASET}}.dim_user`;


-- repeat flag check
SELECT
  eligible_90,
  repeat_90,
  COUNT(*) AS users
FROM `{{PROJECT}}.{{DATASET}}.dim_user`
GROUP BY 1,2
ORDER BY 1,2;
