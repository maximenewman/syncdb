import pandas as pd
from sqlalchemy import Engine

from dialects import Dialect


def validate_table(
    table_name: str,
    source_engine: Engine,
    target_engine: Engine,
    source_dialect: Dialect,
    target_dialect: Dialect,
) -> dict:
    """
    Compare primary keys between source and target to verify migration
    completeness. Prints a one-line summary per table and a sample of any
    missing PKs. Returns a dict with counts of shared, missing, and extra
    rows plus a pass/fail status.
    """
    pk_columns = source_dialect.get_primary_keys(source_engine, table_name)

    if not pk_columns:
        print(f"{table_name}: no primary key, skipping validation")
        return {"table": table_name, "status": "no_pk"}

    source_pk_sql = ", ".join(source_dialect.quote_identifier(c) for c in pk_columns)
    target_pk_sql = ", ".join(target_dialect.quote_identifier(c) for c in pk_columns)
    source_table = source_dialect.quote_identifier(table_name)
    target_table = target_dialect.quote_identifier(table_name)

    old_keys = pd.read_sql(f"SELECT {source_pk_sql} FROM {source_table}", source_engine)
    new_keys = pd.read_sql(f"SELECT {target_pk_sql} FROM {target_table}", target_engine)

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
