"""CSV export helpers for validated generated tables."""

from pathlib import Path
from typing import Mapping

import pandas as pd

from .schemas import TABLE_SCHEMAS


def export_tables(tables: Mapping[str, pd.DataFrame], output_dir: Path) -> None:
    """Write validated DataFrames to one CSV per required table."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for table_name in TABLE_SCHEMAS:
        if table_name in tables:
            tables[table_name].to_csv(output_dir / f"{table_name}.csv", index=False)
