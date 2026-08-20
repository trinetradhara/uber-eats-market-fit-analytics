"""Orchestration entry point for the implemented dimension stages."""

import pandas as pd

from .availability import generate_restaurant_availability
from .behavior import build_user_behavior, load_user_profiles, save_user_profiles
from .config import CONFIG, GeneratorConfig
from .delivery import generate_delivery_events
from .entities import generate_addresses, generate_delivery_partners, generate_restaurants, generate_users, load_entity_profiles, save_entity_profiles
from .experience import generate_order_issues, generate_ratings, generate_refunds
from .finance import generate_order_financials
from .markets import generate_cities, generate_markets
from .orders import generate_order_tables, iter_order_chunks
from .promotions import generate_order_promotions, generate_promotions
from .rng import create_rngs
from .export import export_tables
from .validation import validate_entities, validate_entity_distributions, validate_markets_and_cities, validate_stage3, validate_stage4, validate_stage5, validate_stage6, validate_stage7, validate_stage8

GENERATION_ORDER = (
    "markets", "cities", "users", "addresses", "restaurants", "delivery_partners",
    "promotions", "restaurant_availability", "user_behavior_profiles", "orders",
    "order_items", "delivery_events", "ratings", "order_issues", "refunds",
    "order_promotions", "order_financials", "validation", "csv_export",
)


def describe_generation_plan(config: GeneratorConfig = CONFIG) -> tuple[str, ...]:
    """Return the intended dependency order without generating records."""
    return GENERATION_ORDER


def generate_market_city_stage(config: GeneratorConfig = CONFIG) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate, validate, and export only the market and city dimensions."""
    rngs = create_rngs(config.master_seed)
    markets = generate_markets(config, rngs)
    cities = generate_cities(markets, config, rngs)
    errors = validate_markets_and_cities(markets, cities)
    if errors:
        raise ValueError("Markets and cities validation failed: " + "; ".join(errors))
    export_tables({"markets": markets, "cities": cities}, config.output_root / "raw")
    return markets, cities


def load_market_city_inputs(config: GeneratorConfig = CONFIG) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the previously generated market and city CSVs."""
    raw_dir = config.output_root / "raw"
    markets = pd.read_csv(raw_dir / "markets.csv", parse_dates=["launch_date", "exit_date"])
    cities = pd.read_csv(raw_dir / "cities.csv", parse_dates=["launch_date"])
    return markets, cities


def generate_entity_stage(
    config: GeneratorConfig = CONFIG,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate, validate, and export users, restaurants, and partners only."""
    markets, cities = load_market_city_inputs(config)
    dimension_errors = validate_markets_and_cities(markets, cities)
    if dimension_errors:
        raise ValueError("Market and city inputs failed validation: " + "; ".join(dimension_errors))
    rngs = create_rngs(config.master_seed)
    users = generate_users(cities, config, rngs)
    user_behavior = build_user_behavior(users, config, rngs)
    restaurants = generate_restaurants(cities, config, rngs)
    partners = generate_delivery_partners(cities, config, rngs)
    errors = validate_entities(users, restaurants, partners, markets, cities, config)
    errors.extend(validate_entity_distributions(users, restaurants, partners, user_behavior.profiles, restaurants.attrs["latent_profiles"]))
    if errors:
        raise ValueError("Entity stage validation failed: " + "; ".join(errors))
    export_tables(
        {"users": users, "restaurants": restaurants, "delivery_partners": partners},
        config.output_root / "raw",
    )
    processed_dir = config.output_root / "processed"
    save_user_profiles(user_behavior, processed_dir / "user_profiles.parquet")
    save_entity_profiles(restaurants.attrs["latent_profiles"], processed_dir / "restaurant_profiles.parquet")
    save_entity_profiles(partners.attrs["latent_profiles"], processed_dir / "partner_profiles.parquet")
    users.attrs["latent_behavior"] = user_behavior.profiles
    return users, restaurants, partners, user_behavior.profiles


def generate_stage3(config: GeneratorConfig = CONFIG) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate and export only addresses and restaurant availability."""
    markets, cities = load_market_city_inputs(config)
    raw_dir = config.output_root / "raw"
    processed_dir = config.output_root / "processed"
    users = pd.read_csv(raw_dir / "users.csv", parse_dates=["signup_timestamp", "mobility_signup_date", "membership_start_date"])
    restaurants = pd.read_csv(raw_dir / "restaurants.csv", parse_dates=["onboard_date", "offboard_date"])
    restaurants.attrs["latent_profiles"] = load_entity_profiles(processed_dir / "restaurant_profiles.parquet")
    rngs = create_rngs(config.master_seed)
    addresses = generate_addresses(users, cities, config, rngs)
    availability = generate_restaurant_availability(restaurants, cities, config, rngs)
    errors = validate_stage3(addresses, availability, users, restaurants, cities, config)
    if errors:
        raise ValueError("Stage 3 validation failed: " + "; ".join(errors))
    export_tables({"addresses": addresses, "restaurant_availability": availability}, raw_dir)
    return addresses, availability


def generate_stage4(config: GeneratorConfig = CONFIG) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate and export only orders and order items."""
    markets, cities = load_market_city_inputs(config)
    raw_dir = config.output_root / "raw"
    processed_dir = config.output_root / "processed"
    users = pd.read_csv(raw_dir / "users.csv", parse_dates=["signup_timestamp", "mobility_signup_date", "membership_start_date"])
    restaurants = pd.read_csv(raw_dir / "restaurants.csv", parse_dates=["onboard_date", "offboard_date"])
    partners = pd.read_csv(raw_dir / "delivery_partners.csv", parse_dates=["onboard_date", "offboard_date"])
    addresses = pd.read_csv(raw_dir / "addresses.csv", parse_dates=["created_at"])
    availability = pd.read_csv(raw_dir / "restaurant_availability.csv", parse_dates=["timestamp"])
    behavior = load_user_profiles(processed_dir / "user_profiles.parquet")
    restaurant_profiles = load_entity_profiles(processed_dir / "restaurant_profiles.parquet")
    rngs = create_rngs(config.master_seed)
    orders, order_items = generate_order_tables(
        users,
        restaurants,
        partners,
        addresses,
        availability,
        behavior,
        restaurant_profiles,
        config,
        rngs,
    )
    errors = validate_stage4(orders, order_items, users, restaurants, partners, addresses, cities, config)
    if errors:
        raise ValueError("Stage 4 validation failed: " + "; ".join(errors))
    export_tables({"orders": orders, "order_items": order_items}, raw_dir)
    return orders, order_items


def generate_stage5(config: GeneratorConfig = CONFIG) -> pd.DataFrame:
    """Generate and export only delivery events from existing orders."""
    raw_dir = config.output_root / "raw"
    orders = pd.read_csv(raw_dir / "orders.csv", parse_dates=["order_timestamp", "promised_delivery_timestamp", "actual_delivery_timestamp", "cancelled_at"])
    partners = pd.read_csv(raw_dir / "delivery_partners.csv", parse_dates=["onboard_date", "offboard_date"])
    events = generate_delivery_events(orders, config, create_rngs(config.master_seed))
    errors = validate_stage5(events, orders, partners, config)
    if errors:
        raise ValueError("Stage 5 validation failed: " + "; ".join(errors))
    export_tables({"delivery_events": events}, raw_dir)
    return events


def generate_stage6(config: GeneratorConfig = CONFIG) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate and export only ratings, order issues, and refunds."""
    raw_dir = config.output_root / "raw"
    processed_dir = config.output_root / "processed"
    orders = pd.read_csv(raw_dir / "orders.csv", parse_dates=["order_timestamp", "promised_delivery_timestamp", "actual_delivery_timestamp", "cancelled_at"])
    order_items = pd.read_csv(raw_dir / "order_items.csv")
    delivery_events = pd.read_csv(raw_dir / "delivery_events.csv", parse_dates=["event_timestamp"])
    users = pd.read_csv(raw_dir / "users.csv", parse_dates=["signup_timestamp", "mobility_signup_date", "membership_start_date"])
    restaurants = pd.read_csv(raw_dir / "restaurants.csv", parse_dates=["onboard_date", "offboard_date"])
    behavior = load_user_profiles(processed_dir / "user_profiles.parquet")
    rngs = create_rngs(config.master_seed)
    ratings = generate_ratings(orders, config, rngs, behavior.profiles)
    issues = generate_order_issues(orders, config, rngs, delivery_events)
    refunds = generate_refunds(orders, order_items, issues, config, rngs)
    errors = validate_stage6(ratings, issues, refunds, orders, users, restaurants, config)
    if errors:
        raise ValueError("Stage 6 validation failed: " + "; ".join(errors))
    export_tables({"ratings": ratings, "order_issues": issues, "refunds": refunds}, raw_dir)
    return ratings, issues, refunds


def generate_stage7(config: GeneratorConfig = CONFIG) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate and export only promotions and order promotions."""
    raw_dir = config.output_root / "raw"
    markets, _ = load_market_city_inputs(config)
    orders = pd.read_csv(raw_dir / "orders.csv", parse_dates=["order_timestamp", "promised_delivery_timestamp", "actual_delivery_timestamp", "cancelled_at"])
    promotions = generate_promotions(markets, config, create_rngs(config.master_seed))
    order_promotions = generate_order_promotions(orders, promotions, config, create_rngs(config.master_seed))
    errors = validate_stage7(promotions, order_promotions, orders, config)
    if errors:
        raise ValueError("Stage 7 validation failed: " + "; ".join(errors))
    export_tables({"promotions": promotions, "order_promotions": order_promotions}, raw_dir)
    return promotions, order_promotions


def generate_stage8(config: GeneratorConfig = CONFIG) -> pd.DataFrame:
    """Generate and export only order financials."""
    raw_dir = config.output_root / "raw"
    orders = pd.read_csv(raw_dir / "orders.csv", parse_dates=["order_timestamp", "promised_delivery_timestamp", "actual_delivery_timestamp", "cancelled_at"])
    order_promotions = pd.read_csv(raw_dir / "order_promotions.csv")
    refunds = pd.read_csv(raw_dir / "refunds.csv", parse_dates=["refund_timestamp"])
    issues = pd.read_csv(raw_dir / "order_issues.csv", parse_dates=["reported_at", "resolved_at"])
    financials = generate_order_financials(orders, order_promotions, refunds, issues, config, create_rngs(config.master_seed))
    errors = validate_stage8(financials, orders, config)
    if errors:
        raise ValueError("Stage 8 validation failed: " + "; ".join(errors))
    export_tables({"order_financials": financials}, raw_dir)
    return financials


def main() -> None:
    """Generate and export the eighth stage only."""
    financials = generate_stage8()
    print(f"Generated order_financials={len(financials)}.")
    print("No Stage 9+ tables were generated.")


if __name__ == "__main__":
    main()
