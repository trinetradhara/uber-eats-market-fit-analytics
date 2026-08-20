"""Promotion eligibility, redemption, and discount-dependence logic."""

import numpy as np
import pandas as pd

from .config import GeneratorConfig
from .rng import RNGStreams
from .schemas import TABLE_SCHEMAS


def generate_promotions(markets: pd.DataFrame, config: GeneratorConfig, rngs: RNGStreams) -> pd.DataFrame:
    """Create dated market promotions with varied discount mechanics."""
    random = rngs.for_module("promotions")
    rows: list[dict[str, object]] = []
    promotion_id = 1
    promotion_types = ("FIRST_ORDER", "WEEKDAY", "WEEKEND", "MEMBERSHIP", "REACTIVATION")
    for market in markets.itertuples(index=False):
        for promotion_number in range(12):
            discount_type = str(random.choice(["PERCENTAGE", "FIXED_AMOUNT"], p=[0.68, 0.32]))
            discount_value = round(float(random.uniform(8, 25) if discount_type == "PERCENTAGE" else random.uniform(2, 8)), 2)
            minimum = round(float(random.choice([0, 10, 15, 20, 30], p=[0.18, 0.20, 0.26, 0.24, 0.12])), 2)
            maximum = round(float(random.uniform(5, 18)), 2) if discount_type == "PERCENTAGE" else np.nan
            start = pd.Timestamp(config.start_date) + pd.Timedelta(days=int(random.integers(0, 600)))
            end = min(start + pd.Timedelta(days=int(random.integers(45, 180))), pd.Timestamp(config.end_date))
            rows.append(
                {
                    "promotion_id": promotion_id,
                    "promotion_name": f"{market.country} {promotion_types[promotion_number % len(promotion_types)]} {promotion_number + 1:02d}",
                    "promotion_type": promotion_types[promotion_number % len(promotion_types)],
                    "discount_type": discount_type,
                    "discount_value": discount_value,
                    "minimum_order_value": minimum,
                    "maximum_discount": maximum,
                    "start_date": start.date(),
                    "end_date": end.date(),
                }
            )
            promotion_id += 1
    return _cast_to_schema(pd.DataFrame(rows), "promotions")


def generate_order_promotions(
    orders: pd.DataFrame,
    promotions: pd.DataFrame,
    config: GeneratorConfig,
    rngs: RNGStreams,
) -> pd.DataFrame:
    """Redeem eligible promotions, bounded by each order's existing discount."""
    random = rngs.for_module("promotions")
    if orders.empty or promotions.empty:
        return _cast_to_schema(pd.DataFrame(columns=TABLE_SCHEMAS["order_promotions"]), "order_promotions")
    market_promotions = {market_id: group for market_id, group in promotions.groupby("promotion_id")}
    promotion_lookup = promotions.set_index("promotion_id")
    rows: list[dict[str, object]] = []
    for order in orders.itertuples(index=False):
        if order.discount_amount <= 0 or random.random() > 0.82:
            continue
        eligible = promotions[
            (promotions["start_date"] <= pd.Timestamp(order.order_timestamp))
            & (promotions["end_date"] >= pd.Timestamp(order.order_timestamp))
            & (promotions["minimum_order_value"] <= order.subtotal)
        ]
        if eligible.empty:
            continue
        selected = eligible.iloc[int(random.integers(0, len(eligible)))]
        discount = min(float(order.discount_amount), _promotion_discount(selected, float(order.subtotal)))
        if discount <= 0:
            continue
        rows.append({"order_id": int(order.order_id), "promotion_id": int(selected.promotion_id), "discount_amount": round(discount, 2)})
    return _cast_to_schema(pd.DataFrame(rows), "order_promotions")


def _promotion_discount(promotion: pd.Series, subtotal: float) -> float:
    if promotion["discount_type"] == "PERCENTAGE":
        return min(subtotal * float(promotion["discount_value"]) / 100, float(promotion["maximum_discount"]))
    return float(promotion["discount_value"])


def _cast_to_schema(table: pd.DataFrame, table_name: str) -> pd.DataFrame:
    schema = TABLE_SCHEMAS[table_name]
    table = table.loc[:, list(schema)].copy()
    for column, dtype in schema.items():
        if dtype.startswith("datetime"):
            table[column] = pd.to_datetime(table[column])
        else:
            table[column] = table[column].astype(dtype)
    return table
