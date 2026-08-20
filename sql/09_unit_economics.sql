-- Unit Economics Analysis
-- Dialect: DuckDB
-- Scope: contribution margin by market/order segment, cost components,
-- promotion impact, and negative-margin share.

CREATE OR REPLACE VIEW orders AS SELECT * FROM read_csv_auto('data/raw/orders.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW restaurants AS SELECT * FROM read_csv_auto('data/raw/restaurants.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW order_promotions AS SELECT * FROM read_csv_auto('data/raw/order_promotions.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW order_financials AS SELECT * FROM read_csv_auto('data/raw/order_financials.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW markets AS SELECT * FROM read_csv_auto('data/raw/markets.csv', HEADER = TRUE);

-- ===========================================================================
-- Analysis 1: Which markets have the strongest unit economics?
-- ===========================================================================
-- Business question:
-- Does absolute marketplace scale correspond to positive contribution margin?
--
-- Metric definition:
-- contribution_margin_per_order = average order contribution margin
-- negative_margin_share = negative-margin orders / all orders
-- total_contribution_margin = sum of contribution margin
--
-- Grain: one row per market; financials are one-to-one with orders.

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
ORDER BY contribution_margin_per_order DESC;

-- Observed result: all markets have negative average contribution margin per
-- order. Australia is least negative at approximately -8.12, while the UK is
-- most negative at approximately -8.96.
-- Interpretation: absolute order scale is not sufficient evidence of sustainable
-- scale; unit economics must be evaluated alongside marketplace volume.

-- ===========================================================================
-- Analysis 2: Which order segments carry the highest margin risk?
-- ===========================================================================
-- Business question:
-- How does contribution margin differ by order status, basket value, and price
-- band?
--
-- Metric definition:
-- Order value bands use total_paid: LOW <20, MEDIUM 20-40, HIGH >40.
-- Price band is inherited from the selected restaurant.
--
-- Grain: one row per order segment.

SELECT
    o.order_status,
    r.price_band,
    CASE
        WHEN o.total_paid < 20 THEN 'LOW_VALUE'
        WHEN o.total_paid <= 40 THEN 'MEDIUM_VALUE'
        ELSE 'HIGH_VALUE'
    END AS order_value_segment,
    COUNT(*) AS orders,
    ROUND(AVG(f.contribution_margin), 2) AS average_contribution_margin,
    ROUND(COUNT(*) FILTER (WHERE f.contribution_margin < 0) * 100.0 / COUNT(*), 2) AS negative_margin_share_pct
FROM orders o
JOIN restaurants r USING (restaurant_id)
JOIN order_financials f USING (order_id)
GROUP BY o.order_status, r.price_band, order_value_segment
ORDER BY average_contribution_margin;

-- Interpretation:
-- This output identifies the combinations of order status, price band, and basket
-- size where margin pressure is concentrated. Use it to prioritize driver-level
-- decomposition rather than assuming every negative-margin order has the same
-- cause.

-- ===========================================================================
-- Analysis 3: Which cost components separate negative- and positive-margin orders?
-- ===========================================================================
-- Business question:
-- Are negative margins more associated with delivery cost, discounts, support,
-- or payment processing?
--
-- Metric definition:
-- Compare average visible revenue and cost components by margin sign.
--
-- Grain: one row per margin-sign group.

SELECT
    CASE WHEN contribution_margin < 0 THEN 'NEGATIVE_MARGIN' ELSE 'NON_NEGATIVE_MARGIN' END AS margin_group,
    COUNT(*) AS orders,
    ROUND(AVG(restaurant_commission), 2) AS avg_restaurant_commission,
    ROUND(AVG(delivery_revenue), 2) AS avg_delivery_revenue,
    ROUND(AVG(service_fee), 2) AS avg_service_fee,
    ROUND(AVG(advertising_revenue), 2) AS avg_advertising_revenue,
    ROUND(AVG(promotion_cost), 2) AS avg_promotion_cost,
    ROUND(AVG(delivery_partner_cost), 2) AS avg_delivery_partner_cost,
    ROUND(AVG(payment_processing_cost), 2) AS avg_payment_processing_cost,
    ROUND(AVG(support_cost), 2) AS avg_support_cost,
    ROUND(AVG(contribution_margin), 2) AS avg_contribution_margin
FROM order_financials
GROUP BY margin_group;

-- Observed result: 89.19% of orders have negative contribution margin. Negative-
-- margin orders average delivery partner cost of approximately 16.85, versus
-- 8.79 for non-negative-margin orders.
-- Interpretation: delivery partner cost is the clearest observed margin-risk
-- component in this generated data; promotion and support costs should still be
-- decomposed alongside it.

-- ===========================================================================
-- Analysis 4: What is the descriptive margin impact of promotions?
-- ===========================================================================
-- Business question:
-- Do promoted orders have weaker contribution margin than organic orders?
--
-- Metric definition:
-- promoted_order = order with at least one order_promotions row
-- Compare average contribution margin, negative-margin share, and promotion cost.
--
-- Grain: one row per order after promotion redemption reduction.

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
-- margin versus -8.38 for organic orders.
-- Interpretation: promotions are associated with weaker economics here, but this
-- is not causal. Promoted orders may differ in user mix, order value, or context.
