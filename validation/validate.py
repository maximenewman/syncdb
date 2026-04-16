import pandas as pd
from sqlalchemy import Engine, text
from queries.information_schema import PRIMARY_KEYS


def get_primary_key(table_name: str, engine: Engine) -> list | None:
    """
    Return the ordered list of primary key column names for a table,
    or None if the table has no primary key.
    """
    with engine.connect() as conn:
        result = pd.read_sql(text(PRIMARY_KEYS), conn, params={"table_name": table_name})

    if result.empty:
        return None

    return result["COLUMN_NAME"].tolist()


def validate_table(table_name: str, source_engine: Engine, target_engine: Engine) -> dict:
    """
    Compare primary keys between source and target to verify migration completeness.
    Prints a one-line summary per table and a sample of any missing PKs.
    Returns a dict with counts of shared, missing, and extra rows plus a pass/fail status.
    """
    pk_columns = get_primary_key(table_name, source_engine)

    if not pk_columns:
        print(f"{table_name}: no primary key, skipping validation")
        return {"table": table_name, "status": "no_pk"}

    pk_sql = ", ".join(f"`{col}`" for col in pk_columns)

    old_keys = pd.read_sql(f"SELECT {pk_sql} FROM `{table_name}`", source_engine)
    new_keys = pd.read_sql(f"SELECT {pk_sql} FROM `{table_name}`", target_engine)

    # tuples handles composite primary keys
    old_set = set(old_keys.itertuples(index=False, name=None))
    new_set = set(new_keys.itertuples(index=False, name=None))

    missing_in_new = old_set - new_set
    only_in_new = new_set - old_set
    in_both = old_set & new_set

    status = "✓ pass" if len(missing_in_new) == 0 else "✗ fail"

    print(f"  {status}  {table_name}: "
          f"{len(in_both)} shared, "
          f"{len(missing_in_new)} missing from new, "
          f"{len(only_in_new)} only in new")

    if missing_in_new:
        sample = list(missing_in_new)[:5]
        print(f"         sample missing PKs: {sample}")

    return {
        "table": table_name,
        "in_both": len(in_both),
        "missing_in_new": len(missing_in_new),
        "only_in_new": len(only_in_new),
        "missing_pks": missing_in_new,
        "status": "pass" if len(missing_in_new) == 0 else "fail",
    }
