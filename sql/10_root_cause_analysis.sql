-- Product Root-Cause Analysis
-- Dialect: DuckDB
-- Scope: evidence-based RCA investigations combining prior themes.
-- These are associations and diagnostic decompositions, not causal estimates.

CREATE OR REPLACE VIEW orders AS SELECT * FROM read_csv_auto('data/raw/orders.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW delivery_events AS SELECT * FROM read_csv_auto('data/raw/delivery_events.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW ratings AS SELECT * FROM read_csv_auto('data/raw/ratings.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW order_issues AS SELECT * FROM read_csv_auto('data/raw/order_issues.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW order_promotions AS SELECT * FROM read_csv_auto('data/raw/order_promotions.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW order_financials AS SELECT * FROM read_csv_auto('data/raw/order_financials.csv', HEADER = TRUE);

-- ===========================================================================
-- RCA 1: Is delivery reliability associated with customer sentiment and repeat?
-- ===========================================================================
-- Business question:
-- Are late first-order deliveries associated with lower ratings or weaker
-- 90-day repeat behavior?
--
-- Metric definition:
-- Rating comparison: average rating for late versus on-time/early delivered
-- orders.
-- Repeat comparison: whether a user's next delivered order occurs within 90 days
-- of their first delivered order, segmented by whether that first order was late.
--
-- Grain: one row per comparison group.

WITH delivered AS (
    SELECT
        order_id,
        user_id,
        order_timestamp,
        promised_delivery_timestamp,
        actual_delivery_timestamp,
        actual_delivery_timestamp > promised_delivery_timestamp AS is_late,
        ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_timestamp, order_id) AS order_number
    FROM orders
    WHERE order_status = 'DELIVERED'
), ratings_by_order AS (
    SELECT order_id, AVG(rating) AS rating
    FROM ratings
    GROUP BY order_id
), first_orders AS (
    SELECT *
    FROM delivered
    WHERE order_number = 1
), repeat_flags AS (
    SELECT
        f.user_id,
        f.is_late,
        MAX(CASE WHEN d.order_timestamp > f.order_timestamp
                  AND d.order_timestamp <= f.order_timestamp + INTERVAL 90 DAY THEN 1 ELSE 0 END) AS repeated_90d
    FROM first_orders f
    LEFT JOIN delivered d ON f.user_id = d.user_id
    GROUP BY f.user_id, f.is_late
), rating_summary AS (
    SELECT
        d.is_late,
        AVG(r.rating) AS average_rating,
        COUNT(*) AS rated_orders
    FROM delivered d
    JOIN ratings_by_order r USING (order_id)
    GROUP BY d.is_late
), repeat_summary AS (
    SELECT
        is_late,
        AVG(repeated_90d) AS repeat_90d_rate,
        COUNT(*) AS first_order_users
    FROM repeat_flags
    GROUP BY is_late
)
SELECT
    CASE WHEN rs.is_late THEN 'LATE' ELSE 'ON_TIME_OR_EARLY' END AS delivery_group,
    rs.rated_orders,
    ROUND(rs.average_rating, 2) AS average_rating,
    ROUND(ps.repeat_90d_rate * 100, 2) AS repeat_90d_rate_pct,
    ps.first_order_users
FROM rating_summary rs
JOIN repeat_summary ps USING (is_late)
ORDER BY delivery_group;

-- Observed result: late delivered orders average approximately 3.97 versus 4.33
-- for on-time/early orders. First-order lateness has almost no observed 90-day
-- repeat difference in this generated data, approximately 83.95% versus 83.98%.
-- Interpretation: delivery reliability is strongly associated with sentiment but
-- not measurably associated with repeat in this aggregate cohort test. The next
-- product question is whether lateness affects lower-frequency users or specific
-- cities rather than all customers equally.

-- ===========================================================================
-- RCA 2: Are promotions associated with weaker unit economics?
-- ===========================================================================
-- Business question:
-- Does the promotion flag correspond to lower contribution margin and higher
-- negative-margin share?
--
-- Metric definition:
-- promoted_order = order with at least one redemption
-- Compare average contribution margin, negative-margin share, and promotion cost.
--
-- Grain: one row per promoted/organic order group.

WITH order_promo_flags AS (
    SELECT
        o.order_id,
        CASE WHEN COUNT(op.promotion_id) > 0 THEN 'PROMOTED' ELSE 'ORGANIC' END AS order_group
    FROM orders o
    LEFT JOIN order_promotions op USING (order_id)
    GROUP BY o.order_id
)
SELECT
    p.order_group,
    COUNT(*) AS orders,
    ROUND(AVG(f.contribution_margin), 2) AS average_contribution_margin,
    ROUND(COUNT(*) FILTER (WHERE f.contribution_margin < 0) * 100.0 / COUNT(*), 2) AS negative_margin_share_pct,
    ROUND(AVG(f.promotion_cost), 2) AS average_promotion_cost
FROM order_promo_flags p
JOIN order_financials f USING (order_id)
GROUP BY p.order_group;

-- Observed result: promoted orders average approximately -11.12 contribution
-- margin versus -8.38 for organic orders. The generated data therefore shows a
-- clear descriptive promotion-margin gap.
-- Interpretation: promotions are a plausible economics pressure point, but this
-- does not prove that discounts cause the gap. User mix, basket value, market,
-- and order context should be controlled before a product recommendation.

-- ===========================================================================
-- RCA 3: Is preparation time the primary measured delivery bottleneck?
-- ===========================================================================
-- Business question:
-- Does the delivery lifecycle spend more time before pickup, during assignment,
-- or after pickup?
--
-- Metric definition:
-- preparation_minutes = pickup - restaurant accepted
-- assignment_minutes = partner assigned - partner requested
-- travel_minutes = delivered - pickup
-- Restrict to delivered orders with all required events.
--
-- Grain: one row for the complete-lifecycle comparison.

WITH event_times AS (
    SELECT
        order_id,
        MIN(event_timestamp) FILTER (WHERE event_type = 'RESTAURANT_ACCEPTED') AS accepted_at,
        MIN(event_timestamp) FILTER (WHERE event_type = 'PARTNER_REQUESTED') AS requested_at,
        MIN(event_timestamp) FILTER (WHERE event_type = 'PARTNER_ASSIGNED') AS assigned_at,
        MIN(event_timestamp) FILTER (WHERE event_type = 'ORDER_PICKED_UP') AS picked_up_at,
        MIN(event_timestamp) FILTER (WHERE event_type = 'ORDER_DELIVERED') AS delivered_at
    FROM delivery_events
    GROUP BY order_id
)
SELECT
    COUNT(*) AS complete_delivered_orders,
    ROUND(AVG(DATE_DIFF('minute', accepted_at, picked_up_at)), 2) AS average_preparation_minutes,
    ROUND(AVG(DATE_DIFF('minute', requested_at, assigned_at)), 2) AS average_assignment_minutes,
    ROUND(AVG(DATE_DIFF('minute', picked_up_at, delivered_at)), 2) AS average_travel_minutes
FROM event_times e
JOIN orders o USING (order_id)
WHERE o.order_status = 'DELIVERED'
  AND accepted_at IS NOT NULL
  AND requested_at IS NOT NULL
  AND assigned_at IS NOT NULL
  AND picked_up_at IS NOT NULL
  AND delivered_at IS NOT NULL;

-- Observed result: preparation-to-pickup averages approximately 25.2 minutes,
-- assignment approximately 6.1 minutes, and travel approximately 4.8 minutes.
-- Interpretation: preparation is the largest measured lifecycle component, making
-- restaurant readiness a stronger initial bottleneck hypothesis than travel time.
-- This remains a diagnostic association and should be segmented by city, cuisine,
-- peak window, and restaurant before intervention.

-- End of final RCA module. All interpretations distinguish observed associations
-- from hypotheses and avoid causal claims.
