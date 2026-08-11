from sqlalchemy import Engine

from dialects import Dialect
from migration import get_fk_graph, resolve_table_order, set_fk_checks, migrate_table


def run_migration(
    source_engine: Engine,
    target_engine: Engine,
    source_dialect: Dialect,
    target_dialect: Dialect,
    tables: set,
    batch_size: int = 100,
) -> list:
    """
    Migrate all tables from source to target in FK-safe order.
    Skips tables that fail without stopping the rest.
    Returns a list of per-table stats dicts.
    """

    fk_graph = get_fk_graph(source_engine, source_dialect)
    table_order = resolve_table_order(fk_graph, tables)

    results = []
    failed = []

    # One connection for the whole migration: disabling FK checks only affects
    # the session it ran on, so the inserts have to share it.
    with target_engine.connect() as target_connection:
        fk_checks_disabled = set_fk_checks(
            target_connection, target_dialect, enabled=False
        )

        for table_name in table_order:
            try:
                # Read on the engine, not target_connection: pandas would
                # open an implicit transaction on it and collide with the
                # per-table begin() below.
                target_columns = target_dialect.get_columns(target_engine, table_name)
                column_types = dict(
                    zip(target_columns["column_name"], target_columns["column_type"])
                )

                stats = migrate_table(
                    table_name,
                    source_engine,
                    target_connection,
                    source_dialect,
                    target_dialect,
                    batch_size,
                    target_column_types=column_types,
                )
                results.append(stats)
            except Exception as error:
                failed.append({"table": table_name, "error": str(error)})
                print(f"{table_name} failed: {error}")

        # Inserting explicit key values leaves the target's own key generator
        # untouched, so it must be advanced past the migrated rows before
        # anything else writes to these tables.
        sequences = 0
        for stats in results:
            if stats["status"] == "ok":
                sequences += target_dialect.reset_sequences(
                    target_connection, stats["table"]
                )
        if sequences:
            target_connection.commit()
            print(f"Reset {sequences} key sequence(s) past the migrated rows")

        if fk_checks_disabled:
            set_fk_checks(target_connection, target_dialect, enabled=True)

    total_inserted = sum(stats["inserted"] for stats in results)
    print(f"{'='*20}")
    print(f"Migration Complete")
    print(f"Succeeded: {len(results)} tables, {total_inserted:,} rows inserted")

    if failed:
        print(f"Failed: {len(failed)} tables")
        for failure in failed:
            print(f"- {failure['table']}: {failure['error']}")

    print(f"{'='*20}")

    return results
