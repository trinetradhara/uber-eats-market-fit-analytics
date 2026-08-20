"""Central configuration for the synthetic Uber Eats dataset."""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class EdgeCaseRates:
    """Rates used later by controlled edge-case injectors."""

    duplicate_like_orders: float = 0.002
    duplicate_delivery_events: float = 0.003
    missing_delivery_timestamps: float = 0.004
    multiple_partner_attempts: float = 0.035
    cancellation_after_pickup: float = 0.003
    orders_without_partner: float = 0.018
    high_value_orders: float = 0.002
    missing_delivery_events: float = 0.006
    unusual_event_ordering: float = 0.002


@dataclass(frozen=True)
class MarketConfig:
    """Market-level priors; these do not encode an outcome ranking."""

    country_code: str
    name: str
    population_weight: float
    fee_sensitivity: float
    promotion_sensitivity: float
    traffic_volatility: float
    restaurant_density: float
    partner_density: float


@dataclass(frozen=True)
class GeneratorConfig:
    """All scale, time, reproducibility, and output settings."""

    master_seed: int = 20260820
    target_users: int = 55_000
    target_restaurants: int = 12_000
    target_delivery_partners: int = 12_000
    target_orders: int = 500_000
    start_date: date = date(2024, 1, 1)
    end_date: date = date(2025, 12, 31)
    generation_chunk_size: int = 50_000
    output_root: Path = Path("data")
    markets: tuple[MarketConfig, ...] = field(
        default_factory=lambda: (
            MarketConfig("IN", "India", 1.0, 0.82, 0.78, 0.68, 0.72, 0.70),
            MarketConfig("US", "USA", 0.85, 0.48, 0.45, 0.58, 0.88, 0.86),
            MarketConfig("AU", "Australia", 0.32, 0.42, 0.38, 0.46, 0.63, 0.62),
            MarketConfig("GB", "UK", 0.48, 0.52, 0.50, 0.52, 0.79, 0.76),
            MarketConfig("JP", "Japan", 0.55, 0.60, 0.44, 0.50, 0.81, 0.74),
        )
    )
    edge_cases: EdgeCaseRates = field(default_factory=EdgeCaseRates)


CONFIG = GeneratorConfig()
