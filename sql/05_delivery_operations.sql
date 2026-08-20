-- Delivery Operations Analysis
-- Dialect: DuckDB
-- Scope: delivery duration, ETA error, peak degradation, assignment coverage,
-- and restaurant preparation versus travel bottlenecks.

CREATE OR REPLACE VIEW orders AS SELECT * FROM read_csv_auto('data/raw/orders.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW delivery_events AS SELECT * FROM read_csv_auto('data/raw/delivery_events.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW restaurant_availability AS SELECT * FROM read_csv_auto('data/raw/restaurant_availability.csv', HEADER = TRUE);

-- ===========================================================================
-- Analysis 1: How long do delivered orders take, and how accurate is the ETA?
-- ===========================================================================
-- Business question:
-- What is the delivered-order duration and how often does the actual delivery
-- miss the promised timestamp?
--
-- Metric definition:
-- delivery_minutes = actual delivery - order timestamp
-- eta_error_minutes = actual delivery - promised delivery
-- late_rate = orders with eta_error > 0 / delivered orders
--
-- Grain: one row for the delivered-order summary.

SELECT
    COUNT(*) AS delivered_orders,
    ROUND(AVG(DATE_DIFF('minute', order_timestamp, actual_delivery_timestamp)), 2) AS average_delivery_minutes,
    MEDIAN(DATE_DIFF('minute', order_timestamp, actual_delivery_timestamp)) AS median_delivery_minutes,
    ROUND(AVG(DATE_DIFF('minute', promised_delivery_timestamp, actual_delivery_timestamp)), 2) AS average_eta_error_minutes,
    ROUND(COUNT(*) FILTER (WHERE actual_delivery_timestamp > promised_delivery_timestamp) * 100.0 / COUNT(*), 2) AS late_rate_pct
FROM orders
WHERE order_status = 'DELIVERED';

-- Observed result: average delivery duration is approximately 34.1 minutes,
-- average ETA error is 3.6 minutes, and 64.8% of delivered orders are late.
-- Interpretation: lateness is common enough to be a customer-experience driver,
-- even though the average ETA error is relatively small.

-- ===========================================================================
-- Analysis 2: Does peak demand degrade delivery performance?
-- ===========================================================================
-- Business question:
-- Are lunch and dinner order windows slower or less reliable than non-peak
-- windows?
--
-- Metric definition:
-- peak_window = hours 11-14 or 18-21
-- Compare delivery duration, ETA error, and late rate by peak flag.
--
-- Grain: one row per peak/non-peak group.

WITH delivered AS (
    SELECT
        *,
        CASE WHEN EXTRACT(HOUR FROM order_timestamp) BETWEEN 11 AND 14
                  OR EXTRACT(HOUR FROM order_timestamp) BETWEEN 18 AND 21
             THEN 'PEAK' ELSE 'NON_PEAK' END AS demand_window
    FROM orders
    WHERE order_status = 'DELIVERED'
)
SELECT
    demand_window,
    COUNT(*) AS delivered_orders,
    ROUND(AVG(DATE_DIFF('minute', order_timestamp, actual_delivery_timestamp)), 2) AS average_delivery_minutes,
    ROUND(AVG(DATE_DIFF('minute', promised_delivery_timestamp, actual_delivery_timestamp)), 2) AS average_eta_error_minutes,
    ROUND(COUNT(*) FILTER (WHERE actual_delivery_timestamp > promised_delivery_timestamp) * 100.0 / COUNT(*), 2) AS late_rate_pct
FROM delivered
GROUP BY demand_window
ORDER BY demand_window;

-- Observed result: peak delivery duration is approximately 34.18 minutes versus
-- 33.88 non-peak; late rates are approximately 65.1% versus 64.3%.
-- Interpretation: the generated peak penalty is modest at aggregate level. A
-- city or restaurant breakdown is needed before calling peak degradation a major
-- marketplace constraint.

-- ===========================================================================
-- Analysis 3: Where does the delivery lifecycle lose coverage?
-- ===========================================================================
-- Business question:
-- At which operational milestones do orders stop receiving delivery events?
--
-- Metric definition:
-- milestone coverage = orders containing the event / all orders
-- Delivered orders should normally contain ORDER_DELIVERED; cancelled orders
-- may have a shorter valid prefix.
--
-- Grain: one row per lifecycle milestone.

SELECT 'PARTNER_ASSIGNED' AS event_type, COUNT(DISTINCT order_id) AS orders_with_event,
       ROUND(COUNT(DISTINCT order_id) * 100.0 / (SELECT COUNT(*) FROM orders), 2) AS coverage_pct
FROM delivery_events WHERE event_type = 'PARTNER_ASSIGNED'
UNION ALL
SELECT 'ORDER_PICKED_UP', COUNT(DISTINCT order_id), ROUND(COUNT(DISTINCT order_id) * 100.0 / (SELECT COUNT(*) FROM orders), 2)
FROM delivery_events WHERE event_type = 'ORDER_PICKED_UP'
UNION ALL
SELECT 'ORDER_DELIVERED', COUNT(DISTINCT order_id), ROUND(COUNT(DISTINCT order_id) * 100.0 / (SELECT COUNT(*) FROM orders), 2)
FROM delivery_events WHERE event_type = 'ORDER_DELIVERED'
UNION ALL
SELECT 'ORDER_CANCELLED', COUNT(DISTINCT order_id), ROUND(COUNT(DISTINCT order_id) * 100.0 / (SELECT COUNT(*) FROM orders), 2)
FROM delivery_events WHERE event_type = 'ORDER_CANCELLED';

-- Observed result: partner assignment covers approximately 97.7% of orders,
-- pickup 96.2%, delivery completion 95.4%, matching the delivered-order share.
-- Interpretation: the event layer reflects cancellation prefixes rather than
-- treating missing delivery events as data errors for cancelled orders.

-- ===========================================================================
-- Analysis 4: Is restaurant preparation or travel the larger time component?
-- ===========================================================================
-- Business question:
-- For delivered orders with complete milestones, does time accumulate before
-- pickup or after pickup?
--
-- Metric definition:
-- prep_minutes = ORDER_PICKED_UP - RESTAURANT_ACCEPTED
-- partner_assignment_minutes = PARTNER_ASSIGNED - PARTNER_REQUESTED
-- travel_minutes = ORDER_DELIVERED - ORDER_PICKED_UP
--
-- Grain: one row for the complete-milestone summary.

WITH event_times AS (
    SELECT
        order_id,
        MIN(event_timestamp) FILTER (WHERE event_type = 'RESTAURANT_ACCEPTED') AS restaurant_accepted_at,
        MIN(event_timestamp) FILTER (WHERE event_type = 'PARTNER_REQUESTED') AS partner_requested_at,
        MIN(event_timestamp) FILTER (WHERE event_type = 'PARTNER_ASSIGNED') AS partner_assigned_at,
        MIN(event_timestamp) FILTER (WHERE event_type = 'ORDER_PICKED_UP') AS picked_up_at,
        MIN(event_timestamp) FILTER (WHERE event_type = 'ORDER_DELIVERED') AS delivered_at
    FROM delivery_events
    GROUP BY order_id
)
SELECT
    COUNT(*) AS complete_delivered_orders,
    ROUND(AVG(DATE_DIFF('minute', restaurant_accepted_at, picked_up_at)), 2) AS average_prep_minutes,
    ROUND(AVG(DATE_DIFF('minute', partner_requested_at, partner_assigned_at)), 2) AS average_assignment_minutes,
    ROUND(AVG(DATE_DIFF('minute', picked_up_at, delivered_at)), 2) AS average_travel_minutes
FROM event_times e
JOIN orders o USING (order_id)
WHERE o.order_status = 'DELIVERED'
  AND restaurant_accepted_at IS NOT NULL
  AND partner_requested_at IS NOT NULL
  AND partner_assigned_at IS NOT NULL
  AND picked_up_at IS NOT NULL
  AND delivered_at IS NOT NULL;

-- Observed result: average preparation-to-pickup time is approximately 25.2
-- minutes, assignment time 6.1 minutes, and post-pickup travel 4.8 minutes.
-- Interpretation: preparation is the largest measured lifecycle component in this
-- generated data; restaurant readiness should be investigated before assuming
-- partner travel is the primary bottleneck.
