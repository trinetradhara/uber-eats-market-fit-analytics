"""Authoritative contracts for the 16 required Uber Eats tables."""

from typing import Final

import pandas as pd

# TABLE_SCHEMAS contains pandas dtypes used by empty DataFrames. The SQL type
# registry preserves the specification's exact column types for contract checks.
TABLE_SCHEMAS: Final[dict[str, dict[str, str]]] = {
    "markets": {
        "market_id": "Int64", "country": "string", "currency": "string",
        "timezone": "string", "launch_date": "datetime64[ns]", "exit_date": "datetime64[ns]",
        "market_status": "string", "market_type": "string",
    },
    "cities": {
        "city_id": "Int64", "market_id": "Int64", "city_name": "string", "launch_date": "datetime64[ns]",
        "population": "Int64", "population_density": "float64", "urban_tier": "string",
        "latitude": "float64", "longitude": "float64",
    },
    "users": {
        "user_id": "Int64", "market_id": "Int64", "home_city_id": "Int64",
        "signup_timestamp": "datetime64[ns]", "acquisition_channel": "string",
        "acquisition_source": "string", "is_uber_mobility_user": "boolean",
        "mobility_signup_date": "datetime64[ns]", "membership_status": "string",
        "membership_start_date": "datetime64[ns]",
    },
    "restaurants": {
        "restaurant_id": "Int64", "market_id": "Int64", "city_id": "Int64",
        "restaurant_name": "string", "cuisine_type": "string", "price_band": "string",
        "onboard_date": "datetime64[ns]", "offboard_date": "datetime64[ns]", "chain_flag": "boolean",
        "restaurant_rating": "float64", "delivery_radius_km": "float64",
    },
    "delivery_partners": {
        "partner_id": "Int64", "market_id": "Int64", "city_id": "Int64",
        "onboard_date": "datetime64[ns]", "offboard_date": "datetime64[ns]",
        "vehicle_type": "string", "partner_rating": "float64",
    },
    "addresses": {
        "address_id": "Int64", "user_id": "Int64", "city_id": "Int64", "zone_id": "string",
        "latitude": "float64", "longitude": "float64", "address_type": "string", "created_at": "datetime64[ns]",
    },
    "orders": {
        "order_id": "Int64", "user_id": "Int64", "restaurant_id": "Int64", "delivery_partner_id": "Int64",
        "market_id": "Int64", "city_id": "Int64", "address_id": "Int64", "order_timestamp": "datetime64[ns]",
        "promised_delivery_timestamp": "datetime64[ns]", "actual_delivery_timestamp": "datetime64[ns]",
        "order_status": "string", "subtotal": "float64", "delivery_fee": "float64", "tax": "float64",
        "discount_amount": "float64", "total_paid": "float64", "cancelled_at": "datetime64[ns]",
        "cancellation_reason": "string",
    },
    "order_items": {
        "order_item_id": "Int64", "order_id": "Int64", "item_id": "Int64", "item_name": "string",
        "quantity": "Int64", "unit_price": "float64", "item_status": "string",
        "missing_item_flag": "boolean", "substitution_flag": "boolean",
    },
    "delivery_events": {
        "event_id": "Int64", "order_id": "Int64", "partner_id": "Int64", "event_type": "string",
        "event_timestamp": "datetime64[ns]", "latitude": "float64", "longitude": "float64",
    },
    "restaurant_availability": {
        "availability_id": "Int64", "restaurant_id": "Int64", "timestamp": "datetime64[ns]",
        "is_accepting_orders": "boolean", "estimated_prep_time_min": "Int64", "capacity_status": "string",
    },
    "ratings": {
        "rating_id": "Int64", "order_id": "Int64", "user_id": "Int64", "restaurant_id": "Int64",
        "rating": "Int64", "rating_timestamp": "datetime64[ns]", "review_text": "string",
    },
    "order_issues": {
        "issue_id": "Int64", "order_id": "Int64", "issue_type": "string", "severity": "string",
        "reported_at": "datetime64[ns]", "resolved_at": "datetime64[ns]",
    },
    "refunds": {
        "refund_id": "Int64", "order_id": "Int64", "user_id": "Int64", "refund_amount": "float64",
        "refund_type": "string", "refund_reason": "string", "refund_timestamp": "datetime64[ns]",
    },
    "promotions": {
        "promotion_id": "Int64", "promotion_name": "string", "promotion_type": "string",
        "discount_type": "string", "discount_value": "float64", "minimum_order_value": "float64",
        "maximum_discount": "float64", "start_date": "datetime64[ns]", "end_date": "datetime64[ns]",
    },
    "order_promotions": {
        "order_id": "Int64", "promotion_id": "Int64", "discount_amount": "float64",
    },
    "order_financials": {
        "order_id": "Int64", "restaurant_commission": "float64", "delivery_revenue": "float64",
        "service_fee": "float64", "advertising_revenue": "float64", "promotion_cost": "float64",
        "delivery_partner_cost": "float64", "payment_processing_cost": "float64", "support_cost": "float64",
        "contribution_margin": "float64",
    },
}

TABLE_SQL_TYPES: Final[dict[str, dict[str, str]]] = {
    "markets": {"market_id": "INT", "country": "VARCHAR(50)", "currency": "VARCHAR(10)", "timezone": "VARCHAR(50)", "launch_date": "DATE", "exit_date": "DATE", "market_status": "VARCHAR(20)", "market_type": "VARCHAR(20)"},
    "cities": {"city_id": "INT", "market_id": "INT", "city_name": "VARCHAR(100)", "launch_date": "DATE", "population": "INT", "population_density": "DECIMAL(10,2)", "urban_tier": "VARCHAR(30)", "latitude": "DECIMAL(9,6)", "longitude": "DECIMAL(9,6)"},
    "users": {"user_id": "BIGINT", "market_id": "INT", "home_city_id": "INT", "signup_timestamp": "TIMESTAMP", "acquisition_channel": "VARCHAR(30)", "acquisition_source": "VARCHAR(50)", "is_uber_mobility_user": "BOOLEAN", "mobility_signup_date": "DATE", "membership_status": "VARCHAR(30)", "membership_start_date": "DATE"},
    "restaurants": {"restaurant_id": "BIGINT", "market_id": "INT", "city_id": "INT", "restaurant_name": "VARCHAR(150)", "cuisine_type": "VARCHAR(50)", "price_band": "VARCHAR(10)", "onboard_date": "DATE", "offboard_date": "DATE", "chain_flag": "BOOLEAN", "restaurant_rating": "DECIMAL(3,2)", "delivery_radius_km": "DECIMAL(6,2)"},
    "delivery_partners": {"partner_id": "BIGINT", "market_id": "INT", "city_id": "INT", "onboard_date": "DATE", "offboard_date": "DATE", "vehicle_type": "VARCHAR(30)", "partner_rating": "DECIMAL(3,2)"},
    "addresses": {"address_id": "BIGINT", "user_id": "BIGINT", "city_id": "INT", "zone_id": "VARCHAR(50)", "latitude": "DECIMAL(9,6)", "longitude": "DECIMAL(9,6)", "address_type": "VARCHAR(30)", "created_at": "TIMESTAMP"},
    "orders": {"order_id": "BIGINT", "user_id": "BIGINT", "restaurant_id": "BIGINT", "delivery_partner_id": "BIGINT", "market_id": "INT", "city_id": "INT", "address_id": "BIGINT", "order_timestamp": "TIMESTAMP", "promised_delivery_timestamp": "TIMESTAMP", "actual_delivery_timestamp": "TIMESTAMP", "order_status": "VARCHAR(30)", "subtotal": "DECIMAL(10,2)", "delivery_fee": "DECIMAL(10,2)", "tax": "DECIMAL(10,2)", "discount_amount": "DECIMAL(10,2)", "total_paid": "DECIMAL(10,2)", "cancelled_at": "TIMESTAMP", "cancellation_reason": "VARCHAR(100)"},
    "order_items": {"order_item_id": "BIGINT", "order_id": "BIGINT", "item_id": "BIGINT", "item_name": "VARCHAR(150)", "quantity": "INT", "unit_price": "DECIMAL(10,2)", "item_status": "VARCHAR(30)", "missing_item_flag": "BOOLEAN", "substitution_flag": "BOOLEAN"},
    "delivery_events": {"event_id": "BIGINT", "order_id": "BIGINT", "partner_id": "BIGINT", "event_type": "VARCHAR(40)", "event_timestamp": "TIMESTAMP", "latitude": "DECIMAL(9,6)", "longitude": "DECIMAL(9,6)"},
    "restaurant_availability": {"availability_id": "BIGINT", "restaurant_id": "BIGINT", "timestamp": "TIMESTAMP", "is_accepting_orders": "BOOLEAN", "estimated_prep_time_min": "INT", "capacity_status": "VARCHAR(30)"},
    "ratings": {"rating_id": "BIGINT", "order_id": "BIGINT", "user_id": "BIGINT", "restaurant_id": "BIGINT", "rating": "INT", "rating_timestamp": "TIMESTAMP", "review_text": "TEXT"},
    "order_issues": {"issue_id": "BIGINT", "order_id": "BIGINT", "issue_type": "VARCHAR(50)", "severity": "VARCHAR(20)", "reported_at": "TIMESTAMP", "resolved_at": "TIMESTAMP"},
    "refunds": {"refund_id": "BIGINT", "order_id": "BIGINT", "user_id": "BIGINT", "refund_amount": "DECIMAL(10,2)", "refund_type": "VARCHAR(30)", "refund_reason": "VARCHAR(100)", "refund_timestamp": "TIMESTAMP"},
    "promotions": {"promotion_id": "BIGINT", "promotion_name": "VARCHAR(100)", "promotion_type": "VARCHAR(40)", "discount_type": "VARCHAR(20)", "discount_value": "DECIMAL(10,2)", "minimum_order_value": "DECIMAL(10,2)", "maximum_discount": "DECIMAL(10,2)", "start_date": "DATE", "end_date": "DATE"},
    "order_promotions": {"order_id": "BIGINT", "promotion_id": "BIGINT", "discount_amount": "DECIMAL(10,2)"},
    "order_financials": {"order_id": "BIGINT", "restaurant_commission": "DECIMAL(10,2)", "delivery_revenue": "DECIMAL(10,2)", "service_fee": "DECIMAL(10,2)", "advertising_revenue": "DECIMAL(10,2)", "promotion_cost": "DECIMAL(10,2)", "delivery_partner_cost": "DECIMAL(10,2)", "payment_processing_cost": "DECIMAL(10,2)", "support_cost": "DECIMAL(10,2)", "contribution_margin": "DECIMAL(10,2)"},
}

TABLE_PRIMARY_KEYS: Final[dict[str, tuple[str, ...]]] = {
    table: ("order_id", "promotion_id") if table == "order_promotions" else (next(iter(columns)),)
    for table, columns in TABLE_SCHEMAS.items()
}

DELIVERY_EVENT_TYPES: Final[tuple[str, ...]] = (
    "ORDER_PLACED", "RESTAURANT_ACCEPTED", "PREPARATION_STARTED", "PARTNER_REQUESTED",
    "PARTNER_ASSIGNED", "PARTNER_ARRIVED", "ORDER_PICKED_UP", "ORDER_DELIVERED", "ORDER_CANCELLED",
)

ISSUE_TYPES: Final[tuple[str, ...]] = (
    "LATE_DELIVERY", "MISSING_ITEM", "WRONG_ITEM", "COLD_FOOD", "DAMAGED_FOOD",
    "RESTAURANT_QUALITY", "DRIVER_BEHAVIOR", "PAYMENT_ISSUE", "OTHER",
)

REFUND_TYPES: Final[tuple[str, ...]] = ("FULL", "PARTIAL", "ITEM_LEVEL", "DELIVERY_FEE", "GOODWILL")


def empty_table(table_name: str) -> pd.DataFrame:
    """Return an empty DataFrame conforming to a required table contract."""
    return pd.DataFrame({column: pd.Series(dtype=dtype) for column, dtype in TABLE_SCHEMAS[table_name].items()})
