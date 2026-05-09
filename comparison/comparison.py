import pandas as pd
from sqlalchemy import Engine

from dialects import Dialect


def compare_tables(
    source_engine: Engine,
    target_engine: Engine,
    source_dialect: Dialect,
    target_dialect: Dialect,
) -> None:
    """
    Print which tables are present in one DB but missing from the other.
    """
    try:
        source_tables = source_dialect.get_all_tables(source_engine)
        target_tables = target_dialect.get_all_tables(target_engine)
        print(f"In source only: {source_tables - target_tables}")
        print(f"In target only: {target_tables - source_tables}")
        print(f"In both: {source_tables & target_tables}")
    except Exception as error:
        print(f"Comparison failed: {error}")
        raise


def compare_columns(
    table_name: str,
    source_engine: Engine,
    target_engine: Engine,
    source_dialect: Dialect,
    target_dialect: Dialect,
) -> pd.DataFrame:
    """
    Compare column metadata for a specific table across two databases.
    Returns a DataFrame with one row per column and a 'status' field:
      - matched: column exists in both with the same type
      - type_changed: column exists in both but types differ
      - source_only: column only exists in the source DB
      - target_only: column only exists in the target DB
    """
    source_cols = source_dialect.get_columns(source_engine, table_name)
    target_cols = target_dialect.get_columns(target_engine, table_name)

    merged = source_cols.merge(
        target_cols,
        on="column_name",
        how="outer",
        suffixes=("_source", "_target"),
        indicator=True,
    )

    status_map = {
        "both": "matched",
        "left_only": "source_only",
        "right_only": "target_only",
    }
    merged["status"] = merged["_merge"].map(status_map).astype(str)

    type_changed = (
        (merged["status"] == "matched")
        & (merged["column_type_source"] != merged["column_type_target"])
    )
    merged.loc[type_changed, "status"] = "type_changed"

    return merged
