-- Page 2: Funnel & Conversion

CREATE OR REPLACE TABLE `{{PROJECT}}.{{DATASET}}.mart_funnel_transition` AS
WITH seq AS (
  SELECT
    session_id,
    event_type,
    e_created_at,
    e_id,
    LEAD(event_type) OVER (
      PARTITION BY session_id
      ORDER BY e_created_at, e_id
    ) AS next_event
  FROM `{{PROJECT}}.{{DATASET}}.df_e`
  WHERE session_id IS NOT NULL
    AND e_created_at <= TIMESTAMP('2026-02-28 00:00:00+00')
)

SELECT
  event_type AS source,
  next_event AS target,
  COUNT(*) AS value
FROM seq
WHERE next_event IS NOT NULL
GROUP BY 1, 2;