-- Page 2: Funnel & Conversion

CREATE OR REPLACE TABLE `{{PROJECT}}.{{DATASET}}.mart_funnel_session` AS
WITH base AS (
  SELECT
    session_id,
    e_id,
    u_id,
    event_type,
    e_created_at,
    e_traffic_source,
    uri
  FROM `{{PROJECT}}.{{DATASET}}.df_e`
  WHERE session_id IS NOT NULL
    AND e_created_at <= TIMESTAMP('2026-02-28 00:00:00+00')
),

session_agg AS (
  SELECT
    session_id,

    ARRAY_AGG(event_type ORDER BY e_created_at, e_id) AS session_event_array,
    STRING_AGG(event_type, ' → ' ORDER BY e_created_at, e_id) AS sequence,

    ARRAY_AGG(event_type ORDER BY e_created_at, e_id LIMIT 1)[OFFSET(0)] AS entry_event,
    MAX(CASE WHEN u_id IS NOT NULL THEN 1 ELSE 0 END) AS is_member,

    MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS has_purchase,
    MAX(CASE WHEN event_type = 'cancel' THEN 1 ELSE 0 END) AS has_cancel,
    COUNTIF(event_type = 'cart') AS cart_count,

    MIN(e_created_at) AS e_created_at,
    EXTRACT(YEAR FROM MIN(e_created_at)) AS year,
    DATE_TRUNC(DATE(MIN(e_created_at)), MONTH) AS month,

    ARRAY_AGG(e_traffic_source ORDER BY e_created_at, e_id LIMIT 1)[OFFSET(0)] AS e_traffic_source,
    ARRAY_AGG(NULLIF(REGEXP_EXTRACT(uri, r'category/([^/]+)'), '') ORDER BY e_created_at, e_id LIMIT 1)[OFFSET(0)] AS category
  FROM base
  GROUP BY session_id
)

SELECT
  session_id,
  session_event_array,
  sequence,
  entry_event,
  is_member,
  has_purchase,
  has_cancel,
  cart_count,
  CASE WHEN cart_count >= 3 THEN '3+' ELSE CAST(cart_count AS STRING) END AS cart_bucket,
  e_created_at,
  year,
  month,
  e_traffic_source,
  category
FROM session_agg;