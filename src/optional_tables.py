"""Optional behavioral and market-context tables, intentionally deferred."""

import pandas as pd


def generate_optional_tables(*, orders: pd.DataFrame, **_: object) -> dict[str, pd.DataFrame]:
    """Return optional tables when their generators are implemented."""
    return {}
