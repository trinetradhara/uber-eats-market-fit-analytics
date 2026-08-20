"""Restaurant operating availability and supply snapshots."""

import numpy as np
import pandas as pd

from .config import GeneratorConfig
from .rng import RNGStreams


def generate_restaurant_availability(
    restaurants: pd.DataFrame,
    cities: pd.DataFrame,
    config: GeneratorConfig,
    rngs: RNGStreams,
) -> pd.DataFrame:
    """Create four deterministic weekly operational snapshots per restaurant.

    Snapshots cover Wednesday lunch, Wednesday dinner, Saturday lunch, and
    Saturday dinner. This compact representation is sufficient for future
    order timestamps to map to weekday/weekend and peak meal conditions.
    """
    random = rngs.for_module("availability")
    profile = restaurants.attrs.get("latent_profiles")
    if profile is None:
        raise ValueError("Restaurant latent profiles are required for availability generation")
    profile = profile.set_index("entity_id").reindex(restaurants["restaurant_id"])
    weeks = pd.date_range(config.start_date, config.end_date, freq="7D")
    snapshot_offsets = ((2, 13), (2, 20), (5, 13), (5, 20))
    restaurant_count = len(restaurants)
    snapshot_count = len(weeks) * len(snapshot_offsets)
    total_rows = restaurant_count * snapshot_count
    restaurant_positions = np.repeat(np.arange(restaurant_count), snapshot_count)
    week_positions = np.tile(np.repeat(np.arange(len(weeks)), len(snapshot_offsets)), restaurant_count)
    offset_positions = np.tile(np.arange(len(snapshot_offsets)), restaurant_count * len(weeks))
    offset_days = np.array([offset[0] for offset in snapshot_offsets])
    offset_hours = np.array([offset[1] for offset in snapshot_offsets])
    timestamps = pd.to_datetime(weeks.to_numpy()[week_positions]) + pd.to_timedelta(offset_days[offset_positions], unit="D") + pd.to_timedelta(offset_hours[offset_positions], unit="h")
    in_range = timestamps <= pd.Timestamp(config.end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    restaurant_positions = restaurant_positions[in_range]
    timestamps = timestamps[in_range]
    offset_positions = offset_positions[in_range]
    restaurant_frame = restaurants.iloc[restaurant_positions].reset_index(drop=True)
    selected_profile = profile.iloc[restaurant_positions].reset_index(drop=True)
    city_density = cities.set_index("city_id").loc[restaurant_frame["city_id"], "population_density"].to_numpy(dtype=float)
    city_stress = np.clip(np.log1p(city_density) / 12.0, 0.15, 1.0)
    peak = np.isin(offset_positions, [1, 3])
    weekend = np.isin(offset_positions, [2, 3])
    stress = np.clip(
        0.18 + 0.28 * peak + 0.12 * weekend + 0.20 * city_stress
        + 0.26 * (1 - selected_profile["operational_reliability"].to_numpy(dtype=float))
        + random.normal(0, 0.08, len(restaurant_frame)),
        0,
        1,
    )
    capacity_score = np.clip(stress + random.normal(0, 0.06, len(restaurant_frame)), 0, 1)
    capacity_status = np.select(
        [capacity_score < 0.34, capacity_score < 0.58, capacity_score < 0.80],
        ["NORMAL", "BUSY", "HIGH"],
        default="FULL",
    )
    accepting = (capacity_status != "FULL") | (random.random(len(restaurant_frame)) < 0.08)
    base_prep = 24 + 16 * (1 - selected_profile["preparation_speed"].to_numpy(dtype=float))
    prep_time = np.maximum(10, np.rint(base_prep + 14 * stress + random.normal(0, 3, len(restaurant_frame))).astype(int))
    prep_time = np.where(accepting, prep_time, pd.NA)
    availability = pd.DataFrame(
        {
            "availability_id": np.arange(1, len(restaurant_frame) + 1, dtype=np.int64),
            "restaurant_id": restaurant_frame["restaurant_id"].to_numpy(),
            "timestamp": timestamps,
            "is_accepting_orders": accepting,
            "estimated_prep_time_min": prep_time,
            "capacity_status": capacity_status,
        }
    )
    return _cast_to_schema(availability, "restaurant_availability")


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
