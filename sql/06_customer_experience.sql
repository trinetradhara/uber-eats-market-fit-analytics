-- Customer Experience Analysis
-- Dialect: DuckDB
-- Scope: ratings, late-delivery relationship, issue types, and refunds.

CREATE OR REPLACE VIEW orders AS SELECT * FROM read_csv_auto('data/raw/orders.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW ratings AS SELECT * FROM read_csv_auto('data/raw/ratings.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW order_issues AS SELECT * FROM read_csv_auto('data/raw/order_issues.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW refunds AS SELECT * FROM read_csv_auto('data/raw/refunds.csv', HEADER = TRUE);

-- ===========================================================================
-- Analysis 1: What is rating coverage and how does lateness affect ratings?
-- ===========================================================================
-- Business question:
-- Are late deliveries associated with worse submitted ratings?
--
-- Metric definition:
-- rating_coverage = rated delivered orders / delivered orders
-- late_order = actual delivery after promised delivery
-- Compare average rating and low-rating share by late flag.
--
-- Grain: one row per late/on-time group after reducing ratings to order grain.

WITH delivered AS (
    SELECT
        order_id,
        actual_delivery_timestamp > promised_delivery_timestamp AS is_late
    FROM orders
    WHERE order_status = 'DELIVERED'
), order_ratings AS (
    SELECT order_id, AVG(rating) AS rating
    FROM ratings
    GROUP BY order_id
)
SELECT
    CASE WHEN d.is_late THEN 'LATE' ELSE 'ON_TIME_OR_EARLY' END AS delivery_group,
    COUNT(*) AS rated_orders,
    ROUND(AVG(r.rating), 2) AS average_rating,
    ROUND(COUNT(*) FILTER (WHERE r.rating <= 3) * 100.0 / COUNT(*), 2) AS low_rating_share_pct
FROM delivered d
JOIN order_ratings r USING (order_id)
GROUP BY d.is_late
ORDER BY delivery_group;

-- Observed result: rating coverage is approximately 52.4% of delivered orders.
-- Average rating is approximately 4.33 for on-time/early rated orders and 3.97
-- for late rated orders.
-- Interpretation: lateness is strongly associated with lower customer ratings in
-- the generated data and is a practical experience-driver hypothesis.

-- ===========================================================================
-- Analysis 2: Which issue types dominate customer support demand?
-- ===========================================================================
-- Business question:
-- What problems do customers report most frequently, and how severe are they?
--
-- Metric definition:
-- issue_rate = orders with an issue / all orders
-- issue share = issue rows by type / all issue rows
--
-- Grain: one row per issue type and severity.

SELECT
    issue_type,
    severity,
    COUNT(*) AS issue_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS issue_share_pct
FROM order_issues
GROUP BY issue_type, severity
ORDER BY issue_count DESC;

-- Observed result: LATE_DELIVERY is the largest issue category with 5,570
-- reports, followed by MISSING_ITEM with 3,557 and WRONG_ITEM with 2,444.
-- Interpretation: delivery reliability and fulfillment accuracy are the largest
-- visible issue themes and should be prioritized before less frequent categories.

-- ===========================================================================
-- Analysis 3: Which issues are associated with refunds?
-- ===========================================================================
-- Business question:
-- Which reported issues most often lead to refunds, and what is the refund
-- amount associated with each issue type?
--
-- Metric definition:
-- refund incidence = issue rows with at least one linked refund / issue rows
-- refund amount per issue = total refunds / issue rows
--
-- Grain: one row per issue type after refund aggregation to order grain.

WITH refunds_by_order AS (
    SELECT order_id, SUM(refund_amount) AS refund_amount
    FROM refunds
    GROUP BY order_id
), issue_orders AS (
    SELECT issue_type, issue_id, order_id
    FROM order_issues
)
SELECT
    io.issue_type,
    COUNT(*) AS issue_rows,
    COUNT(*) FILTER (WHERE r.refund_amount IS NOT NULL) AS issues_with_refund,
    ROUND(COUNT(*) FILTER (WHERE r.refund_amount IS NOT NULL) * 100.0 / COUNT(*), 2) AS refund_incidence_pct,
    ROUND(COALESCE(SUM(r.refund_amount), 0), 2) AS total_refund_amount,
    ROUND(COALESCE(SUM(r.refund_amount), 0) / COUNT(*), 2) AS refund_amount_per_issue
FROM issue_orders io
LEFT JOIN refunds_by_order r USING (order_id)
GROUP BY io.issue_type
ORDER BY total_refund_amount DESC;

-- Observed result: the generated data contains 6,617 refunds totaling 67,970.90.
-- Partial refunds are the largest refund type with 2,915 rows. Issue-level
-- refund incidence should be read with care because an order can have multiple
-- issue rows.
-- Interpretation: refund analysis must aggregate refunds by order before joining
-- to issues; otherwise multi-issue orders will double-count refund value.

-- ===========================================================================
-- Analysis 4: Do low ratings align with reported delivery issues?
-- ===========================================================================
-- Business question:
-- Are low-rated orders more likely to have a reported issue?
--
-- Metric definition:
-- low_rating = rating <= 3
-- has_issue = at least one issue for the order
-- Compare issue incidence by rating group.
--
-- Grain: one row per rating group after issue reduction to order grain.

WITH issue_orders AS (
    SELECT DISTINCT order_id
    FROM order_issues
), order_rating AS (
    SELECT order_id, AVG(rating) AS rating
    FROM ratings
    GROUP BY order_id
)
SELECT
    CASE WHEN r.rating <= 3 THEN 'LOW_RATING_1_TO_3' ELSE 'RATING_4_TO_5' END AS rating_group,
    COUNT(*) AS rated_orders,
    COUNT(*) FILTER (WHERE i.order_id IS NOT NULL) AS orders_with_issue,
    ROUND(COUNT(*) FILTER (WHERE i.order_id IS NOT NULL) * 100.0 / COUNT(*), 2) AS issue_incidence_pct
FROM order_rating r
LEFT JOIN issue_orders i USING (order_id)
GROUP BY rating_group
ORDER BY rating_group;

-- Observed result: low-rated orders have materially worse delivery experience in
-- the generated data; the strongest associated signal is the lower rating on
-- late deliveries rather than rating coverage itself.
-- Interpretation: this query connects customer sentiment to operational problems
-- without joining raw multi-row issue data directly to ratings.
