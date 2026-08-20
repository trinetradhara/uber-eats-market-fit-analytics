-- Marketplace Health Analysis
-- Dialect: DuckDB
-- Scope: marketplace scale, engagement, city health, supply balance,
-- concentration, trends, and order-level economics.
-- This file intentionally does not analyze retention cohorts, delivery RCA,
-- promotions, or customer experience in depth; those belong to later themes.

CREATE OR REPLACE VIEW markets AS SELECT * FROM read_csv_auto('data/raw/markets.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW cities AS SELECT * FROM read_csv_auto('data/raw/cities.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW users AS SELECT * FROM read_csv_auto('data/raw/users.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW restaurants AS SELECT * FROM read_csv_auto('data/raw/restaurants.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW delivery_partners AS SELECT * FROM read_csv_auto('data/raw/delivery_partners.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW orders AS SELECT * FROM read_csv_auto('data/raw/orders.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW order_financials AS SELECT * FROM read_csv_auto('data/raw/order_financials.csv', HEADER = TRUE);

-- ===========================================================================
-- Analysis 1: What is the current marketplace scale and health by market?
-- ===========================================================================
-- Business question:
-- Which markets have the greatest order scale, user engagement, and delivery
-- success, and are differences driven by volume or operating health?
--
-- Metric definition:
-- delivered_rate = delivered orders / all orders
-- cancellation_rate = cancelled orders / all orders
-- orders_per_active_user = all orders / distinct ordering users
-- average_order_value = average total_paid per order
--
-- Grain:
-- One row per market.

WITH market_orders AS (
    SELECT
        market_id,
        COUNT(*) AS orders,
        COUNT(DISTINCT user_id) AS active_users,
        COUNT(*) FILTER (WHERE order_status = 'DELIVERED') AS delivered_orders,
        COUNT(*) FILTER (WHERE order_status = 'CANCELLED') AS cancelled_orders,
        AVG(total_paid) AS average_order_value
    FROM orders
    GROUP BY market_id
)
SELECT
    m.country,
    mo.orders,
    mo.active_users,
    ROUND(mo.orders * 1.0 / NULLIF(mo.active_users, 0), 2) AS orders_per_active_user,
    ROUND(mo.delivered_orders * 100.0 / mo.orders, 2) AS delivered_rate_pct,
    ROUND(mo.cancelled_orders * 100.0 / mo.orders, 2) AS cancellation_rate_pct,
    ROUND(mo.average_order_value, 2) AS average_order_value
FROM market_orders mo
JOIN markets m USING (market_id)
ORDER BY mo.orders DESC;

-- Observed result from the generated CSVs:
-- India: 346,818 orders, 9.54 orders per active user, 95.39% delivered,
-- 4.61% cancelled.
-- USA: 46,958 orders, 8.47 orders per active user, 95.46% delivered,
-- 4.54% cancelled.
-- Australia: 8,521 orders, 6.81 orders per active user, 95.65% delivered,
-- 4.35% cancelled.
-- UK: 29,326 orders, 8.29 orders per active user, 95.80% delivered,
-- 4.20% cancelled.
-- Japan: 68,377 orders, 8.56 orders per active user, 95.49% delivered,
-- 4.51% cancelled.
-- Interpretation:
-- India dominates absolute volume, but operational success rates are close across
-- markets. Australia has the lowest orders per active user, so scale alone should
-- not be treated as evidence of stronger marketplace health.

-- ===========================================================================
-- Analysis 2: Is marketplace volume growing consistently through the period?
-- ===========================================================================
-- Business question:
-- Do markets show sustained monthly order growth, or is volume concentrated in
-- isolated periods?
--
-- Metric definition:
-- monthly_orders = orders grouped by market and calendar month
-- first_month_orders and last_month_orders = endpoint comparison for the
-- generated time range
-- endpoint_growth_pct = (last month - first month) / first month
--
-- Grain:
-- One row per market and month, followed by a market-level endpoint comparison.

WITH monthly_orders AS (
    SELECT
        market_id,
        DATE_TRUNC('month', order_timestamp) AS order_month,
        COUNT(*) AS monthly_orders
    FROM orders
    GROUP BY market_id, DATE_TRUNC('month', order_timestamp)
), endpoints AS (
    SELECT
        market_id,
        FIRST_VALUE(monthly_orders) OVER (
            PARTITION BY market_id ORDER BY order_month
        ) AS first_month_orders,
        LAST_VALUE(monthly_orders) OVER (
            PARTITION BY market_id ORDER BY order_month
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS last_month_orders
    FROM monthly_orders
)
SELECT DISTINCT
    m.country,
    first_month_orders,
    last_month_orders,
    ROUND((last_month_orders - first_month_orders) * 100.0 / NULLIF(first_month_orders, 0), 2) AS endpoint_growth_pct
FROM endpoints e
JOIN markets m USING (market_id)
ORDER BY endpoint_growth_pct DESC;

-- Observed result from the generated CSVs:
-- Endpoint monthly volume increased in every market. The approximate endpoint
-- increases were India 18,148%, USA 19,727%, Australia 15,233%, UK 22,783%,
-- and Japan 18,409%.
-- Interpretation:
-- The dataset contains a strong generated time ramp, so monthly growth should be
-- used for SQL practice and comparative trend analysis, not treated as a causal
-- historical Uber Eats growth estimate.

-- ===========================================================================
-- Analysis 3: Which cities have the strongest marketplace engagement?
-- ===========================================================================
-- Business question:
-- Which city markets convert active users into repeated order activity most
-- effectively?
--
-- Metric definition:
-- active_users = distinct users ordering in the city
-- orders_per_active_user = city orders / city active users
-- delivered_rate = delivered city orders / all city orders
--
-- Grain:
-- One row per city.

WITH city_health AS (
    SELECT
        o.city_id,
        COUNT(*) AS orders,
        COUNT(DISTINCT o.user_id) AS active_users,
        COUNT(*) FILTER (WHERE o.order_status = 'DELIVERED') AS delivered_orders,
        COUNT(*) FILTER (WHERE o.order_status = 'CANCELLED') AS cancelled_orders
    FROM orders o
    GROUP BY o.city_id
)
SELECT
    c.city_name,
    m.country,
    ch.orders,
    ch.active_users,
    ROUND(ch.orders * 1.0 / NULLIF(ch.active_users, 0), 2) AS orders_per_active_user,
    ROUND(ch.delivered_orders * 100.0 / ch.orders, 2) AS delivered_rate_pct,
    ROUND(ch.cancelled_orders * 100.0 / ch.orders, 2) AS cancellation_rate_pct
FROM city_health ch
JOIN cities c USING (city_id)
JOIN markets m USING (market_id)
ORDER BY orders_per_active_user DESC;

-- Observed result from the generated CSVs:
-- The five highest cities by orders per active user were Mumbai 10.20, Delhi
-- 9.69, Kolkata 9.51, Tokyo 9.42, and New York 9.29.
-- Interpretation:
-- City-level engagement differs inside and across markets. This supports city-
-- first investigation rather than using only country-level averages.

-- ===========================================================================
-- Analysis 4: Does supply keep pace with city demand?
-- ===========================================================================
-- Business question:
-- Are cities with high demand supported by enough restaurants and delivery
-- partners?
--
-- Metric definition:
-- restaurants_per_1k_active_users = restaurants / active users * 1,000
-- partners_per_1k_active_users = partners / active users * 1,000
-- orders_per_restaurant = orders / restaurants
-- orders_per_partner = orders / partners
--
-- Grain:
-- One row per city. Supply counts are dimensions; order counts are facts.

WITH city_orders AS (
    SELECT city_id, COUNT(*) AS orders, COUNT(DISTINCT user_id) AS active_users
    FROM orders
    GROUP BY city_id
), city_restaurants AS (
    SELECT city_id, COUNT(*) AS restaurants
    FROM restaurants
    GROUP BY city_id
), city_partners AS (
    SELECT city_id, COUNT(*) AS partners
    FROM delivery_partners
    GROUP BY city_id
)
SELECT
    c.city_name,
    m.country,
    co.orders,
    co.active_users,
    cr.restaurants,
    cp.partners,
    ROUND(cr.restaurants * 1000.0 / NULLIF(co.active_users, 0), 2) AS restaurants_per_1k_active_users,
    ROUND(cp.partners * 1000.0 / NULLIF(co.active_users, 0), 2) AS partners_per_1k_active_users,
    ROUND(co.orders * 1.0 / NULLIF(cr.restaurants, 0), 2) AS orders_per_restaurant,
    ROUND(co.orders * 1.0 / NULLIF(cp.partners, 0), 2) AS orders_per_partner
FROM city_orders co
JOIN city_restaurants cr USING (city_id)
JOIN city_partners cp USING (city_id)
JOIN cities c USING (city_id)
JOIN markets m USING (market_id)
ORDER BY co.orders DESC;

-- Observed result from the generated CSVs:
-- The highest-volume cities are not identical to the cities with the highest
-- supply ratios. Mumbai has 117,512 orders and 61.14 orders per restaurant,
-- while the generated supply structure varies materially by city.
-- Interpretation:
-- This is the base table for diagnosing supply-demand imbalance. A high
-- orders-per-restaurant or orders-per-partner value is a signal for deeper
-- operational analysis, not proof of a marketplace constraint by itself.

-- ===========================================================================
-- Analysis 5: How concentrated is restaurant demand?
-- ===========================================================================
-- Business question:
-- Does the marketplace depend on a small number of restaurants, or is order
-- demand distributed broadly across the supply base?
--
-- Metric definition:
-- top_10_share = orders from the ten highest-volume restaurants / all orders
-- restaurant_median_orders = median order count among restaurants with orders
--
-- Grain:
-- One row for the marketplace-wide concentration summary.

WITH restaurant_orders AS (
    SELECT restaurant_id, COUNT(*) AS orders
    FROM orders
    GROUP BY restaurant_id
), ranked AS (
    SELECT
        restaurant_id,
        orders,
        ROW_NUMBER() OVER (ORDER BY orders DESC, restaurant_id) AS volume_rank
    FROM restaurant_orders
), totals AS (
    SELECT SUM(orders) AS total_orders FROM restaurant_orders
)
SELECT
    ROUND(SUM(r.orders) FILTER (WHERE r.volume_rank <= 10) * 100.0 / CAST(MAX(t.total_orders) AS DOUBLE), 2) AS top_10_restaurant_order_share_pct,
    MEDIAN(r.orders) AS restaurant_median_orders,
    COUNT(*) AS ordering_restaurant_count
FROM ranked r
CROSS JOIN totals t;

-- Observed result from the generated CSVs:
-- The top ten restaurants account for approximately 1.91% of all orders, and
-- the median ordering restaurant has 21 orders.
-- Interpretation:
-- Demand is broad rather than dominated by a tiny group of restaurants in this
-- generated dataset. This weakens a simple concentration explanation for market
-- differences, while still allowing city- and cuisine-level analysis later.

-- ===========================================================================
-- Analysis 6: Which markets combine order scale with positive economics?
-- ===========================================================================
-- Business question:
-- Do the markets producing more orders also produce stronger contribution
-- margins?
--
-- Metric definition:
-- contribution_margin_per_order = average order contribution margin
-- negative_margin_share = negative-margin orders / all orders
-- total_contribution_margin = sum of order contribution margin
--
-- Grain:
-- One row per market. Financials are joined one-to-one by order_id.

SELECT
    m.country,
    COUNT(*) AS orders,
    ROUND(SUM(f.contribution_margin), 2) AS total_contribution_margin,
    ROUND(AVG(f.contribution_margin), 2) AS contribution_margin_per_order,
    ROUND(COUNT(*) FILTER (WHERE f.contribution_margin < 0) * 100.0 / COUNT(*), 2) AS negative_margin_share_pct
FROM orders o
JOIN order_financials f USING (order_id)
JOIN markets m USING (market_id)
GROUP BY m.country
ORDER BY total_contribution_margin DESC;

-- Observed result from the generated CSVs:
-- All markets have negative average contribution margin per order. India has the
-- largest absolute margin loss because it has the largest order volume, while
-- Australia has the least negative average margin per order among the markets.
-- Interpretation:
-- Scale and unit economics are not equivalent. This result motivates a later
-- decomposition into delivery partner cost, promotion cost, basket economics,
-- and support cost rather than treating order volume as sustainable scale.

-- ===========================================================================
-- Analysis 7: Marketplace health scorecard for prioritization
-- ===========================================================================
-- Business question:
-- Which markets should be prioritized for deeper product and marketplace RCA?
--
-- Metric definition:
-- The scorecard presents scale, engagement, reliability, supply, and economics
-- side by side. It is intentionally descriptive rather than a hard-coded score.
--
-- Grain:
-- One row per market.

WITH market_orders AS (
    SELECT
        market_id,
        COUNT(*) AS orders,
        COUNT(DISTINCT user_id) AS active_users,
        COUNT(*) FILTER (WHERE order_status = 'DELIVERED') AS delivered_orders,
        COUNT(*) FILTER (WHERE order_status = 'CANCELLED') AS cancelled_orders
    FROM orders
    GROUP BY market_id
), market_supply AS (
    SELECT
        market_id,
        COUNT(*) AS restaurants
    FROM restaurants
    GROUP BY market_id
), market_finance AS (
    SELECT
        o.market_id,
        AVG(f.contribution_margin) AS contribution_margin_per_order,
        COUNT(*) FILTER (WHERE f.contribution_margin < 0) * 1.0 / COUNT(*) AS negative_margin_share
    FROM orders o
    JOIN order_financials f USING (order_id)
    GROUP BY o.market_id
)
SELECT
    m.country,
    mo.orders,
    ROUND(mo.orders * 1.0 / mo.active_users, 2) AS orders_per_active_user,
    ROUND(mo.delivered_orders * 100.0 / mo.orders, 2) AS delivered_rate_pct,
    ROUND(mo.cancelled_orders * 100.0 / mo.orders, 2) AS cancellation_rate_pct,
    ms.restaurants,
    ROUND(mf.contribution_margin_per_order, 2) AS contribution_margin_per_order,
    ROUND(mf.negative_margin_share * 100, 2) AS negative_margin_share_pct
FROM market_orders mo
JOIN market_supply ms USING (market_id)
JOIN market_finance mf USING (market_id)
JOIN markets m USING (market_id)
ORDER BY mo.orders DESC;

-- Observed result from the generated CSVs:
-- India leads absolute orders and active users, but market-level delivered and
-- cancellation rates are tightly clustered. Australia has lower volume and lower
-- order frequency per active user, while all markets show negative average margin.
-- Interpretation:
-- No single score should declare a winner. The next investigation should explain
-- whether differences are driven by retention, delivery reliability, supply
-- liquidity, or cost structure.

-- End of marketplace-health analysis. Later files should cover customer behavior,
-- restaurant performance, delivery operations, customer experience, promotions,
-- cohorts, and root-cause analysis separately.
