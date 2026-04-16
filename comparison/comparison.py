from typing import List
import pandas as pd
from sqlalchemy import text, Engine
from queries import COLUMNS_FOR_TABLE


def compare_tables(query: str, connections: List[Engine]) -> None:
    """
    Run a table-listing query against each connection and print
    which tables are present in one DB but missing from the other.
    """
    dataframes = [pd.read_sql(query, connection) for connection in connections]
    try:
        for i in range(len(dataframes)):
            for j in range(i + 1, len(dataframes)):
                old_tables = set(dataframes[i]["TABLE_NAME"])
                new_tables = set(dataframes[j]["TABLE_NAME"])
                print(f"In Old Linode DB but not DigitalOcean DB: {old_tables - new_tables}")
                print(f"In New DigitalOcean DB but not Linode DB: {new_tables - old_tables}")
                print(f"In both: {old_tables & new_tables}")
    except Exception as error:
        print(f"Comparison failed: {error}")
        raise


def compare_columns(query: str, table_name: str, connections: List[Engine]) -> pd.DataFrame:
    """
    Compare column metadata for a specific table across two databases.
    Returns a DataFrame with one row per column and a 'status' field:
      - matched: column exists in both with the same type
      - type_changed: column exists in both but types differ
      - old_db_only: column only exists in the source DB
      - new_db_only: column only exists in the target DB
    """
    old_cols, new_cols = [
        pd.read_sql(text(query), conn, params={"table_name": table_name})
        for conn in connections
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


