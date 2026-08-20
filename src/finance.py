"""Order-level revenue, cost, and contribution-margin calculations."""

import numpy as np
import pandas as pd

from .config import GeneratorConfig
from .rng import RNGStreams
from .schemas import TABLE_SCHEMAS


def generate_order_financials(
    orders: pd.DataFrame,
    order_promotions: pd.DataFrame,
    refunds: pd.DataFrame,
    issues: pd.DataFrame,
    config: GeneratorConfig,
    rngs: RNGStreams,
) -> pd.DataFrame:
    """Calculate reconciled revenue, costs, and contribution margin per order."""
    random = rngs.for_module("finance")
    if orders.empty:
        return _cast_to_schema(pd.DataFrame(columns=TABLE_SCHEMAS["order_financials"]), "order_financials")
    promotion_cost = order_promotions.groupby("order_id")["discount_amount"].sum().reindex(orders["order_id"], fill_value=0).to_numpy(dtype=float)
    refund_cost = refunds.groupby("order_id")["refund_amount"].sum().reindex(orders["order_id"], fill_value=0).to_numpy(dtype=float)
    issue_counts = issues.groupby("order_id").size().reindex(orders["order_id"], fill_value=0).to_numpy(dtype=float)
    subtotal = orders["subtotal"].to_numpy(dtype=float)
    delivery_fee = orders["delivery_fee"].to_numpy(dtype=float)
    delivered = orders["order_status"].eq("DELIVERED").to_numpy()
    delivery_minutes = np.maximum(
        0,
        (orders["actual_delivery_timestamp"].fillna(orders["order_timestamp"]) - orders["order_timestamp"]).dt.total_seconds().to_numpy() / 60,
    )
    restaurant_commission = np.round(subtotal * np.where(delivered, 0.22, 0.08), 2)
    delivery_revenue = np.round(delivery_fee * np.where(delivered, 0.92, 0.25), 2)
    service_fee = np.round(np.maximum(0, subtotal * 0.055), 2)
    advertising_revenue = np.round(random.uniform(0, 1.75, len(orders)) * np.where(delivered, 1, 0.35), 2)
    delivery_partner_cost = np.round(
        np.where(delivered, 2.40 + 0.42 * delivery_minutes + random.normal(0, 0.35, len(orders)), 0.75),
        2,
    )
    delivery_partner_cost = np.maximum(0, delivery_partner_cost)
    payment_processing_cost = np.round(np.maximum(0, orders["total_paid"].to_numpy(dtype=float) * 0.029 + 0.30), 2)
    support_cost = np.round(0.12 + 2.25 * issue_counts + 0.18 * refund_cost + random.uniform(0, 0.35, len(orders)), 2)
    contribution_margin = np.round(
        restaurant_commission + delivery_revenue + service_fee + advertising_revenue
        - promotion_cost - delivery_partner_cost - payment_processing_cost - support_cost,
        2,
    )
    financials = pd.DataFrame(
        {
            "order_id": orders["order_id"].to_numpy(),
            "restaurant_commission": restaurant_commission,
            "delivery_revenue": delivery_revenue,
            "service_fee": service_fee,
            "advertising_revenue": advertising_revenue,
            "promotion_cost": np.round(promotion_cost, 2),
            "delivery_partner_cost": delivery_partner_cost,
            "payment_processing_cost": payment_processing_cost,
            "support_cost": support_cost,
            "contribution_margin": contribution_margin,
        }
    )
    return _cast_to_schema(financials, "order_financials")


def _cast_to_schema(table: pd.DataFrame, table_name: str) -> pd.DataFrame:
    from .schemas import TABLE_SCHEMAS

    schema = TABLE_SCHEMAS[table_name]
    table = table.loc[:, list(schema)].copy()
    for column, dtype in schema.items():
        if dtype.startswith("datetime"):
            table[column] = pd.to_datetime(table[column])
        else:
            table[column] = table[column].astype(dtype)
    return table
