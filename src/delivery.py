"""Delivery event state machine and operational performance generation."""

import numpy as np
import pandas as pd

from .config import GeneratorConfig
from .rng import RNGStreams
from .schemas import DELIVERY_EVENT_TYPES, TABLE_SCHEMAS


def generate_delivery_events(
    orders: pd.DataFrame,
    config: GeneratorConfig,
    rngs: RNGStreams,
) -> pd.DataFrame:
    """Create chronological event prefixes and terminal events for every order."""
    random = rngs.for_module("delivery")
    order_count = len(orders)
    if order_count == 0:
        return _cast_to_schema(pd.DataFrame(columns=TABLE_SCHEMAS["delivery_events"]), "delivery_events")

    delivered = orders["order_status"].eq("DELIVERED").to_numpy()
    order_ns = orders["order_timestamp"].astype("int64").to_numpy()
    actual_ns = orders["actual_delivery_timestamp"].fillna(orders["cancelled_at"]).astype("int64").to_numpy()
    duration_ns = np.maximum(actual_ns - order_ns, pd.Timedelta(minutes=1).value)

    # Small order-level pace variation keeps event timing heterogeneous while
    # sorting intermediate fractions preserves the lifecycle sequence.
    base_fractions = np.array([0.00, 0.12, 0.24, 0.40, 0.58, 0.72, 0.86, 1.00])
    intermediate = np.clip(
        base_fractions[1:7][None, :] + random.normal(0.0, 0.025, (order_count, 6)),
        0.02,
        0.96,
    )
    intermediate.sort(axis=1)
    fractions = np.column_stack([np.zeros(order_count), intermediate, np.ones(order_count)])
    timestamp_ns = order_ns[:, None] + (duration_ns[:, None] * fractions).astype(np.int64)
    timestamp_matrix = pd.to_datetime(timestamp_ns.ravel(), unit="ns").to_numpy().reshape(order_count, 8)

    event_matrix = np.full((order_count, 8), None, dtype=object)
    event_matrix[:, :7] = np.array(DELIVERY_EVENT_TYPES[:7], dtype=object)
    event_matrix[:, 7] = np.where(delivered, "ORDER_DELIVERED", "ORDER_CANCELLED")
    active_matrix = np.zeros((order_count, 8), dtype=bool)
    active_matrix[delivered, :] = True

    cancelled = ~delivered
    partner_assigned = orders["delivery_partner_id"].notna().to_numpy()
    cancellation_minutes = np.maximum(
        1,
        (orders["cancelled_at"].fillna(orders["order_timestamp"]).astype("int64").to_numpy() - order_ns) / 60_000_000_000,
    )
    prefix_length = np.clip((cancellation_minutes // 5).astype(int) + 1, 1, 7)
    prefix_length = np.where(partner_assigned, prefix_length, np.minimum(prefix_length, 4))
    for row_index in np.flatnonzero(cancelled):
        active_matrix[row_index, : prefix_length[row_index]] = True
        active_matrix[row_index, 7] = True

    partner_values = orders["delivery_partner_id"].astype("Int64").to_numpy()
    partner_matrix = np.full((order_count, 8), pd.NA, dtype=object)
    partner_event_slots = np.arange(8) >= 4
    partner_matrix[:, partner_event_slots] = partner_values[:, None]
    partner_matrix[~partner_assigned, :] = pd.NA
    partner_matrix[~active_matrix] = pd.NA

    flat_mask = active_matrix.ravel()
    flat_indices = np.flatnonzero(flat_mask)
    order_indices = flat_indices // 8
    slot_indices = flat_indices % 8
    events = pd.DataFrame(
        {
            "event_id": np.arange(1, len(flat_indices) + 1, dtype=np.int64),
            "order_id": orders.iloc[order_indices]["order_id"].to_numpy(),
            "partner_id": partner_matrix.ravel()[flat_indices],
            "event_type": event_matrix.ravel()[flat_indices],
            "event_timestamp": timestamp_matrix.ravel()[flat_indices],
            "latitude": np.nan,
            "longitude": np.nan,
        }
    )
    return _cast_to_schema(events, "delivery_events")


def _cast_to_schema(table: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """Apply the exact schema registry order and pandas dtypes."""
    schema = TABLE_SCHEMAS[table_name]
    table = table.loc[:, list(schema)].copy()
    for column, dtype in schema.items():
        if dtype.startswith("datetime"):
            table[column] = pd.to_datetime(table[column])
        else:
            table[column] = table[column].astype(dtype)
    return table
