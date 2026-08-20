-- Restaurant Performance Analysis
-- Dialect: DuckDB
-- Scope: restaurant demand, completion/cancellation, ratings, cuisine,
-- price bands, concentration, and actionable performance segments.
-- Delivery-event root cause analysis belongs in a later delivery module.

CREATE OR REPLACE VIEW restaurants AS SELECT * FROM read_csv_auto('data/raw/restaurants.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW orders AS SELECT * FROM read_csv_auto('data/raw/orders.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW ratings AS SELECT * FROM read_csv_auto('data/raw/ratings.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW order_financials AS SELECT * FROM read_csv_auto('data/raw/order_financials.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW cities AS SELECT * FROM read_csv_auto('data/raw/cities.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW markets AS SELECT * FROM read_csv_auto('data/raw/markets.csv', HEADER = TRUE);

-- ===========================================================================
-- Analysis 1: How is restaurant demand distributed?
-- ===========================================================================
-- Business question:
-- Is demand broadly distributed across restaurants, or concentrated among a
-- small set of high-volume restaurants?
--
-- Metric definition:
-- restaurant_orders = total orders per restaurant
-- top_10_share = orders from the ten highest-volume restaurants / all orders
-- ordering_restaurant_rate = restaurants with >=1 order / all restaurants
--
-- Grain:
-- One row per restaurant in the first CTE, then one marketplace summary row.

WITH restaurant_orders AS (
    SELECT
        r.restaurant_id,
        r.restaurant_name,
        r.cuisine_type,
        r.price_band,
        COUNT(o.order_id) AS orders
    FROM restaurants r
    LEFT JOIN orders o USING (restaurant_id)
    GROUP BY r.restaurant_id, r.restaurant_name, r.cuisine_type, r.price_band
), ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (ORDER BY orders DESC, restaurant_id) AS volume_rank
    FROM restaurant_orders
)
SELECT
    COUNT(*) AS restaurants,
    COUNT(*) FILTER (WHERE orders > 0) AS ordering_restaurants,
    COUNT(*) FILTER (WHERE orders = 0) AS zero_order_restaurants,
    ROUND(COUNT(*) FILTER (WHERE orders > 0) * 100.0 / COUNT(*), 2) AS ordering_restaurant_rate_pct,
    ROUND(SUM(orders) FILTER (WHERE volume_rank <= 10) * 100.0 / SUM(orders), 2) AS top_10_order_share_pct,
    MEDIAN(orders) AS median_orders_per_restaurant,
    MAX(orders) AS maximum_orders_per_restaurant
FROM ranked;

-- Observed result from the generated CSVs:
-- 11,852 of 12,000 restaurants have orders; 148 have zero orders. The top ten
-- account for 1.91% of orders, the median restaurant has 21 orders, and the
-- highest-volume restaurant has 1,453 orders.
-- Interpretation:
-- Demand is heavy-tailed but not dominated by a tiny restaurant set. The zero-
-- order supply tail is more material than top-ten concentration and is a useful
-- marketplace-liquidity investigation target.

-- ===========================================================================
-- Analysis 2: Which restaurants have strong completion or cancellation rates?
-- ===========================================================================
-- Business question:
-- Which restaurants combine meaningful order volume with reliable completion,
-- and which show cancellation risk?
--
-- Metric definition:
-- completion_rate = DELIVERED orders / all restaurant orders
-- cancellation_rate = CANCELLED orders / all restaurant orders
-- Minimum volume threshold: 20 orders, chosen to avoid unstable one-order rates.
--
-- Grain:
-- One row per restaurant with >=20 orders.

WITH restaurant_performance AS (
    SELECT
        r.restaurant_id,
        r.restaurant_name,
        r.cuisine_type,
        r.price_band,
        COUNT(o.order_id) AS orders,
        COUNT(*) FILTER (WHERE o.order_status = 'DELIVERED') AS delivered_orders,
        COUNT(*) FILTER (WHERE o.order_status = 'CANCELLED') AS cancelled_orders,
        AVG(o.total_paid) AS average_order_value
    FROM restaurants r
    JOIN orders o USING (restaurant_id)
    GROUP BY r.restaurant_id, r.restaurant_name, r.cuisine_type, r.price_band
)
SELECT
    restaurant_id,
    restaurant_name,
    cuisine_type,
    price_band,
    orders,
    ROUND(delivered_orders * 100.0 / orders, 2) AS completion_rate_pct,
    ROUND(cancelled_orders * 100.0 / orders, 2) AS cancellation_rate_pct,
    ROUND(average_order_value, 2) AS average_order_value
FROM restaurant_performance
WHERE orders >= 20
ORDER BY cancellation_rate_pct DESC, orders DESC;

-- Observed result from the generated CSVs:
-- Overall restaurant cancellation rates are close to the marketplace baseline,
-- but some restaurants with at least 20 orders show cancellation rates above 20%.
-- The highest observed examples include Kolkata Fast Food at 28.57% and
-- Hyderabad North Indian at 23.81%.
-- Interpretation:
-- Restaurant-level reliability is heterogeneous even when aggregate completion
-- rates look stable. High-volume filtering is necessary before prioritizing an
-- operational intervention.

-- ===========================================================================
-- Analysis 3: Does restaurant rating align with demand and reliability?
-- ===========================================================================
-- Business question:
-- Are highly rated restaurants attracting more orders or completing more orders?
--
-- Metric definition:
-- submitted_rating = average of rows in ratings, not restaurants.restaurant_rating
-- rating_coverage = submitted ratings / delivered orders
-- Restaurant-level rating analysis requires a minimum of 20 submitted ratings.
--
-- Grain:
-- One row per restaurant with sufficient submitted ratings.

WITH restaurant_orders AS (
    SELECT
        restaurant_id,
        COUNT(*) AS orders,
        COUNT(*) FILTER (WHERE order_status = 'DELIVERED') AS delivered_orders,
        COUNT(*) FILTER (WHERE order_status = 'CANCELLED') AS cancelled_orders
    FROM orders
    GROUP BY restaurant_id
), restaurant_ratings AS (
    SELECT
        restaurant_id,
        COUNT(*) AS rating_count,
        AVG(rating) AS average_submitted_rating
    FROM ratings
    GROUP BY restaurant_id
)
SELECT
    r.restaurant_id,
    r.restaurant_name,
    rr.rating_count,
    ROUND(rr.average_submitted_rating, 2) AS average_submitted_rating,
    ro.orders,
    ROUND(ro.delivered_orders * 100.0 / ro.orders, 2) AS completion_rate_pct,
    ROUND(ro.cancelled_orders * 100.0 / ro.orders, 2) AS cancellation_rate_pct
FROM restaurants r
JOIN restaurant_orders ro USING (restaurant_id)
JOIN restaurant_ratings rr USING (restaurant_id)
WHERE rr.rating_count >= 20
ORDER BY average_submitted_rating DESC, rating_count DESC;

-- Observed result from the generated CSVs:
-- 249,902 ratings cover approximately 52.37% of delivered orders. Across
-- restaurants with ratings, the average submitted rating is approximately 4.10.
-- Among restaurants with at least 20 ratings, observed averages reach about
-- 4.50, but rating coverage is not universal.
-- Interpretation:
-- Ratings are useful for quality segmentation but should not be treated as a
-- complete restaurant-quality measure. The minimum-rating threshold reduces
-- small-sample noise.

-- ===========================================================================
-- Analysis 4: Which cuisines generate demand and reliable completion?
-- ===========================================================================
-- Business question:
-- Do cuisine categories differ in demand, restaurant productivity, order value,
-- or cancellation performance?
--
-- Metric definition:
-- orders = total orders for the cuisine
-- orders_per_restaurant = cuisine orders / restaurants offering the cuisine
-- weighted_completion_rate = delivered orders / all cuisine orders
-- average_order_value = average total_paid for cuisine orders
--
-- Grain:
-- One row per cuisine type.

WITH cuisine_supply AS (
    SELECT cuisine_type, COUNT(*) AS restaurants
    FROM restaurants
    GROUP BY cuisine_type
), cuisine_orders AS (
    SELECT
        r.cuisine_type,
        COUNT(*) AS orders,
        COUNT(*) FILTER (WHERE o.order_status = 'DELIVERED') AS delivered_orders,
        COUNT(*) FILTER (WHERE o.order_status = 'CANCELLED') AS cancelled_orders,
        AVG(o.total_paid) AS average_order_value
    FROM orders o
    JOIN restaurants r USING (restaurant_id)
    GROUP BY r.cuisine_type
)
SELECT
    co.cuisine_type,
    cs.restaurants,
    co.orders,
    ROUND(co.orders * 1.0 / cs.restaurants, 2) AS orders_per_restaurant,
    ROUND(co.delivered_orders * 100.0 / co.orders, 2) AS completion_rate_pct,
    ROUND(co.cancelled_orders * 100.0 / co.orders, 2) AS cancellation_rate_pct,
    ROUND(co.average_order_value, 2) AS average_order_value
FROM cuisine_orders co
JOIN cuisine_supply cs USING (cuisine_type)
ORDER BY orders DESC;

-- Observed result from the generated CSVs:
-- FAST_FOOD generated 73,986 orders and CHINESE generated 73,899, the highest
-- cuisine totals. JAPANESE had the highest average order value among major
-- categories at approximately 29.43, while cuisine completion rates remained
-- close to 95% overall.
-- Interpretation:
-- Cuisine demand differences are mainly volume and basket-size signals here;
-- completion-rate differences are comparatively small and should not be used as
-- a root cause without delivery or availability analysis.

-- ===========================================================================
-- Analysis 5: How does price band affect demand and basket economics?
-- ===========================================================================
-- Business question:
-- Do premium restaurants produce higher order values, and does that come with
-- different completion or cancellation behavior?
--
-- Metric definition:
-- orders_per_restaurant = orders / restaurants in the price band
-- average_order_value = average total_paid
-- cancellation_rate = cancelled orders / all orders
--
-- Grain:
-- One row per price band.

WITH band_supply AS (
    SELECT price_band, COUNT(*) AS restaurants
    FROM restaurants
    GROUP BY price_band
), band_orders AS (
    SELECT
        r.price_band,
        COUNT(*) AS orders,
        COUNT(*) FILTER (WHERE o.order_status = 'DELIVERED') AS delivered_orders,
        COUNT(*) FILTER (WHERE o.order_status = 'CANCELLED') AS cancelled_orders,
        AVG(o.total_paid) AS average_order_value
    FROM orders o
    JOIN restaurants r USING (restaurant_id)
    GROUP BY r.price_band
)
SELECT
    bo.price_band,
    bs.restaurants,
    bo.orders,
    ROUND(bo.orders * 1.0 / bs.restaurants, 2) AS orders_per_restaurant,
    ROUND(bo.average_order_value, 2) AS average_order_value,
    ROUND(bo.delivered_orders * 100.0 / bo.orders, 2) AS completion_rate_pct,
    ROUND(bo.cancelled_orders * 100.0 / bo.orders, 2) AS cancellation_rate_pct
FROM band_orders bo
JOIN band_supply bs USING (price_band)
ORDER BY bo.average_order_value DESC;

-- Observed result from the generated CSVs:
-- PREMIUM has the highest average order value at approximately 50.79, followed
-- by HIGH at 35.33, MEDIUM at 24.94, and LOW at 19.14. PREMIUM also has the
-- highest cancellation rate at approximately 4.99%, versus about 4.43%-4.57%
-- for the other bands.
-- Interpretation:
-- Premium restaurants increase basket value but do not automatically improve
-- operating reliability. This creates a useful product question around whether
-- higher-value orders require different service expectations or operations.

-- ===========================================================================
-- Analysis 6: Which restaurants are meaningful high- and low-performers?
-- ===========================================================================
-- Business question:
-- Which restaurants should be prioritized for growth support, operational
-- intervention, or deeper investigation?
--
-- Metric definition:
-- HIGH_VOLUME = restaurant order count >= the observed 90th percentile
-- LOW_VOLUME = restaurant order count between 1 and the observed median
-- HIGH_CANCELLATION = at least 20 orders and cancellation rate above 10%
-- HIGH_VALUE_RELIABLE = at least 50 orders, completion >= 96%, and average
-- total_paid above the restaurant median among qualifying restaurants
--
-- Grain:
-- One row per restaurant segment.

WITH restaurant_metrics AS (
    SELECT
        r.restaurant_id,
        r.restaurant_name,
        r.cuisine_type,
        r.price_band,
        COUNT(o.order_id) AS orders,
        COUNT(*) FILTER (WHERE o.order_status = 'DELIVERED') AS delivered_orders,
        COUNT(*) FILTER (WHERE o.order_status = 'CANCELLED') AS cancelled_orders,
        AVG(o.total_paid) AS average_order_value
    FROM restaurants r
    LEFT JOIN orders o USING (restaurant_id)
    GROUP BY r.restaurant_id, r.restaurant_name, r.cuisine_type, r.price_band
), thresholds AS (
    SELECT
        QUANTILE_CONT(orders, 0.50) AS median_orders,
        QUANTILE_CONT(orders, 0.90) AS p90_orders,
        QUANTILE_CONT(average_order_value, 0.50) FILTER (WHERE orders >= 50) AS median_value_50_plus
    FROM restaurant_metrics
)
SELECT
    CASE
        WHEN rm.orders = 0 THEN 'ZERO_ORDER_SUPPLY'
        WHEN rm.orders >= t.p90_orders AND rm.cancelled_orders * 1.0 / rm.orders <= 0.05 THEN 'HIGH_VOLUME_STABLE'
        WHEN rm.orders >= 20 AND rm.cancelled_orders * 1.0 / rm.orders > 0.10 THEN 'HIGH_CANCELLATION'
        WHEN rm.orders BETWEEN 1 AND t.median_orders THEN 'LOW_VOLUME'
        WHEN rm.orders >= 50
             AND rm.delivered_orders * 1.0 / rm.orders >= 0.96
             AND rm.average_order_value >= t.median_value_50_plus THEN 'HIGH_VALUE_RELIABLE'
        ELSE 'CORE_MID_TIER'
    END AS restaurant_segment,
    COUNT(*) AS restaurants,
    SUM(rm.orders) AS orders,
    ROUND(AVG(rm.orders), 2) AS average_orders_per_restaurant,
    ROUND(AVG(rm.cancelled_orders * 100.0 / NULLIF(rm.orders, 0)), 2) AS average_cancellation_rate_pct
FROM restaurant_metrics rm
CROSS JOIN thresholds t
GROUP BY restaurant_segment
ORDER BY restaurants DESC;

-- Observed result from the generated CSVs:
-- The generated restaurant population contains 148 zero-order restaurants and a
-- broad core/mid-tier. High-cancellation examples exist even above the 20-order
-- threshold, while the top demand restaurants remain a small share of total
-- orders.
-- Interpretation:
-- This segmentation supports different interventions: discoverability or
-- onboarding support for zero/low-volume supply, operational investigation for
-- high-cancellation restaurants, and retention or merchandising support for
-- high-volume stable restaurants. The thresholds are explicit and query-visible,
-- not hidden assumptions.

-- End of restaurant-performance analysis. Delivery-event root cause, issue
-- drivers, and peak-hour operational degradation belong in the delivery module.
