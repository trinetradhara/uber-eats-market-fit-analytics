"""Generate users, restaurants, partners, and addresses."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import GeneratorConfig
from .rng import RNGStreams


_ACQUISITION_CHANNELS = ("organic", "paid_search", "social", "referral", "partnership", "mobility_cross_sell", "direct")
_ACQUISITION_SOURCES = ("search_engine", "instagram", "friend_referral", "restaurant_partner", "uber_app", "app_store", "direct_web")
_CUISINES = {
    "India": ("INDIAN", "NORTH_INDIAN", "SOUTH_INDIAN", "CHINESE", "FAST_FOOD", "DESSERT"),
    "USA": ("AMERICAN", "MEXICAN", "ITALIAN", "CHINESE", "JAPANESE", "FAST_FOOD"),
    "Australia": ("AUSTRALIAN", "ITALIAN", "THAI", "JAPANESE", "MEXICAN", "CAFE"),
    "UK": ("BRITISH", "INDIAN", "ITALIAN", "CHINESE", "MEXICAN", "FAST_FOOD"),
    "Japan": ("JAPANESE", "SUSHI", "RAMEN", "ITALIAN", "KOREAN", "CAFE"),
}
_PRICE_BANDS = ("LOW", "MEDIUM", "HIGH", "PREMIUM")
_VEHICLE_TYPES = ("BICYCLE", "MOTORBIKE", "SCOOTER", "CAR")


@dataclass(frozen=True)
class EntityProfiles:
    """Internal profiles retained for downstream order and delivery generation."""

    profiles: pd.DataFrame


def generate_users(cities: pd.DataFrame, config: GeneratorConfig, rngs: RNGStreams) -> pd.DataFrame:
    """Create configured users with city-weighted acquisition and lifecycle fields."""
    random = rngs.for_module("entities")
    city_counts = _allocate_counts(cities, config.target_users, _user_city_weights(cities), random)
    city_rows = cities.loc[cities.index.repeat(city_counts)].reset_index(drop=True)
    user_count = len(city_rows)
    market_by_id = _market_config_by_id(config)
    market_names = city_rows["market_id"].map({key: value.name for key, value in market_by_id.items()})
    city_launch = pd.to_datetime(city_rows["launch_date"])
    lower_dates = pd.to_datetime(city_rows["launch_date"]).where(
        pd.to_datetime(city_rows["launch_date"]) > pd.Timestamp(config.start_date), pd.Timestamp(config.start_date)
    )
    signup = _random_timestamps(random, lower_dates, config.end_date)
    mobility_probability = market_names.map({"India": 0.16, "USA": 0.31, "Australia": 0.24, "UK": 0.27, "Japan": 0.20}).to_numpy()
    is_mobility = random.random(user_count) < mobility_probability
    channel_probabilities = random.random(user_count)
    channels = np.where(
        is_mobility & (channel_probabilities < 0.55), "mobility_cross_sell",
        np.select(
            [channel_probabilities < 0.28, channel_probabilities < 0.48, channel_probabilities < 0.63, channel_probabilities < 0.75, channel_probabilities < 0.88],
            ["organic", "paid_search", "social", "referral", "partnership"],
            default="direct",
        ),
    )
    source_map = dict(zip(_ACQUISITION_CHANNELS, _ACQUISITION_SOURCES))
    acquisition_sources = np.array([source_map[channel] for channel in channels], dtype=object)
    acquisition_sources[channels == "organic"] = "direct_web"
    acquisition_sources[channels == "mobility_cross_sell"] = "uber_app"
    mobility_dates = []
    membership_status = []
    membership_dates = []
    for index, signup_timestamp in enumerate(signup):
        if is_mobility[index]:
            mobility_dates.append(max(city_launch.iloc[index], signup_timestamp - pd.Timedelta(days=int(random.integers(0, 366)))).date())
        else:
            mobility_dates.append(pd.NaT)
        has_membership = random.random() < (0.08 + 0.25 * is_mobility[index])
        if has_membership:
            membership_status.append(random.choice(["ACTIVE", "PAUSED"], p=[0.86, 0.14]))
            membership_dates.append(min(signup_timestamp + pd.Timedelta(days=int(random.integers(0, 121))), pd.Timestamp(config.end_date)).date())
        else:
            membership_status.append(pd.NA)
            membership_dates.append(pd.NaT)
    users = pd.DataFrame(
        {
            "user_id": np.arange(1, user_count + 1, dtype=np.int64),
            "market_id": city_rows["market_id"].to_numpy(),
            "home_city_id": city_rows["city_id"].to_numpy(),
            "signup_timestamp": signup,
            "acquisition_channel": channels,
            "acquisition_source": acquisition_sources,
            "is_uber_mobility_user": is_mobility,
            "mobility_signup_date": mobility_dates,
            "membership_status": membership_status,
            "membership_start_date": membership_dates,
        }
    )
    return _cast_to_schema(users, "users")


def generate_addresses(users: pd.DataFrame, cities: pd.DataFrame, config: GeneratorConfig, rngs: RNGStreams) -> pd.DataFrame:
    """Create deterministic, city-local user addresses without changing users."""
    random = rngs.for_module("entities")
    city_lookup = cities.set_index("city_id")
    address_rows: list[dict[str, object]] = []
    address_id = 1
    for user in users.itertuples(index=False):
        address_count = int(random.choice([1, 2, 3, 4], p=[0.80, 0.16, 0.035, 0.005]))
        city = city_lookup.loc[user.home_city_id]
        signup = pd.Timestamp(user.signup_timestamp)
        address_types = random.choice(["HOME", "WORK", "OTHER"], size=address_count, p=[0.72, 0.20, 0.08])
        if "HOME" not in address_types:
            address_types[0] = "HOME"
        used_locations: set[tuple[float, float, str]] = set()
        for address_index in range(address_count):
            for _ in range(10):
                radius = float(random.lognormal(mean=-3.4, sigma=0.55))
                angle = float(random.uniform(0, 2 * np.pi))
                latitude = float(city.latitude + radius * np.cos(angle))
                longitude_scale = max(np.cos(np.radians(float(city.latitude))), 0.2)
                longitude = float(city.longitude + radius * np.sin(angle) / longitude_scale)
                key = (round(latitude, 6), round(longitude, 6), str(address_types[address_index]))
                if key not in used_locations:
                    used_locations.add(key)
                    break
            else:
                raise ValueError(f"Could not create a unique address for user {user.user_id}")
            created_at = signup + pd.Timedelta(days=int(random.integers(0, 180)), minutes=int(random.integers(0, 1440)))
            zone_lat = int(np.floor((latitude - float(city.latitude)) / 0.02))
            zone_lon = int(np.floor((longitude - float(city.longitude)) / 0.02))
            address_rows.append(
                {
                    "address_id": address_id,
                    "user_id": int(user.user_id),
                    "city_id": int(user.home_city_id),
                    "zone_id": f"CITY{int(user.home_city_id):03d}_Z{zone_lat:+03d}_{zone_lon:+03d}",
                    "latitude": round(latitude, 6),
                    "longitude": round(longitude, 6),
                    "address_type": str(address_types[address_index]),
                    "created_at": created_at,
                }
            )
            address_id += 1
    return _cast_to_schema(pd.DataFrame(address_rows), "addresses")


def generate_restaurants(cities: pd.DataFrame, config: GeneratorConfig, rngs: RNGStreams) -> pd.DataFrame:
    """Create city-weighted restaurants and retain a heavy-tailed latent profile."""
    random = rngs.for_module("entities")
    market_config = _market_config_by_id(config)
    weights = _restaurant_city_weights(cities, market_config)
    counts = _allocate_counts(cities, config.target_restaurants, weights, random)
    city_rows = cities.loc[cities.index.repeat(counts)].reset_index(drop=True)
    restaurant_count = len(city_rows)
    city_to_market_name = city_rows["market_id"].map({key: value.name for key, value in market_config.items()})
    cuisine_values = [random.choice(_CUISINES[market_name]) for market_name in city_to_market_name]
    price_values = random.choice(_PRICE_BANDS, restaurant_count, p=[0.24, 0.43, 0.25, 0.08])
    lower_dates = pd.to_datetime(city_rows["launch_date"]).where(
        pd.to_datetime(city_rows["launch_date"]) > pd.Timestamp(config.start_date), pd.Timestamp(config.start_date)
    )
    onboard = _random_timestamps(random, lower_dates, config.end_date).normalize()
    offboard = _optional_offboard_dates(random, onboard, config.end_date, 0.07)
    popularity = random.lognormal(mean=0.0, sigma=1.15, size=restaurant_count)
    city_demand = city_rows["population"].to_numpy(dtype=float) * np.sqrt(city_rows["population_density"].to_numpy(dtype=float))
    quality = np.clip(random.normal(4.05, 0.38, restaurant_count), 2.8, 4.95)
    profiles = pd.DataFrame(
        {
            "entity_id": np.arange(1, restaurant_count + 1, dtype=np.int64),
            "popularity_score": popularity,
            "expected_order_volume": popularity * city_demand / np.median(city_demand),
            "cuisine_attractiveness": np.clip(random.normal(0.65, 0.16, restaurant_count), 0.1, 1),
            "price_sensitivity": np.clip(random.normal(0.5, 0.18, restaurant_count), 0, 1),
            "operational_reliability": np.clip(random.normal(0.76, 0.12, restaurant_count), 0.25, 1),
            "preparation_speed": np.clip(random.normal(0.68, 0.15, restaurant_count), 0.2, 1),
            "delivery_demand_intensity": np.clip(random.normal(0.62, 0.18, restaurant_count), 0.1, 1),
            "capacity": np.maximum(10, random.lognormal(3.7, 0.45, restaurant_count).round().astype(int)),
            "quality_tendency": quality,
        }
    )
    profiles["popularity_segment"] = pd.qcut(profiles["popularity_score"], q=[0, 0.75, 0.95, 1], labels=["LOW_VOLUME", "MEDIUM_VOLUME", "HIGH_VOLUME"], duplicates="drop").astype("string")
    restaurants = pd.DataFrame(
        {
            "restaurant_id": profiles["entity_id"].to_numpy(),
            "market_id": city_rows["market_id"].to_numpy(),
            "city_id": city_rows["city_id"].to_numpy(),
            "restaurant_name": [f"{city} {cuisine.title()} Kitchen {index:05d}" for index, (city, cuisine) in enumerate(zip(city_rows["city_name"], cuisine_values), start=1)],
            "cuisine_type": cuisine_values,
            "price_band": price_values,
            "onboard_date": onboard,
            "offboard_date": offboard,
            "chain_flag": random.random(restaurant_count) < np.where(city_rows["urban_tier"].eq("TIER_1"), 0.28, 0.16),
            "restaurant_rating": quality.round(2),
            "delivery_radius_km": np.round(np.clip(random.lognormal(1.0, 0.35, restaurant_count), 1.0, 30.0), 2),
        }
    )
    restaurants = _cast_to_schema(restaurants, "restaurants")
    restaurants.attrs["latent_profiles"] = profiles
    return restaurants


def generate_delivery_partners(cities: pd.DataFrame, config: GeneratorConfig, rngs: RNGStreams) -> pd.DataFrame:
    """Create city-weighted partners and retain operational latent profiles."""
    random = rngs.for_module("entities")
    market_config = _market_config_by_id(config)
    weights = _partner_city_weights(cities, market_config)
    counts = _allocate_counts(cities, config.target_delivery_partners, weights, random)
    city_rows = cities.loc[cities.index.repeat(counts)].reset_index(drop=True)
    partner_count = len(city_rows)
    market_names = city_rows["market_id"].map({key: value.name for key, value in market_config.items()})
    vehicle_choices = []
    for market_name in market_names:
        probabilities = {"India": [0.08, 0.56, 0.30, 0.06], "USA": [0.08, 0.18, 0.10, 0.64], "Australia": [0.10, 0.20, 0.12, 0.58], "UK": [0.12, 0.25, 0.16, 0.47], "Japan": [0.18, 0.40, 0.24, 0.18]}[market_name]
        vehicle_choices.append(random.choice(_VEHICLE_TYPES, p=probabilities))
    lower_dates = pd.to_datetime(city_rows["launch_date"]).where(
        pd.to_datetime(city_rows["launch_date"]) > pd.Timestamp(config.start_date), pd.Timestamp(config.start_date)
    )
    onboard = _random_timestamps(random, lower_dates, config.end_date).normalize()
    offboard = _optional_offboard_dates(random, onboard, config.end_date, 0.055)
    reliability = np.clip(random.normal(0.76, 0.13, partner_count), 0.25, 1)
    profiles = pd.DataFrame(
        {
            "entity_id": np.arange(1, partner_count + 1, dtype=np.int64),
            "availability_propensity": np.clip(random.normal(0.70, 0.16, partner_count), 0.1, 1),
            "speed_tendency": np.clip(random.normal(0.68, 0.14, partner_count), 0.15, 1),
            "acceptance_tendency": np.clip(random.normal(0.75, 0.13, partner_count), 0.2, 1),
            "reliability": reliability,
            "experience": np.clip(random.beta(3.0, 2.0, partner_count), 0.05, 1),
            "preferred_operating_hours": random.choice(["MORNING", "DAY", "EVENING", "LATE_NIGHT"], partner_count),
            "vehicle_type": vehicle_choices,
        }
    )
    partners = pd.DataFrame(
        {
            "partner_id": profiles["entity_id"].to_numpy(),
            "market_id": city_rows["market_id"].to_numpy(),
            "city_id": city_rows["city_id"].to_numpy(),
            "onboard_date": onboard,
            "offboard_date": offboard,
            "vehicle_type": vehicle_choices,
            "partner_rating": np.round(np.clip(3.1 + 1.5 * reliability + random.normal(0, 0.16, partner_count), 2.5, 4.98), 2),
        }
    )
    partners = _cast_to_schema(partners, "delivery_partners")
    partners.attrs["latent_profiles"] = profiles
    return partners


def _market_config_by_id(config: GeneratorConfig) -> dict[int, object]:
    return {market_id: market for market_id, market in enumerate(config.markets, start=1)}


def _user_city_weights(cities: pd.DataFrame) -> np.ndarray:
    return cities["population"].to_numpy(dtype=float) * np.sqrt(cities["population_density"].to_numpy(dtype=float))


def _restaurant_city_weights(cities: pd.DataFrame, market_config: dict[int, object]) -> np.ndarray:
    market_density = cities["market_id"].map({key: value.restaurant_density for key, value in market_config.items()}).to_numpy(dtype=float)
    return cities["population"].to_numpy(dtype=float) * np.power(cities["population_density"].to_numpy(dtype=float), 0.25) * market_density


def _partner_city_weights(cities: pd.DataFrame, market_config: dict[int, object]) -> np.ndarray:
    partner_density = cities["market_id"].map({key: value.partner_density for key, value in market_config.items()}).to_numpy(dtype=float)
    restaurant_density = cities["market_id"].map({key: value.restaurant_density for key, value in market_config.items()}).to_numpy(dtype=float)
    demand = _user_city_weights(cities)
    supply_adjustment = 0.75 + 0.25 * restaurant_density
    return demand * partner_density * supply_adjustment


def _allocate_counts(cities: pd.DataFrame, target: int, weights: np.ndarray, random: np.random.Generator) -> np.ndarray:
    if target < len(cities):
        raise ValueError(f"Target {target} is smaller than the {len(cities)} available cities")
    counts = np.ones(len(cities), dtype=int)
    remaining = target - len(cities)
    if remaining:
        probabilities = weights / weights.sum()
        counts += random.multinomial(remaining, probabilities)
    return counts


def _random_timestamps(random: np.random.Generator, lower_dates: pd.Series, end_date: object) -> pd.DatetimeIndex:
    lower_ns = pd.to_datetime(lower_dates).astype("int64").to_numpy()
    upper_ns = pd.Timestamp(end_date).normalize().value + pd.Timedelta(days=1).value
    if (lower_ns >= upper_ns).any():
        raise ValueError("Generation end date must be after every entity lower date")
    values = lower_ns + (random.random(len(lower_ns)) * (upper_ns - lower_ns)).astype(np.int64)
    return pd.to_datetime(values)


def _optional_offboard_dates(random: np.random.Generator, onboard: pd.Series, end_date: object, rate: float) -> list[object]:
    end = pd.Timestamp(end_date).normalize()
    result = []
    for onboard_date in pd.to_datetime(onboard):
        if random.random() < rate:
            days = int(random.integers(30, 366))
            result.append(min(onboard_date + pd.Timedelta(days=days), end).date())
        else:
            result.append(pd.NaT)
    return result


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


def save_entity_profiles(profiles: pd.DataFrame, path: Path) -> None:
    """Persist restaurant or delivery-partner latent profiles as Parquet."""
    path.parent.mkdir(parents=True, exist_ok=True)
    profiles.to_parquet(path, index=False)


def load_entity_profiles(path: Path) -> pd.DataFrame:
    """Load a persisted restaurant or delivery-partner profile artifact."""
    return pd.read_parquet(path)
