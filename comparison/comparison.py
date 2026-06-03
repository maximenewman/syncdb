from typing import List

import pandas as pd
from sqlalchemy import Engine

from dialects import get_dialect


def compare_tables(connections: List[Engine]) -> None:
    """
    List tables on each connection and print which tables are present in one
    database but missing from the other.
    """
    table_sets = [get_dialect(conn).get_all_tables(conn) for conn in connections]
    for i in range(len(table_sets)):
        for j in range(i + 1, len(table_sets)):
            source_tables = table_sets[i]
            target_tables = table_sets[j]
            print(f"In source only: {source_tables - target_tables}")
            print(f"In target only: {target_tables - source_tables}")
            print(f"In both: {source_tables & target_tables}")


def compare_columns(table_name: str, connections: List[Engine]) -> pd.DataFrame:
    """
    Compare column metadata for a specific table across two databases.
    Returns a DataFrame with one row per column and a 'status' field:
      - matched: column exists in both with the same type
      - type_changed: column exists in both but types differ
      - old_db_only: column only exists in the source DB
      - new_db_only: column only exists in the target DB
    """
    old_cols, new_cols = [
        get_dialect(conn).get_columns(conn, table_name) for conn in connections
    ]

    merged = old_cols.merge(
        new_cols,
        on="COLUMN_NAME",
        how="outer",
        suffixes=("_old", "_new"),
        indicator=True,
    )

    status_map = {
        "both": "matched",
        "left_only": "old_db_only",
        "right_only": "new_db_only",
    }
    merged["status"] = merged["_merge"].map(status_map).astype(str)

    type_changed = (
        (merged["status"] == "matched")
        & (merged["COLUMN_TYPE_old"] != merged["COLUMN_TYPE_new"])
    )
    merged.loc[type_changed, "status"] = "type_changed"

    return merged
