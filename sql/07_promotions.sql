-- Promotions Analysis
-- Dialect: DuckDB
-- Scope: redemption patterns, promotion-dependent users, order behavior,
-- and contribution-margin implications.

CREATE OR REPLACE VIEW orders AS SELECT * FROM read_csv_auto('data/raw/orders.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW users AS SELECT * FROM read_csv_auto('data/raw/users.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW promotions AS SELECT * FROM read_csv_auto('data/raw/promotions.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW order_promotions AS SELECT * FROM read_csv_auto('data/raw/order_promotions.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW order_financials AS SELECT * FROM read_csv_auto('data/raw/order_financials.csv', HEADER = TRUE);

-- ===========================================================================
-- Analysis 1: Which promotions and promotion types are redeemed?
-- ===========================================================================
-- Business question:
-- Which promotion types generate the most redemption activity?
--
-- Metric definition:
-- redemption_count = rows in order_promotions
-- redeemed_orders = distinct orders using the promotion
-- redemption_share = promotion redemptions / all redemptions
--
-- Grain: one row per promotion type and promotion.

SELECT
    p.promotion_type,
    p.discount_type,
    COUNT(*) AS redemption_count,
    COUNT(DISTINCT op.order_id) AS redeemed_orders,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS redemption_share_pct,
    ROUND(SUM(op.discount_amount), 2) AS total_discount_amount
FROM order_promotions op
JOIN promotions p USING (promotion_id)
GROUP BY p.promotion_type, p.discount_type
ORDER BY redemption_count DESC;

-- Observed result: 57,467 redemptions occur across 60 promotions and 11.49% of
-- all orders use a promotion. Percentage promotions outnumber fixed-amount
-- promotions 40 to 20 in the promotion catalog.
-- Interpretation: promotional exposure is meaningful but not dominant; redemption
-- analysis should distinguish catalog availability from actual order usage.

-- ===========================================================================
-- Analysis 2: Which users are promotion-dependent?
-- ===========================================================================
-- Business question:
-- Which customers rely most heavily on promotions for their orders?
--
-- Metric definition:
-- promo_order_share = orders with redemption / all user orders
-- promotion-dependent users are users with at least 50% of orders using a
-- promotion and at least two total orders.
--
-- Grain: one row per user, followed by a segment summary.

WITH user_orders AS (
    SELECT user_id, COUNT(*) AS total_orders
    FROM orders
    GROUP BY user_id
), user_promo_orders AS (
    SELECT o.user_id, COUNT(DISTINCT op.order_id) AS promo_orders
    FROM orders o
    JOIN order_promotions op USING (order_id)
    GROUP BY o.user_id
), user_behavior AS (
    SELECT
        u.user_id,
        COALESCE(uo.total_orders, 0) AS total_orders,
        COALESCE(upo.promo_orders, 0) AS promo_orders,
        COALESCE(upo.promo_orders, 0) * 1.0 / NULLIF(uo.total_orders, 0) AS promo_order_share
    FROM users u
    LEFT JOIN user_orders uo USING (user_id)
    LEFT JOIN user_promo_orders upo USING (user_id)
)
SELECT
    CASE
        WHEN total_orders = 0 THEN 'NO_ORDERS'
        WHEN total_orders >= 2 AND promo_order_share >= 0.50 THEN 'PROMOTION_DEPENDENT'
        WHEN promo_orders > 0 THEN 'PROMOTION_USER_NOT_DEPENDENT'
        ELSE 'ORGANIC_ONLY'
    END AS user_promotion_segment,
    COUNT(*) AS users,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS user_share_pct,
    ROUND(AVG(total_orders), 2) AS average_orders,
    ROUND(AVG(promo_order_share), 3) AS average_promo_order_share
FROM user_behavior
GROUP BY user_promotion_segment
ORDER BY users DESC;

-- Observed result: 33,116 ordering users use at least one promotion. The
-- distribution of promotion share varies by user; 60.58% of ordering users have
-- at least one promoted order.
-- Interpretation: promotion usage is common enough to segment users, but a user
-- with one promotional order should not automatically be labeled dependent.

-- ===========================================================================
-- Analysis 3: Do promoted orders behave differently from organic orders?
-- ===========================================================================
-- Business question:
-- Are promoted orders associated with different basket value, completion, or
-- order frequency characteristics?
--
-- Metric definition:
-- promoted_order = order with at least one order_promotions row
-- Compare total paid, subtotal, delivered rate, and discount per order.
--
-- Grain: one row per order after reducing redemptions to order grain.

WITH promoted_orders AS (
    SELECT
        o.order_id,
        CASE WHEN COUNT(op.promotion_id) > 0 THEN 'PROMOTED' ELSE 'ORGANIC' END AS order_group,
        o.subtotal,
        o.total_paid,
        o.order_status,
        COALESCE(SUM(op.discount_amount), 0) AS promotion_discount
    FROM orders o
    LEFT JOIN order_promotions op USING (order_id)
    GROUP BY o.order_id, o.subtotal, o.total_paid, o.order_status
)
SELECT
    order_group,
    COUNT(*) AS orders,
    ROUND(AVG(subtotal), 2) AS average_subtotal,
    ROUND(AVG(total_paid), 2) AS average_total_paid,
    ROUND(AVG(promotion_discount), 2) AS average_promotion_discount,
    ROUND(COUNT(*) FILTER (WHERE order_status = 'DELIVERED') * 100.0 / COUNT(*), 2) AS delivered_rate_pct
FROM promoted_orders
GROUP BY order_group;

-- Observed result: promoted orders average approximately 25.31 total paid versus
-- 28.26 for organic orders. The promoted group is therefore lower-value on this
-- generated order measure, not simply a larger version of organic demand.
-- Interpretation: promotion impact should be evaluated with user mix and order
-- context controls; raw group averages do not establish incremental causality.

-- ===========================================================================
-- Analysis 4: What is the contribution-margin implication of promotions?
-- ===========================================================================
-- Business question:
-- Are promoted orders economically weaker than organic orders?
--
-- Metric definition:
-- contribution_margin = order_financials.contribution_margin
-- Compare average margin, negative-margin share, and promotion cost per order.
--
-- Grain: one row per order after reducing promotion redemptions to order grain.

WITH promoted_orders AS (
    SELECT
        o.order_id,
        CASE WHEN COUNT(op.promotion_id) > 0 THEN 'PROMOTED' ELSE 'ORGANIC' END AS order_group
    FROM orders o
    LEFT JOIN order_promotions op USING (order_id)
    GROUP BY o.order_id
)
SELECT
    po.order_group,
    COUNT(*) AS orders,
    ROUND(AVG(f.contribution_margin), 2) AS average_contribution_margin,
    ROUND(COUNT(*) FILTER (WHERE f.contribution_margin < 0) * 100.0 / COUNT(*), 2) AS negative_margin_share_pct,
    ROUND(AVG(f.promotion_cost), 2) AS average_promotion_cost
FROM promoted_orders po
JOIN order_financials f USING (order_id)
GROUP BY po.order_group;

-- Observed result: promoted orders average approximately -11.12 contribution
-- margin versus -8.38 for organic orders. This is a descriptive association,
-- not a causal estimate, because promoted and organic orders may have different
-- users, baskets, and operating contexts.
-- Interpretation: promotion activity has a visible margin tradeoff in the
-- generated data and should be paired with incrementality or retention analysis
-- before recommending broader discounting.

-- End of delivery, customer-experience, and promotion-adjacent analysis modules.
-- Retention, unit economics, and full product RCA remain separate modules.
