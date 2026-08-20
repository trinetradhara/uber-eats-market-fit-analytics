"""Chunked order generation driven by users, restaurants, and operations."""

from collections.abc import Iterator

import numpy as np
import pandas as pd

from .availability import generate_restaurant_availability
from .behavior import UserBehaviorProfiles
from .config import GeneratorConfig
from .rng import RNGStreams


_CANCELLATION_REASONS = (
    "CUSTOMER_CHANGED_MIND",
    "RESTAURANT_UNAVAILABLE",
    "NO_DELIVERY_PARTNER",
    "LONG_PREP_TIME",
    "PAYMENT_FAILED",
)
_CUISINE_ITEM_PREFIXES = {
    "INDIAN": "Curry", "NORTH_INDIAN": "Tandoori", "SOUTH_INDIAN": "Dosa",
    "CHINESE": "Wok", "FAST_FOOD": "Classic", "DESSERT": "Sweet",
    "AMERICAN": "Grill", "MEXICAN": "Taco", "ITALIAN": "Pasta",
    "JAPANESE": "Sushi", "AUSTRALIAN": "Bistro", "THAI": "Thai",
    "CAFE": "Cafe", "BRITISH": "House", "SUSHI": "Sushi", "RAMEN": "Ramen",
    "KOREAN": "Seoul",
}


def iter_order_chunks(
    users: pd.DataFrame,
    restaurants: pd.DataFrame,
    delivery_partners: pd.DataFrame,
    addresses: pd.DataFrame,
    availability: pd.DataFrame,
    behavior: UserBehaviorProfiles,
    config: GeneratorConfig,
    rngs: RNGStreams,
) -> Iterator[pd.DataFrame]:
    """Yield order DataFrames in bounded chunks; does not write CSV files."""
    raise NotImplementedError


def generate_order_tables(
    users: pd.DataFrame,
    restaurants: pd.DataFrame,
    delivery_partners: pd.DataFrame,
    addresses: pd.DataFrame,
    availability: pd.DataFrame,
    behavior: UserBehaviorProfiles,
    restaurant_profiles: pd.DataFrame,
    config: GeneratorConfig,
    rngs: RNGStreams,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate exactly the configured orders and their one-or-more items."""
    random = rngs.for_module("orders")
    user_profiles = behavior.profiles.set_index("entity_id").reindex(users["user_id"])
    restaurant_profiles = restaurant_profiles.set_index("entity_id").reindex(restaurants["restaurant_id"])
    city_ids = users["home_city_id"].to_numpy()
    city_order_weights = users.assign(
        propensity=user_profiles["order_propensity"].to_numpy(),
    ).groupby("home_city_id")["propensity"].sum()
    restaurant_counts = restaurants.groupby("city_id").size()
    city_order_weights = city_order_weights * (1 + np.log1p(city_order_weights.index.map(restaurant_counts).fillna(0)))
    city_order_probabilities = city_order_weights / city_order_weights.sum()
    selected_cities = random.choice(city_order_weights.index.to_numpy(), size=config.target_orders, p=city_order_probabilities.to_numpy())

    users_by_city = {city_id: group.index.to_numpy() for city_id, group in users.groupby("home_city_id")}
    restaurants_by_city = {city_id: group.index.to_numpy() for city_id, group in restaurants.groupby("city_id")}
    partners_by_city = {city_id: group.index.to_numpy() for city_id, group in delivery_partners.groupby("city_id")}
    addresses_by_user = {user_id: group["address_id"].to_numpy() for user_id, group in addresses.groupby("user_id")}
    acceptance_rates = _availability_rates(availability)

    selected_user_indices = np.empty(config.target_orders, dtype=np.int64)
    selected_restaurant_indices = np.empty(config.target_orders, dtype=np.int64)
    selected_partner_indices = np.full(config.target_orders, -1, dtype=np.int64)
    for city_id in city_order_weights.index:
        order_positions = np.flatnonzero(selected_cities == city_id)
        if not len(order_positions):
            continue
        user_pool = users_by_city[city_id]
        user_weights = user_profiles.iloc[user_pool]["order_propensity"].to_numpy(dtype=float)
        user_weights = np.maximum(user_weights, 0.002)
        user_weights /= user_weights.sum()
        selected_user_indices[order_positions] = random.choice(user_pool, len(order_positions), p=user_weights)
        restaurant_pool = restaurants_by_city[city_id]
        popularity = restaurant_profiles.iloc[restaurant_pool]["expected_order_volume"].to_numpy(dtype=float)
        acceptance = np.array([acceptance_rates.get((int(restaurants.iloc[index].restaurant_id), 13), 0.8) for index in restaurant_pool])
        acceptance += np.array([acceptance_rates.get((int(restaurants.iloc[index].restaurant_id), 20), 0.8) for index in restaurant_pool])
        restaurant_weights = np.maximum(popularity, 0.001) * np.maximum(acceptance / 2, 0.05)
        restaurant_weights /= restaurant_weights.sum()
        selected_restaurant_indices[order_positions] = random.choice(restaurant_pool, len(order_positions), p=restaurant_weights)
        partner_pool = partners_by_city.get(city_id, np.array([], dtype=np.int64))
        if len(partner_pool):
            selected_partner_indices[order_positions] = random.choice(partner_pool, len(order_positions))

    selected_users = users.iloc[selected_user_indices].reset_index(drop=True)
    selected_restaurants = restaurants.iloc[selected_restaurant_indices].reset_index(drop=True)
    selected_restaurant_profiles = restaurant_profiles.iloc[selected_restaurant_indices].reset_index(drop=True)
    selected_user_profiles = user_profiles.iloc[selected_user_indices].reset_index(drop=True)
    order_timestamps = _generate_order_timestamps(selected_users, selected_user_profiles, random, config)
    meal_hours = order_timestamps.dt.hour.to_numpy()
    availability_for_orders = np.array([
        acceptance_rates.get((int(restaurant_id), 13 if hour < 16 else 20), 0.8)
        for restaurant_id, hour in zip(selected_restaurants["restaurant_id"], meal_hours)
    ])
    stress = np.clip(1 - availability_for_orders, 0, 1)
    cancellation_probability = np.clip(
        0.035 + 0.045 * stress + 0.018 * (1 - selected_restaurant_profiles["operational_reliability"].to_numpy(dtype=float)),
        0.02,
        0.18,
    )
    cancelled = random.random(config.target_orders) < cancellation_probability
    no_partner = random.random(config.target_orders) < 0.012
    selected_partner_indices[cancelled & no_partner] = -1
    selected_partners = delivery_partners.iloc[np.maximum(selected_partner_indices, 0)].reset_index(drop=True)

    items, subtotals = _generate_items(selected_restaurants, selected_user_profiles, selected_restaurant_profiles, random)
    delivery_fee = np.round(np.clip(1.25 + 0.75 * stress + random.lognormal(-1.0, 0.35, config.target_orders), 0.75, 12.0), 2)
    tax_rates = selected_restaurants["market_id"].map({1: 0.05, 2: 0.085, 3: 0.10, 4: 0.20, 5: 0.10}).to_numpy(dtype=float)
    tax = np.round(subtotals * tax_rates, 2)
    discount_probability = np.clip(0.08 + 0.30 * selected_user_profiles["promotion_affinity"].to_numpy(dtype=float), 0.05, 0.40)
    discounts = np.where(
        random.random(config.target_orders) < discount_probability,
        np.minimum(np.round(subtotals * random.uniform(0.05, 0.25, config.target_orders), 2), np.round(subtotals * 0.30, 2)),
        0.0,
    )
    total_paid = np.round(subtotals + delivery_fee + tax - discounts, 2)
    order_ids = np.arange(1, config.target_orders + 1, dtype=np.int64)
    promised_minutes = np.maximum(20, np.rint(28 + 18 * stress + random.normal(0, 4, config.target_orders)).astype(int))
    promised = order_timestamps + pd.to_timedelta(promised_minutes, unit="m")
    actual_delay = np.rint(random.normal(2 + 12 * stress, 8, config.target_orders)).astype(int)
    actual_duration = np.maximum(1, promised_minutes + actual_delay)
    actual = pd.Series(order_timestamps + pd.to_timedelta(actual_duration, unit="m"))
    actual[cancelled] = pd.NaT
    cancellation_reason = np.full(config.target_orders, None, dtype=object)
    cancellation_reason[cancelled] = random.choice(_CANCELLATION_REASONS, cancelled.sum(), p=[0.27, 0.24, 0.18, 0.22, 0.09])
    cancelled_at = pd.Series(order_timestamps.copy())
    cancelled_at[~cancelled] = pd.NaT
    cancellation_offset = random.integers(5, 35, config.target_orders)
    cancelled_at[cancelled] = order_timestamps[cancelled] + pd.to_timedelta(cancellation_offset[cancelled], unit="m")
    orders = pd.DataFrame(
        {
            "order_id": order_ids,
            "user_id": selected_users["user_id"].to_numpy(),
            "restaurant_id": selected_restaurants["restaurant_id"].to_numpy(),
            "delivery_partner_id": np.where(selected_partner_indices >= 0, selected_partners["partner_id"].to_numpy(), pd.NA),
            "market_id": selected_users["market_id"].to_numpy(),
            "city_id": selected_users["home_city_id"].to_numpy(),
            "address_id": [int(random.choice(addresses_by_user[int(user_id)])) for user_id in selected_users["user_id"]],
            "order_timestamp": order_timestamps,
            "promised_delivery_timestamp": promised,
            "actual_delivery_timestamp": actual,
            "order_status": np.where(cancelled, "CANCELLED", "DELIVERED"),
            "subtotal": subtotals,
            "delivery_fee": delivery_fee,
            "tax": tax,
            "discount_amount": discounts,
            "total_paid": total_paid,
            "cancelled_at": cancelled_at,
            "cancellation_reason": cancellation_reason,
        }
    )
    return _cast_to_schema(orders, "orders"), _cast_to_schema(items, "order_items")


def _availability_rates(availability: pd.DataFrame) -> dict[tuple[int, int], float]:
    grouped = availability.assign(hour=availability["timestamp"].dt.hour).groupby(["restaurant_id", "hour"])["is_accepting_orders"].mean()
    return {(int(restaurant_id), int(hour)): float(rate) for (restaurant_id, hour), rate in grouped.items()}


def _generate_order_timestamps(users: pd.DataFrame, profiles: pd.DataFrame, random: np.random.Generator, config: GeneratorConfig) -> pd.Series:
    signup = users["signup_timestamp"].dt.normalize().to_numpy()
    end = pd.Timestamp(config.end_date).normalize()
    day_span = np.maximum(0, (end.to_datetime64() - signup.astype("datetime64[ns]")).astype("timedelta64[D]").astype(int))
    day_offsets = np.array([random.integers(0, int(span) + 1) for span in day_span], dtype=np.int64)
    chosen_preference = profiles["preferred_order_daypart"].to_numpy()
    global_parts = random.choice(["BREAKFAST", "LUNCH", "DINNER", "LATE_NIGHT"], len(users), p=[0.08, 0.38, 0.48, 0.06])
    use_preference = random.random(len(users)) < 0.60
    meal_parts = np.where(use_preference, chosen_preference, global_parts)
    ranges = {"BREAKFAST": (7, 10), "LUNCH": (11, 14), "DINNER": (18, 21), "LATE_NIGHT": (22, 23)}
    hours = np.array([random.integers(ranges[part][0], ranges[part][1] + 1) for part in meal_parts])
    minutes = random.integers(0, 60, len(users))
    return pd.Series(pd.to_datetime(signup) + pd.to_timedelta(day_offsets, unit="D") + pd.to_timedelta(hours, unit="h") + pd.to_timedelta(minutes, unit="m"))


def _generate_items(restaurants: pd.DataFrame, user_profiles: pd.DataFrame, restaurant_profiles: pd.DataFrame, random: np.random.Generator) -> tuple[pd.DataFrame, np.ndarray]:
    rows: list[dict[str, object]] = []
    subtotals = np.zeros(len(restaurants), dtype=float)
    next_item_id = 1
    price_multipliers = {"LOW": 0.75, "MEDIUM": 1.0, "HIGH": 1.45, "PREMIUM": 2.1}
    for order_index, restaurant in enumerate(restaurants.itertuples(index=False)):
        price_band = str(restaurant.price_band)
        item_count = int(random.choice([1, 2, 3, 4], p=[0.48, 0.32, 0.15, 0.05]))
        prefix = _CUISINE_ITEM_PREFIXES.get(str(restaurant.cuisine_type), "House")
        subtotal = 0.0
        for item_number in range(item_count):
            quantity = int(random.choice([1, 2, 3], p=[0.80, 0.17, 0.03]))
            unit_price = round(float(np.clip(random.lognormal(np.log(9.5 * price_multipliers[price_band]), 0.35), 3.5, 85.0)), 2)
            missing = bool(random.random() < 0.012)
            substituted = bool((not missing) and random.random() < 0.012)
            item_status = "MISSING" if missing else "SUBSTITUTED" if substituted else "FULFILLED"
            rows.append(
                {
                    "order_item_id": next_item_id,
                    "order_id": order_index + 1,
                    "item_id": int(restaurant.restaurant_id) * 100 + item_number + 1,
                    "item_name": f"{prefix} Selection {item_number + 1}",
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "item_status": item_status,
                    "missing_item_flag": missing,
                    "substitution_flag": substituted,
                }
            )
            next_item_id += 1
            subtotal += quantity * unit_price
        subtotals[order_index] = round(subtotal, 2)
    return pd.DataFrame(rows), subtotals


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
