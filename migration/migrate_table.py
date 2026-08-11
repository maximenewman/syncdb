import pandas as pd
from sqlalchemy import Connection, Engine, text

from dialects import Dialect


def migrate_table(
    table_name: str,
    source_engine: Engine,
    target_connection: Connection,
    source_dialect: Dialect,
    target_dialect: Dialect,
    batch_size: int = 100,
) -> dict:
    """
    Extract all rows from a source table and insert into the target,
    skipping rows that conflict on PK/unique. NaN values are converted
    to NULL before insertion.

    Writes go through the caller's connection so they share the session that
    has FK checks disabled. Each table gets its own transaction, so a failure
    rolls back only that table.

    Returns a stats dict with source row count, inserted count, and status.
    """

    df = pd.read_sql(source_dialect.select_all_sql(table_name), source_engine)
    total = len(df)

    if total == 0:
        print(f"{table_name}: empty, skipping")
        return {"table": table_name, "source": 0, "inserted": 0, "status": "skipped"}

    insert_sql = text(
        target_dialect.insert_skipping_duplicates_sql(table_name, list(df.columns))
    )

    rows = df.astype(object).where(df.notna(), None).to_dict("records")
    inserted = 0

    with target_connection.begin():
        for batch_num, offset in enumerate(range(0, len(rows), batch_size), start=1):
            batch = rows[offset:offset + batch_size]
            batch_result = target_connection.execute(insert_sql, batch)
            inserted += batch_result.rowcount
            print(f"batch {batch_num}: sent {len(batch)}, inserted {batch_result.rowcount}")

    print(f"✓ {table_name}: {inserted} new rows inserted out of {total}")
    return {"table": table_name, "source": total, "inserted": inserted, "status": "ok"}
