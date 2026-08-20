"""Generate market and city dimensions from configuration."""

import pandas as pd

from .config import GeneratorConfig
from .rng import RNGStreams


_MARKET_DETAILS = {
    "India": {"currency": "INR", "timezone": "Asia/Kolkata", "launch_date": "2017-05-01"},
    "USA": {"currency": "USD", "timezone": "America/New_York", "launch_date": "2014-08-01"},
    "Australia": {"currency": "AUD", "timezone": "Australia/Sydney", "launch_date": "2016-03-01"},
    "UK": {"currency": "GBP", "timezone": "Europe/London", "launch_date": "2016-06-01"},
    "Japan": {"currency": "JPY", "timezone": "Asia/Tokyo", "launch_date": "2016-05-01"},
}

_CITY_PROFILES = {
    "India": (
        ("Bengaluru", 12_300_000, 4_500.0, "TIER_1", 12.9716, 77.5946),
        ("Delhi", 19_000_000, 11_300.0, "TIER_1", 28.6139, 77.2090),
        ("Mumbai", 20_700_000, 20_700.0, "TIER_1", 19.0760, 72.8777),
        ("Hyderabad", 10_800_000, 4_900.0, "TIER_1", 17.3850, 78.4867),
        ("Chennai", 11_200_000, 4_900.0, "TIER_1", 13.0827, 80.2707),
        ("Pune", 7_400_000, 5_600.0, "TIER_1", 18.5204, 73.8567),
        ("Kolkata", 15_100_000, 8_200.0, "TIER_1", 22.5726, 88.3639),
        ("Jaipur", 4_000_000, 2_200.0, "TIER_2", 26.9124, 75.7873),
    ),
    "USA": (
        ("New York", 8_300_000, 11_300.0, "TIER_1", 40.7128, -74.0060),
        ("Los Angeles", 3_900_000, 3_200.0, "TIER_1", 34.0522, -118.2437),
        ("Chicago", 2_700_000, 4_600.0, "TIER_1", 41.8781, -87.6298),
        ("San Francisco", 815_000, 7_100.0, "TIER_1", 37.7749, -122.4194),
        ("Austin", 980_000, 1_700.0, "TIER_2", 30.2672, -97.7431),
        ("Denver", 715_000, 1_800.0, "TIER_2", 39.7392, -104.9903),
    ),
    "Australia": (
        ("Sydney", 5_300_000, 430.0, "TIER_1", -33.8688, 151.2093),
        ("Melbourne", 5_100_000, 510.0, "TIER_1", -37.8136, 144.9631),
        ("Brisbane", 2_600_000, 160.0, "TIER_2", -27.4698, 153.0251),
        ("Perth", 2_200_000, 330.0, "TIER_2", -31.9505, 115.8605),
        ("Adelaide", 1_400_000, 410.0, "TIER_2", -34.9285, 138.6007),
    ),
    "UK": (
        ("London", 9_000_000, 5_700.0, "TIER_1", 51.5074, -0.1278),
        ("Manchester", 2_800_000, 2_500.0, "TIER_1", 53.4808, -2.2426),
        ("Birmingham", 1_150_000, 4_300.0, "TIER_2", 52.4862, -1.8904),
        ("Edinburgh", 550_000, 1_900.0, "TIER_2", 55.9533, -3.1883),
        ("Bristol", 470_000, 2_700.0, "TIER_2", 51.4545, -2.5879),
    ),
    "Japan": (
        ("Tokyo", 14_000_000, 6_400.0, "TIER_1", 35.6762, 139.6503),
        ("Osaka", 2_750_000, 12_000.0, "TIER_1", 34.6937, 135.5023),
        ("Yokohama", 3_770_000, 8_600.0, "TIER_1", 35.4437, 139.6380),
        ("Nagoya", 2_330_000, 7_100.0, "TIER_1", 35.1815, 136.9066),
        ("Fukuoka", 1_630_000, 4_600.0, "TIER_2", 33.5904, 130.4017),
    ),
}


def generate_markets(config: GeneratorConfig, rngs: RNGStreams) -> pd.DataFrame:
    """Create the five market dimension rows from configured market definitions."""
    rows = []
    for market_id, market in enumerate(config.markets, start=1):
        details = _MARKET_DETAILS[market.name]
        rows.append(
            {
                "market_id": market_id,
                "country": market.name,
                "currency": details["currency"],
                "timezone": details["timezone"],
                "launch_date": details["launch_date"],
                "exit_date": pd.NaT,
                "market_status": "ACTIVE",
                "market_type": "NATIONAL",
            }
        )
    markets = pd.DataFrame(rows)
    return _cast_to_schema(markets, "markets")


def generate_cities(markets: pd.DataFrame, config: GeneratorConfig, rngs: RNGStreams) -> pd.DataFrame:
    """Create geographically plausible cities with seeded correlated variation."""
    random = rngs.for_module("markets")
    market_ids = markets.set_index("country")["market_id"].to_dict()
    market_launch_dates = markets.set_index("market_id")["launch_date"].to_dict()
    rows = []
    city_id = 1

    for market_name, profiles in _CITY_PROFILES.items():
        market_id = market_ids[market_name]
        market_launch_date = market_launch_dates[market_id]
        for city_name, population, density, urban_tier, latitude, longitude in profiles:
            scale_noise = float(random.normal(1.0, 0.018))
            density_noise = float(random.normal(1.0, 0.025))
            city_launch_date = max(
                pd.Timestamp(market_launch_date),
                pd.Timestamp(market_launch_date) + pd.to_timedelta(int(random.integers(0, 730)), unit="D"),
            )
            rows.append(
                {
                    "city_id": city_id,
                    "market_id": market_id,
                    "city_name": city_name,
                    "launch_date": city_launch_date,
                    "population": max(1, int(round(population * scale_noise))),
                    "population_density": round(max(1.0, density * density_noise), 2),
                    "urban_tier": urban_tier,
                    "latitude": round(latitude + float(random.normal(0.0, 0.002)), 6),
                    "longitude": round(longitude + float(random.normal(0.0, 0.002)), 6),
                }
            )
            city_id += 1
    cities = pd.DataFrame(rows)
    return _cast_to_schema(cities, "cities")


def _cast_to_schema(table: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """Apply the pandas dtypes and column order defined by the schema registry."""
    from .schemas import TABLE_SCHEMAS

    schema = TABLE_SCHEMAS[table_name]
    table = table.loc[:, list(schema)].copy()
    for column, dtype in schema.items():
        if dtype.startswith("datetime"):
            table[column] = pd.to_datetime(table[column])
        else:
            table[column] = table[column].astype(dtype)
    return table
