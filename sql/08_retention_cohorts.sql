-- Retention and Cohort Analysis
-- Dialect: DuckDB
-- Scope: first-order cohorts, repeat conversion, and 30/60/90-day retention.

CREATE OR REPLACE VIEW orders AS SELECT * FROM read_csv_auto('data/raw/orders.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW users AS SELECT * FROM read_csv_auto('data/raw/users.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW markets AS SELECT * FROM read_csv_auto('data/raw/markets.csv', HEADER = TRUE);

-- ===========================================================================
-- Analysis 1: What is the first-to-second-order conversion rate?
-- ===========================================================================
-- Business question:
-- How many customers who complete a first order return for a second order?
--
-- Metric definition:
-- first_order = first DELIVERED order per user
-- repeat_user = user with a later DELIVERED order
--
-- Grain: one row per first-order user before the final summary.

WITH delivered AS (
    SELECT
        user_id,
        order_id,
        order_timestamp,
        ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_timestamp, order_id) AS order_number
    FROM orders
    WHERE order_status = 'DELIVERED'
), user_repeat AS (
    SELECT
        user_id,
        MAX(order_number) AS delivered_order_count
    FROM delivered
    GROUP BY user_id
)
SELECT
    COUNT(*) AS first_order_users,
    COUNT(*) FILTER (WHERE delivered_order_count >= 2) AS repeat_users,
    ROUND(COUNT(*) FILTER (WHERE delivered_order_count >= 2) * 100.0 / COUNT(*), 2) AS first_to_second_rate_pct
FROM user_repeat;

-- Observed result: 53,840 of 54,628 activated users place at least a second
-- delivered order, or approximately 98.56%.
-- Interpretation: first-to-second conversion is highly saturated in this data;
-- retention-depth and timing metrics are more discriminating.

-- ===========================================================================
-- Analysis 2: What is 30/60/90-day repeat retention?
-- ===========================================================================
-- Business question:
-- How quickly do first-order customers return, using only cohorts with complete
-- observation windows?
--
-- Metric definition:
-- Denominator: users whose first delivered order occurred on or before
-- 2025-10-01, allowing a complete 90-day window.
-- Numerator: user has a later delivered order within 30, 60, or 90 days.
--
-- Grain: one row for the retention summary.

WITH delivered AS (
    SELECT
        user_id,
        order_timestamp,
        ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_timestamp, order_id) AS order_number
    FROM orders
    WHERE order_status = 'DELIVERED'
), first_orders AS (
    SELECT user_id, order_timestamp AS first_order_timestamp
    FROM delivered
    WHERE order_number = 1
      AND order_timestamp <= TIMESTAMP '2025-10-01'
), repeat_flags AS (
    SELECT
        f.user_id,
        MAX(CASE WHEN d.order_timestamp > f.first_order_timestamp
                  AND d.order_timestamp <= f.first_order_timestamp + INTERVAL 30 DAY THEN 1 ELSE 0 END) AS retained_30d,
        MAX(CASE WHEN d.order_timestamp > f.first_order_timestamp
                  AND d.order_timestamp <= f.first_order_timestamp + INTERVAL 60 DAY THEN 1 ELSE 0 END) AS retained_60d,
        MAX(CASE WHEN d.order_timestamp > f.first_order_timestamp
                  AND d.order_timestamp <= f.first_order_timestamp + INTERVAL 90 DAY THEN 1 ELSE 0 END) AS retained_90d
    FROM first_orders f
    LEFT JOIN delivered d ON f.user_id = d.user_id
    GROUP BY f.user_id
)
SELECT
    COUNT(*) AS eligible_first_order_users,
    ROUND(AVG(retained_30d) * 100, 2) AS retention_30d_pct,
    ROUND(AVG(retained_60d) * 100, 2) AS retention_60d_pct,
    ROUND(AVG(retained_90d) * 100, 2) AS retention_90d_pct
FROM repeat_flags;

-- Observed result: 30-day repeat is approximately 49.54%, 60-day repeat
-- 70.87%, and 90-day repeat 81.76% for complete-window cohorts.
-- Interpretation: the largest measurable drop occurs before 30 days; this is
-- the most useful window for future activation and early-retention investigation.

-- ===========================================================================
-- Analysis 3: How do first-order cohorts compare over time and market?
-- ===========================================================================
-- Business question:
-- Are repeat outcomes consistent across signup/first-order cohorts and markets?
--
-- Metric definition:
-- cohort_month = calendar month of first delivered order
-- 90-day retention uses only cohort users whose first order permits a full window.
--
-- Grain: one row per first-order month and market.

WITH delivered AS (
    SELECT
        user_id,
        market_id,
        order_timestamp,
        ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_timestamp, order_id) AS order_number
    FROM orders
    WHERE order_status = 'DELIVERED'
), first_orders AS (
    SELECT user_id, market_id, order_timestamp AS first_order_timestamp
    FROM delivered
    WHERE order_number = 1
      AND order_timestamp <= TIMESTAMP '2025-10-01'
), cohort_flags AS (
    SELECT
        f.market_id,
        DATE_TRUNC('month', f.first_order_timestamp) AS cohort_month,
        f.user_id,
        MAX(CASE WHEN d.order_timestamp > f.first_order_timestamp
                  AND d.order_timestamp <= f.first_order_timestamp + INTERVAL 90 DAY THEN 1 ELSE 0 END) AS retained_90d
    FROM first_orders f
    LEFT JOIN delivered d ON f.user_id = d.user_id
    GROUP BY f.market_id, DATE_TRUNC('month', f.first_order_timestamp), f.user_id
)
SELECT
    m.country,
    cohort_month,
    COUNT(*) AS cohort_users,
    ROUND(AVG(retained_90d) * 100, 2) AS retention_90d_pct
FROM cohort_flags c
JOIN markets m USING (market_id)
GROUP BY m.country, cohort_month
HAVING COUNT(*) >= 50
ORDER BY cohort_month, m.country;

-- Interpretation:
-- Use this output to compare cohort consistency rather than relying on one
-- aggregate retention number. Cohort differences are observed patterns; they do
-- not establish a causal effect without controlling for acquisition mix and
-- operating conditions.
