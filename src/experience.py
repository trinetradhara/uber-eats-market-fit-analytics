"""Post-order ratings, issues, and refunds derived from order experience."""

import numpy as np
import pandas as pd

from .config import GeneratorConfig
from .rng import RNGStreams
from .schemas import ISSUE_TYPES, REFUND_TYPES, TABLE_SCHEMAS


def generate_ratings(
    orders: pd.DataFrame,
    config: GeneratorConfig,
    rngs: RNGStreams,
    user_profiles: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Generate a probabilistic subset of ratings for delivered orders."""
    random = rngs.for_module("experience")
    delivered = orders[orders["order_status"].eq("DELIVERED")].reset_index(drop=True)
    if delivered.empty:
        return _cast_to_schema(pd.DataFrame(columns=TABLE_SCHEMAS["ratings"]), "ratings")
    if user_profiles is not None:
        profile = user_profiles.set_index("entity_id").reindex(delivered["user_id"])
        rating_probability = np.clip(0.28 + 0.52 * profile["rating_propensity"].to_numpy(dtype=float), 0.10, 0.92)
    else:
        rating_probability = np.full(len(delivered), 0.62)
    rated = random.random(len(delivered)) < rating_probability
    selected = delivered.loc[rated].reset_index(drop=True)
    if selected.empty:
        return _cast_to_schema(pd.DataFrame(columns=TABLE_SCHEMAS["ratings"]), "ratings")
    late_minutes = np.maximum(
        0,
        (selected["actual_delivery_timestamp"] - selected["promised_delivery_timestamp"]).dt.total_seconds().to_numpy() / 60,
    )
    experience_score = np.clip(4.35 - 0.045 * late_minutes + random.normal(0, 0.55, len(selected)), 1, 5)
    rating_values = np.rint(experience_score).astype(int)
    rating_timestamp = selected["actual_delivery_timestamp"] + pd.to_timedelta(random.integers(1, 73, len(selected)), unit="h")
    ratings = pd.DataFrame(
        {
            "rating_id": np.arange(1, len(selected) + 1, dtype=np.int64),
            "order_id": selected["order_id"].to_numpy(),
            "user_id": selected["user_id"].to_numpy(),
            "restaurant_id": selected["restaurant_id"].to_numpy(),
            "rating": rating_values,
            "rating_timestamp": rating_timestamp.to_numpy(),
            "review_text": np.where(rating_values >= 4, "Good order experience", np.where(rating_values <= 2, "Order experience needs improvement", "Average order experience")),
        }
    )
    return _cast_to_schema(ratings, "ratings")


def generate_order_issues(
    orders: pd.DataFrame,
    config: GeneratorConfig,
    rngs: RNGStreams,
    delivery_events: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Generate issue reports from delays, cancellations, and order context."""
    random = rngs.for_module("experience")
    terminal = orders["actual_delivery_timestamp"].fillna(orders["cancelled_at"])
    late_minutes = np.maximum(
        0,
        (orders["actual_delivery_timestamp"] - orders["promised_delivery_timestamp"]).dt.total_seconds().fillna(0).to_numpy() / 60,
    )
    cancelled = orders["order_status"].eq("CANCELLED").to_numpy()
    issue_probability = np.clip(0.025 + 0.0018 * late_minutes + 0.035 * cancelled, 0.02, 0.24)
    reported = random.random(len(orders)) < issue_probability
    selected = orders.loc[reported].reset_index(drop=True)
    if selected.empty:
        return _cast_to_schema(pd.DataFrame(columns=TABLE_SCHEMAS["order_issues"]), "order_issues")
    selected_late = late_minutes[reported]
    selected_cancelled = cancelled[reported]
    issue_type = np.empty(len(selected), dtype=object)
    for index, (late, was_cancelled) in enumerate(zip(selected_late, selected_cancelled)):
        probabilities = np.array([0.42 if late > 10 else 0.16, 0.14, 0.10, 0.12 if late > 20 else 0.05, 0.05, 0.07, 0.05, 0.03, 0.02], dtype=float)
        if was_cancelled:
            probabilities = probabilities * np.array([0.35, 0.20, 0.10, 0.10, 0.05, 0.05, 0.05, 0.25, 0.10])
        probabilities /= probabilities.sum()
        issue_type[index] = random.choice(ISSUE_TYPES, p=probabilities)
    severity = random.choice(["LOW", "MEDIUM", "HIGH"], len(selected), p=[0.55, 0.35, 0.10])
    order_start = selected["order_timestamp"].to_numpy()
    terminal_selected = terminal[reported].to_numpy()
    duration_ns = np.maximum(terminal_selected.astype("datetime64[ns]").astype("int64") - order_start.astype("datetime64[ns]").astype("int64"), pd.Timedelta(minutes=1).value)
    report_fraction = random.uniform(0.35, 0.95, len(selected))
    reported_at = pd.to_datetime(order_start.astype("datetime64[ns]").astype("int64") + (duration_ns * report_fraction).astype(np.int64))
    resolved = random.random(len(selected)) < 0.82
    resolved_at = pd.Series(reported_at + pd.to_timedelta(random.integers(1, 73, len(selected)), unit="h"))
    resolved_at[~resolved] = pd.NaT
    issues = pd.DataFrame(
        {
            "issue_id": np.arange(1, len(selected) + 1, dtype=np.int64),
            "order_id": selected["order_id"].to_numpy(),
            "issue_type": issue_type,
            "severity": severity,
            "reported_at": reported_at,
            "resolved_at": resolved_at,
        }
    )
    return _cast_to_schema(issues, "order_issues")


def generate_refunds(
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    issues: pd.DataFrame,
    config: GeneratorConfig,
    rngs: RNGStreams,
) -> pd.DataFrame:
    """Generate bounded refunds linked to issues and optional order items."""
    random = rngs.for_module("experience")
    if issues.empty:
        return _cast_to_schema(pd.DataFrame(columns=TABLE_SCHEMAS["refunds"]), "refunds")
    order_lookup = orders.set_index("order_id")
    issue_orders = issues["order_id"].to_numpy()
    severity_probability = issues["severity"].map({"LOW": 0.22, "MEDIUM": 0.48, "HIGH": 0.78}).to_numpy(dtype=float)
    refund_mask = random.random(len(issues)) < severity_probability
    selected_issues = issues.loc[refund_mask].reset_index(drop=True)
    if selected_issues.empty:
        return _cast_to_schema(pd.DataFrame(columns=TABLE_SCHEMAS["refunds"]), "refunds")
    selected_orders = order_lookup.loc[selected_issues["order_id"]].reset_index()
    refund_type = random.choice(REFUND_TYPES, len(selected_issues), p=[0.08, 0.44, 0.16, 0.18, 0.14])
    base_amount = selected_orders["total_paid"].to_numpy(dtype=float)
    fraction = np.where(refund_type == "FULL", 1.0, random.uniform(0.08, 0.55, len(selected_issues)))
    refund_amount = np.round(np.minimum(base_amount, np.maximum(0.50, base_amount * fraction)), 2)
    refund_timestamp = selected_issues["reported_at"] + pd.to_timedelta(random.integers(1, 97, len(selected_issues)), unit="h")
    refunds = pd.DataFrame(
        {
            "refund_id": np.arange(1, len(selected_issues) + 1, dtype=np.int64),
            "order_id": selected_issues["order_id"].to_numpy(),
            "user_id": selected_orders["user_id"].to_numpy(),
            "refund_amount": refund_amount,
            "refund_type": refund_type,
            "refund_reason": selected_issues["issue_type"].to_numpy(),
            "refund_timestamp": refund_timestamp.to_numpy(),
        }
    )
    return _cast_to_schema(refunds, "refunds")


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
