"""Latent user behavior profiles used by order generation."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import GeneratorConfig
from .rng import RNGStreams


@dataclass
class UserBehaviorProfiles:
    """Internal behavior state; fields are not exported as user columns."""

    profiles: pd.DataFrame


def build_user_behavior(users: pd.DataFrame, config: GeneratorConfig, rngs: RNGStreams) -> UserBehaviorProfiles:
    """Assign correlated lifecycle, frequency, retention, and promotion traits."""
    random = rngs.for_module("behavior")
    user_count = len(users)
    mobility = users["is_uber_mobility_user"].to_numpy(dtype=bool)
    promotion_affinity = random.beta(2.0, 4.0, user_count)
    price_sensitivity = np.clip(0.35 + 0.45 * promotion_affinity + random.normal(0, 0.08, user_count), 0, 1)
    order_propensity = np.clip(0.15 + 0.55 * (1 - price_sensitivity) + random.normal(0, 0.12, user_count), 0, 1)
    frequency_score = np.clip(order_propensity + random.normal(0, 0.10, user_count), 0, 1)
    churn_propensity = np.clip(0.75 - 0.55 * order_propensity + 0.20 * price_sensitivity + random.normal(0, 0.08, user_count), 0, 1)
    delivery_tolerance = np.clip(0.70 - 0.40 * price_sensitivity + random.normal(0, 0.10, user_count), 0, 1)
    rating_propensity = np.clip(0.18 + 0.62 * order_propensity + random.normal(0, 0.10, user_count), 0, 1)
    restaurant_loyalty = np.clip(0.25 + 0.55 * order_propensity + random.normal(0, 0.12, user_count), 0, 1)
    discount_dependent = (promotion_affinity > 0.62) & (price_sensitivity > 0.58)
    organic = (promotion_affinity < 0.38) & (price_sensitivity < 0.55)
    segment = np.select(
        [frequency_score < 0.18, frequency_score < 0.35, frequency_score < 0.60, frequency_score >= 0.82],
        ["zero_order_dormant", "one_time", "low_frequency", "high_frequency"],
        default="medium_frequency",
    )
    segment = np.where(discount_dependent, "discount_dependent", segment)
    retained = (frequency_score > 0.45) & (churn_propensity < 0.45)
    churn_prone = churn_propensity > 0.68
    segment = np.where(retained, "retained", segment)
    segment = np.where(churn_prone & ~retained, "churn_prone", segment)
    profiles = pd.DataFrame(
        {
            "entity_id": users["user_id"].to_numpy(),
            "order_propensity": order_propensity,
            "promotion_affinity": promotion_affinity,
            "price_sensitivity": price_sensitivity,
            "restaurant_loyalty": restaurant_loyalty,
            "delivery_tolerance": delivery_tolerance,
            "rating_propensity": rating_propensity,
            "churn_propensity": churn_propensity,
            "preferred_order_frequency": frequency_score,
            "preferred_order_daypart": random.choice(["BREAKFAST", "LUNCH", "DINNER", "LATE_NIGHT"], user_count),
            "preferred_cuisine_tendency": random.choice(["LOCAL", "FAST_FOOD", "HEALTHY", "ASIAN", "DESSERT"], user_count),
            "discount_dependent": discount_dependent,
            "organic": organic,
            "segment": segment,
            "mobility_user": mobility,
        }
    )
    return UserBehaviorProfiles(profiles=profiles)


def save_user_profiles(profiles: UserBehaviorProfiles, path: Path) -> None:
    """Persist latent user behavior for later generator processes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    profiles.profiles.to_parquet(path, index=False)


def load_user_profiles(path: Path) -> UserBehaviorProfiles:
    """Load persisted latent user behavior from a processed Parquet artifact."""
    return UserBehaviorProfiles(profiles=pd.read_parquet(path))
