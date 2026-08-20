# Schema and Grain

This project contains 16 generated CSV tables. The SQL examples in this directory target DuckDB, which can query the CSV files directly with `read_csv_auto`.

## Table Map

| Table | Actual rows | Grain | Primary key | Main foreign keys |
|---|---:|---|---|---|
| `markets` | 5 | One row per market/country | `market_id` | None |
| `cities` | 29 | One row per city | `city_id` | `market_id -> markets` |
| `users` | 55,000 | One row per user | `user_id` | `market_id -> markets`, `home_city_id -> cities` |
| `restaurants` | 12,000 | One row per restaurant | `restaurant_id` | `market_id -> markets`, `city_id -> cities` |
| `delivery_partners` | 12,000 | One row per delivery partner | `partner_id` | `market_id -> markets`, `city_id -> cities` |
| `addresses` | 68,427 | One saved address per user | `address_id` | `user_id -> users`, `city_id -> cities` |
| `orders` | 500,000 | One row per order | `order_id` | `user_id`, `restaurant_id`, `delivery_partner_id`, `market_id`, `city_id`, `address_id` |
| `order_items` | 886,569 | One item line within an order | `order_item_id` | `order_id -> orders` |
| `delivery_events` | 3,942,064 | One lifecycle event for an order | `event_id` | `order_id -> orders`, nullable `partner_id -> delivery_partners` |
| `restaurant_availability` | 5,016,000 | One restaurant operational snapshot | `availability_id` | `restaurant_id -> restaurants` |
| `ratings` | 249,902 | One submitted rating | `rating_id` | `order_id`, `user_id`, `restaurant_id` |
| `order_issues` | 17,949 | One reported order issue | `issue_id` | `order_id -> orders` |
| `refunds` | 6,617 | One refund transaction | `refund_id` | `order_id -> orders`, `user_id -> users` |
| `promotions` | 60 | One promotion definition | `promotion_id` | None in the actual schema |
| `order_promotions` | 57,467 | One order-promotion redemption | `(order_id, promotion_id)` | `order_id -> orders`, `promotion_id -> promotions` |
| `order_financials` | 500,000 | One financial summary per order | `order_id` | `order_id -> orders` |

## Detailed Contracts

### `markets`

Columns: `market_id`, `country`, `currency`, `timezone`, `launch_date`, nullable `exit_date`, `market_status`, `market_type`.

This is the highest geographic grain. It contains five markets: India, USA, Australia, UK, and Japan.

### `cities`

Columns: `city_id`, `market_id`, `city_name`, `launch_date`, nullable `population`, `population_density`, `urban_tier`, `latitude`, and `longitude`.

Each city belongs to exactly one market. City-level joins should use `city_id`; do not join cities by name.

### `users`

Columns: `user_id`, `market_id`, `home_city_id`, `signup_timestamp`, `acquisition_channel`, nullable `acquisition_source`, `is_uber_mobility_user`, nullable `mobility_signup_date`, nullable `membership_status`, and nullable `membership_start_date`.

One row represents one registered user. User order activity must be calculated from `orders`, not inferred from signup rows.

### `restaurants`

Columns: `restaurant_id`, `market_id`, `city_id`, `restaurant_name`, `cuisine_type`, `price_band`, `onboard_date`, nullable `offboard_date`, nullable `chain_flag`, nullable `restaurant_rating`, and nullable `delivery_radius_km`.

One row represents one restaurant. Restaurant order volume comes from `orders`; availability is stored separately at snapshot grain.

### `delivery_partners`

Columns: `partner_id`, `market_id`, `city_id`, `onboard_date`, nullable `offboard_date`, nullable `vehicle_type`, and nullable `partner_rating`.

One row represents one delivery partner. Partner assignment and event activity come from orders and delivery events.

### `addresses`

Columns: `address_id`, `user_id`, `city_id`, `zone_id`, nullable `latitude`, nullable `longitude`, nullable `address_type`, and `created_at`.

One row represents one saved address. A user can have multiple addresses. An order selects one address, so `user_id` is not unique here.

### `orders`

Columns: `order_id`, `user_id`, `restaurant_id`, nullable `delivery_partner_id`, `market_id`, `city_id`, `address_id`, `order_timestamp`, `promised_delivery_timestamp`, nullable `actual_delivery_timestamp`, `order_status`, `subtotal`, `delivery_fee`, `tax`, `discount_amount`, `total_paid`, nullable `cancelled_at`, and nullable `cancellation_reason`.

This is the central order-level fact table. Valid statuses are `DELIVERED` and `CANCELLED` in the generated Stage 4 data.

### `order_items`

Columns: `order_item_id`, `order_id`, `item_id`, `item_name`, `quantity`, `unit_price`, `item_status`, `missing_item_flag`, and `substitution_flag`.

One order can have many item rows. Never sum order-level monetary columns after joining directly to this table without re-aggregating by `order_id`.

### `delivery_events`

Columns: `event_id`, `order_id`, nullable `partner_id`, `event_type`, `event_timestamp`, nullable `latitude`, and nullable `longitude`.

One order can have many events. Valid event types are `ORDER_PLACED`, `RESTAURANT_ACCEPTED`, `PREPARATION_STARTED`, `PARTNER_REQUESTED`, `PARTNER_ASSIGNED`, `PARTNER_ARRIVED`, `ORDER_PICKED_UP`, `ORDER_DELIVERED`, and `ORDER_CANCELLED`.

### `restaurant_availability`

Columns: `availability_id`, `restaurant_id`, `timestamp`, `is_accepting_orders`, nullable `estimated_prep_time_min`, and nullable `capacity_status`.

This table uses four weekly snapshots per restaurant: Wednesday lunch, Wednesday dinner, Saturday lunch, and Saturday dinner. It is not an order table and should be joined to orders through a time-window mapping, not only by restaurant.

### `ratings`

Columns: `rating_id`, `order_id`, `user_id`, `restaurant_id`, `rating`, `rating_timestamp`, and nullable `review_text`.

Only a subset of orders is rated. Rating coverage must use delivered orders as the denominator where appropriate.

### `order_issues`

Columns: `issue_id`, `order_id`, `issue_type`, nullable `severity`, `reported_at`, and nullable `resolved_at`.

One order can have multiple issues. Valid issue types are `LATE_DELIVERY`, `MISSING_ITEM`, `WRONG_ITEM`, `COLD_FOOD`, `DAMAGED_FOOD`, `RESTAURANT_QUALITY`, `DRIVER_BEHAVIOR`, `PAYMENT_ISSUE`, and `OTHER`.

### `refunds`

Columns: `refund_id`, `order_id`, `user_id`, `refund_amount`, `refund_type`, `refund_reason`, and `refund_timestamp`.

One order can have multiple refund rows. Valid refund types are `FULL`, `PARTIAL`, `ITEM_LEVEL`, `DELIVERY_FEE`, and `GOODWILL`.

### `promotions`

Columns: `promotion_id`, `promotion_name`, `promotion_type`, `discount_type`, `discount_value`, nullable `minimum_order_value`, nullable `maximum_discount`, `start_date`, and `end_date`.

This table defines promotions. The actual schema has no `market_id`, so market-level promotion analysis must use redeemed orders and their market rather than joining promotions directly to markets.

### `order_promotions`

Columns: `order_id`, `promotion_id`, and `discount_amount`.

This is a bridge table at order-promotion grain. Its composite key is `(order_id, promotion_id)`. An order can have zero or more redemptions.

### `order_financials`

Columns: `order_id`, `restaurant_commission`, `delivery_revenue`, nullable `service_fee`, nullable `advertising_revenue`, `promotion_cost`, `delivery_partner_cost`, nullable `payment_processing_cost`, nullable `support_cost`, and `contribution_margin`.

This is one row per order. Contribution margin should be reconciled as visible revenue components minus visible cost components.

## Join and Double-Counting Rules

1. Start order-level metrics from `orders`.
2. Aggregate `order_items`, `delivery_events`, `order_issues`, `refunds`, and `order_promotions` to one row per order before joining to order-level facts.
3. Use `COUNT(DISTINCT order_id)` when measuring orders after a one-to-many join.
4. Use `COUNT(DISTINCT user_id)` for user metrics after joining order-level tables.
5. Join `order_financials` directly by `order_id`; it is one-to-one.
6. Treat nullable partner IDs as valid for some cancelled orders.
7. Do not use `restaurant_availability` as a direct order-count fact table.
8. For cohort analysis, anchor users on `signup_timestamp` and order activity on `order_timestamp`.
9. For delivery analysis, aggregate events by order before calculating lifecycle durations.
10. Keep promotion redemption amounts separate from the order's `discount_amount` until reconciliation is explicitly checked.

## Recommended Query Layers

Use these reusable logical layers in later SQL files:

- `order_base`: one row per order with market, city, user, restaurant, and status
- `item_order_summary`: one row per order aggregated from `order_items`
- `delivery_order_summary`: one row per order aggregated from `delivery_events`
- `issue_order_summary`: one row per order aggregated from `order_issues`
- `refund_order_summary`: one row per order aggregated from `refunds`
- `promotion_order_summary`: one row per order aggregated from `order_promotions`
- `financial_order_summary`: one row per order from `order_financials`

These layers prevent accidental multiplication when several one-to-many tables are combined.
