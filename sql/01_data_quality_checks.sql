-- Data-quality checks for the completed Uber Eats dataset.
-- Dialect: DuckDB.
-- Each query returns violating rows or counts. A healthy result is zero rows
-- or zero violations, except where the query is explicitly a row-count report.

-- ---------------------------------------------------------------------------
-- 1. Load views
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW markets AS SELECT * FROM read_csv_auto('data/raw/markets.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW cities AS SELECT * FROM read_csv_auto('data/raw/cities.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW users AS SELECT * FROM read_csv_auto('data/raw/users.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW restaurants AS SELECT * FROM read_csv_auto('data/raw/restaurants.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW delivery_partners AS SELECT * FROM read_csv_auto('data/raw/delivery_partners.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW addresses AS SELECT * FROM read_csv_auto('data/raw/addresses.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW orders AS SELECT * FROM read_csv_auto('data/raw/orders.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW order_items AS SELECT * FROM read_csv_auto('data/raw/order_items.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW delivery_events AS SELECT * FROM read_csv_auto('data/raw/delivery_events.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW restaurant_availability AS SELECT * FROM read_csv_auto('data/raw/restaurant_availability.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW ratings AS SELECT * FROM read_csv_auto('data/raw/ratings.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW order_issues AS SELECT * FROM read_csv_auto('data/raw/order_issues.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW refunds AS SELECT * FROM read_csv_auto('data/raw/refunds.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW promotions AS SELECT * FROM read_csv_auto('data/raw/promotions.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW order_promotions AS SELECT * FROM read_csv_auto('data/raw/order_promotions.csv', HEADER = TRUE);
CREATE OR REPLACE VIEW order_financials AS SELECT * FROM read_csv_auto('data/raw/order_financials.csv', HEADER = TRUE);

-- ---------------------------------------------------------------------------
-- 2. Row counts: informational baseline checks
-- ---------------------------------------------------------------------------

SELECT 'markets' AS table_name, COUNT(*) AS row_count FROM markets
UNION ALL SELECT 'cities', COUNT(*) FROM cities
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'restaurants', COUNT(*) FROM restaurants
UNION ALL SELECT 'delivery_partners', COUNT(*) FROM delivery_partners
UNION ALL SELECT 'addresses', COUNT(*) FROM addresses
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'delivery_events', COUNT(*) FROM delivery_events
UNION ALL SELECT 'restaurant_availability', COUNT(*) FROM restaurant_availability
UNION ALL SELECT 'ratings', COUNT(*) FROM ratings
UNION ALL SELECT 'order_issues', COUNT(*) FROM order_issues
UNION ALL SELECT 'refunds', COUNT(*) FROM refunds
UNION ALL SELECT 'promotions', COUNT(*) FROM promotions
UNION ALL SELECT 'order_promotions', COUNT(*) FROM order_promotions
UNION ALL SELECT 'order_financials', COUNT(*) FROM order_financials;

-- ---------------------------------------------------------------------------
-- 3. Primary-key uniqueness
-- ---------------------------------------------------------------------------

SELECT 'markets.market_id' AS key_name, COUNT(*) - COUNT(DISTINCT market_id) AS duplicate_count FROM markets
UNION ALL SELECT 'cities.city_id', COUNT(*) - COUNT(DISTINCT city_id) FROM cities
UNION ALL SELECT 'users.user_id', COUNT(*) - COUNT(DISTINCT user_id) FROM users
UNION ALL SELECT 'restaurants.restaurant_id', COUNT(*) - COUNT(DISTINCT restaurant_id) FROM restaurants
UNION ALL SELECT 'delivery_partners.partner_id', COUNT(*) - COUNT(DISTINCT partner_id) FROM delivery_partners
UNION ALL SELECT 'addresses.address_id', COUNT(*) - COUNT(DISTINCT address_id) FROM addresses
UNION ALL SELECT 'orders.order_id', COUNT(*) - COUNT(DISTINCT order_id) FROM orders
UNION ALL SELECT 'order_items.order_item_id', COUNT(*) - COUNT(DISTINCT order_item_id) FROM order_items
UNION ALL SELECT 'delivery_events.event_id', COUNT(*) - COUNT(DISTINCT event_id) FROM delivery_events
UNION ALL SELECT 'restaurant_availability.availability_id', COUNT(*) - COUNT(DISTINCT availability_id) FROM restaurant_availability
UNION ALL SELECT 'ratings.rating_id', COUNT(*) - COUNT(DISTINCT rating_id) FROM ratings
UNION ALL SELECT 'order_issues.issue_id', COUNT(*) - COUNT(DISTINCT issue_id) FROM order_issues
UNION ALL SELECT 'refunds.refund_id', COUNT(*) - COUNT(DISTINCT refund_id) FROM refunds
UNION ALL SELECT 'promotions.promotion_id', COUNT(*) - COUNT(DISTINCT promotion_id) FROM promotions
UNION ALL SELECT 'order_financials.order_id', COUNT(*) - COUNT(DISTINCT order_id) FROM order_financials;

-- Composite-key uniqueness for the bridge table.
SELECT order_id, promotion_id, COUNT(*) AS row_count
FROM order_promotions
GROUP BY order_id, promotion_id
HAVING COUNT(*) > 1;

-- ---------------------------------------------------------------------------
-- 4. NULLs in important fields
-- ---------------------------------------------------------------------------

SELECT 'orders' AS table_name, COUNT(*) AS violations
FROM orders
WHERE order_id IS NULL OR user_id IS NULL OR restaurant_id IS NULL
   OR market_id IS NULL OR city_id IS NULL OR address_id IS NULL
   OR order_timestamp IS NULL OR order_status IS NULL
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
WHERE order_item_id IS NULL OR order_id IS NULL OR item_id IS NULL
   OR quantity IS NULL OR unit_price IS NULL OR item_status IS NULL
UNION ALL SELECT 'delivery_events', COUNT(*) FROM delivery_events
WHERE event_id IS NULL OR order_id IS NULL OR event_type IS NULL OR event_timestamp IS NULL
UNION ALL SELECT 'ratings', COUNT(*) FROM ratings
WHERE rating_id IS NULL OR order_id IS NULL OR user_id IS NULL
   OR restaurant_id IS NULL OR rating IS NULL OR rating_timestamp IS NULL
UNION ALL SELECT 'order_issues', COUNT(*) FROM order_issues
WHERE issue_id IS NULL OR order_id IS NULL OR issue_type IS NULL OR reported_at IS NULL
UNION ALL SELECT 'refunds', COUNT(*) FROM refunds
WHERE refund_id IS NULL OR order_id IS NULL OR user_id IS NULL
   OR refund_amount IS NULL OR refund_type IS NULL OR refund_timestamp IS NULL
UNION ALL SELECT 'order_financials', COUNT(*) FROM order_financials
WHERE order_id IS NULL OR restaurant_commission IS NULL OR delivery_revenue IS NULL
   OR promotion_cost IS NULL OR delivery_partner_cost IS NULL
   OR contribution_margin IS NULL;

-- ---------------------------------------------------------------------------
-- 5. Foreign-key coverage
-- ---------------------------------------------------------------------------

SELECT 'cities.market_id -> markets' AS relationship, COUNT(*) AS orphan_count
FROM cities c LEFT JOIN markets m ON c.market_id = m.market_id
WHERE m.market_id IS NULL
UNION ALL SELECT 'users.home_city_id -> cities', COUNT(*)
FROM users u LEFT JOIN cities c ON u.home_city_id = c.city_id
WHERE c.city_id IS NULL
UNION ALL SELECT 'users.market_id -> markets', COUNT(*)
FROM users u LEFT JOIN markets m ON u.market_id = m.market_id
WHERE m.market_id IS NULL
UNION ALL SELECT 'restaurants.city_id -> cities', COUNT(*)
FROM restaurants r LEFT JOIN cities c ON r.city_id = c.city_id
WHERE c.city_id IS NULL
UNION ALL SELECT 'delivery_partners.city_id -> cities', COUNT(*)
FROM delivery_partners p LEFT JOIN cities c ON p.city_id = c.city_id
WHERE c.city_id IS NULL
UNION ALL SELECT 'addresses.user_id -> users', COUNT(*)
FROM addresses a LEFT JOIN users u ON a.user_id = u.user_id
WHERE u.user_id IS NULL
UNION ALL SELECT 'addresses.city_id -> cities', COUNT(*)
FROM addresses a LEFT JOIN cities c ON a.city_id = c.city_id
WHERE c.city_id IS NULL
UNION ALL SELECT 'orders.user_id -> users', COUNT(*)
FROM orders o LEFT JOIN users u ON o.user_id = u.user_id
WHERE u.user_id IS NULL
UNION ALL SELECT 'orders.restaurant_id -> restaurants', COUNT(*)
FROM orders o LEFT JOIN restaurants r ON o.restaurant_id = r.restaurant_id
WHERE r.restaurant_id IS NULL
UNION ALL SELECT 'orders.address_id -> addresses', COUNT(*)
FROM orders o LEFT JOIN addresses a ON o.address_id = a.address_id
WHERE a.address_id IS NULL
UNION ALL SELECT 'orders.delivery_partner_id -> partners', COUNT(*)
FROM orders o LEFT JOIN delivery_partners p ON o.delivery_partner_id = p.partner_id
WHERE o.delivery_partner_id IS NOT NULL AND p.partner_id IS NULL
UNION ALL SELECT 'order_items.order_id -> orders', COUNT(*)
FROM order_items i LEFT JOIN orders o ON i.order_id = o.order_id
WHERE o.order_id IS NULL
UNION ALL SELECT 'delivery_events.order_id -> orders', COUNT(*)
FROM delivery_events e LEFT JOIN orders o ON e.order_id = o.order_id
WHERE o.order_id IS NULL
UNION ALL SELECT 'ratings.order_id -> orders', COUNT(*)
FROM ratings r LEFT JOIN orders o ON r.order_id = o.order_id
WHERE o.order_id IS NULL
UNION ALL SELECT 'order_issues.order_id -> orders', COUNT(*)
FROM order_issues i LEFT JOIN orders o ON i.order_id = o.order_id
WHERE o.order_id IS NULL
UNION ALL SELECT 'refunds.order_id -> orders', COUNT(*)
FROM refunds r LEFT JOIN orders o ON r.order_id = o.order_id
WHERE o.order_id IS NULL
UNION ALL SELECT 'order_promotions.order_id -> orders', COUNT(*)
FROM order_promotions op LEFT JOIN orders o ON op.order_id = o.order_id
WHERE o.order_id IS NULL
UNION ALL SELECT 'order_promotions.promotion_id -> promotions', COUNT(*)
FROM order_promotions op LEFT JOIN promotions p ON op.promotion_id = p.promotion_id
WHERE p.promotion_id IS NULL
UNION ALL SELECT 'order_financials.order_id -> orders', COUNT(*)
FROM order_financials f LEFT JOIN orders o ON f.order_id = o.order_id
WHERE o.order_id IS NULL;

-- Cross-entity geographic consistency for orders.
SELECT COUNT(*) AS inconsistent_order_geographies
FROM orders o
JOIN users u ON o.user_id = u.user_id
JOIN restaurants r ON o.restaurant_id = r.restaurant_id
WHERE o.market_id <> u.market_id OR o.market_id <> r.market_id
   OR o.city_id <> u.home_city_id OR o.city_id <> r.city_id;

-- ---------------------------------------------------------------------------
-- 6. Duplicate relationship checks
-- ---------------------------------------------------------------------------

-- A saved address is allowed per user, but the same user/address relationship
-- must not be repeated with identical stored attributes.
SELECT user_id, city_id, zone_id, latitude, longitude, address_type, COUNT(*) AS row_count
FROM addresses
GROUP BY user_id, city_id, zone_id, latitude, longitude, address_type
HAVING COUNT(*) > 1;

-- Every order should have at least one item, and item lines must not repeat the
-- same order/item combination unexpectedly.
SELECT o.order_id
FROM orders o
LEFT JOIN order_items i ON o.order_id = i.order_id
GROUP BY o.order_id
HAVING COUNT(i.order_item_id) = 0;

SELECT order_id, item_id, COUNT(*) AS row_count
FROM order_items
GROUP BY order_id, item_id
HAVING COUNT(*) > 1;

-- ---------------------------------------------------------------------------
-- 7. Status and controlled-vocabulary validity
-- ---------------------------------------------------------------------------

SELECT order_status, COUNT(*) AS row_count
FROM orders
WHERE order_status NOT IN ('DELIVERED', 'CANCELLED')
GROUP BY order_status;

SELECT event_type, COUNT(*) AS row_count
FROM delivery_events
WHERE event_type NOT IN (
    'ORDER_PLACED', 'RESTAURANT_ACCEPTED', 'PREPARATION_STARTED',
    'PARTNER_REQUESTED', 'PARTNER_ASSIGNED', 'PARTNER_ARRIVED',
    'ORDER_PICKED_UP', 'ORDER_DELIVERED', 'ORDER_CANCELLED'
)
GROUP BY event_type;

SELECT item_status, COUNT(*) AS row_count
FROM order_items
WHERE item_status NOT IN ('FULFILLED', 'MISSING', 'SUBSTITUTED')
GROUP BY item_status;

-- ---------------------------------------------------------------------------
-- 8. Timestamp and lifecycle consistency
-- ---------------------------------------------------------------------------

SELECT COUNT(*) AS invalid_order_timestamps
FROM orders
WHERE order_timestamp < TIMESTAMP '2024-01-01'
   OR order_timestamp >= TIMESTAMP '2026-01-01'
   OR promised_delivery_timestamp <= order_timestamp
   OR (order_status = 'DELIVERED' AND actual_delivery_timestamp <= order_timestamp)
   OR (order_status = 'CANCELLED' AND cancelled_at <= order_timestamp);

SELECT COUNT(*) AS invalid_order_lifecycle_fields
FROM orders
WHERE (order_status = 'DELIVERED' AND (actual_delivery_timestamp IS NULL OR cancelled_at IS NOT NULL OR cancellation_reason IS NOT NULL))
   OR (order_status = 'CANCELLED' AND (actual_delivery_timestamp IS NOT NULL OR cancelled_at IS NULL OR cancellation_reason IS NULL));

-- Terminal delivery event must agree with the order's terminal timestamp.
SELECT COUNT(*) AS terminal_event_mismatches
FROM (
    SELECT e.order_id, e.event_type, e.event_timestamp,
           ROW_NUMBER() OVER (PARTITION BY e.order_id ORDER BY e.event_timestamp DESC, e.event_id DESC) AS rn
    FROM delivery_events e
) last_event
JOIN orders o ON last_event.order_id = o.order_id
WHERE last_event.rn = 1
  AND ((o.order_status = 'DELIVERED' AND (last_event.event_type <> 'ORDER_DELIVERED' OR last_event.event_timestamp <> o.actual_delivery_timestamp))
    OR (o.order_status = 'CANCELLED' AND (last_event.event_type <> 'ORDER_CANCELLED' OR last_event.event_timestamp <> o.cancelled_at)));

-- ---------------------------------------------------------------------------
-- 9. Impossible and negative values
-- ---------------------------------------------------------------------------

SELECT COUNT(*) AS negative_order_values
FROM orders
WHERE subtotal < 0 OR delivery_fee < 0 OR tax < 0 OR discount_amount < 0 OR total_paid < 0;

SELECT COUNT(*) AS order_total_mismatches
FROM orders
WHERE ABS(total_paid - ROUND(subtotal + delivery_fee + tax - discount_amount, 2)) > 0.011;

SELECT COUNT(*) AS invalid_item_values
FROM order_items
WHERE quantity <= 0 OR unit_price <= 0
   OR (item_status = 'MISSING' AND missing_item_flag <> TRUE)
   OR (item_status = 'MISSING' AND substitution_flag = TRUE)
   OR (item_status = 'SUBSTITUTED' AND substitution_flag <> TRUE);

SELECT COUNT(*) AS invalid_refunds
FROM refunds
WHERE refund_amount <= 0;

SELECT COUNT(*) AS invalid_financial_values
FROM order_financials
WHERE restaurant_commission < 0 OR delivery_revenue < 0 OR service_fee < 0
   OR advertising_revenue < 0 OR promotion_cost < 0 OR delivery_partner_cost < 0
   OR payment_processing_cost < 0 OR support_cost < 0;

-- ---------------------------------------------------------------------------
-- 10. Financial consistency
-- ---------------------------------------------------------------------------

SELECT COUNT(*) AS financial_margin_mismatches
FROM order_financials f
WHERE ABS(
    f.contribution_margin
    - ROUND(
        f.restaurant_commission + f.delivery_revenue + f.service_fee + f.advertising_revenue
        - f.promotion_cost - f.delivery_partner_cost - f.payment_processing_cost - f.support_cost,
        2
      )
) > 0.011;

SELECT COUNT(*) AS missing_financial_orders
FROM orders o
LEFT JOIN order_financials f ON o.order_id = f.order_id
WHERE f.order_id IS NULL;

-- ---------------------------------------------------------------------------
-- 11. Promotion and refund consistency
-- ---------------------------------------------------------------------------

SELECT COUNT(*) AS invalid_promotion_redemptions
FROM order_promotions op
JOIN orders o ON op.order_id = o.order_id
JOIN promotions p ON op.promotion_id = p.promotion_id
WHERE o.order_timestamp < p.start_date
   OR o.order_timestamp > p.end_date
   OR o.subtotal < p.minimum_order_value
   OR op.discount_amount <= 0
   OR op.discount_amount > o.discount_amount + 0.011;

SELECT COUNT(*) AS refunds_exceeding_order_paid
FROM refunds r
JOIN orders o ON r.order_id = o.order_id
WHERE r.refund_amount > o.total_paid;

-- ---------------------------------------------------------------------------
-- 12. Delivery relationship consistency
-- ---------------------------------------------------------------------------

SELECT COUNT(*) AS invalid_event_partners
FROM delivery_events e
JOIN orders o ON e.order_id = o.order_id
LEFT JOIN delivery_partners p ON e.partner_id = p.partner_id
WHERE e.partner_id IS NOT NULL
  AND (p.partner_id IS NULL OR p.city_id <> o.city_id OR p.market_id <> o.market_id);

SELECT COUNT(*) AS delivered_orders_missing_terminal_event
FROM orders o
LEFT JOIN delivery_events e ON o.order_id = e.order_id AND e.event_type = 'ORDER_DELIVERED'
WHERE o.order_status = 'DELIVERED' AND e.event_id IS NULL;
