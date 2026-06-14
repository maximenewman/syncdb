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

    set_fk_checks(target_engine, target_dialect, enabled=False)

    results = []
    failed = []

    for table_name in table_order:
        try:
            stats = migrate_table(
                table_name,
                source_engine,
                target_engine,
                source_dialect,
                target_dialect,
                batch_size,
            )
            results.append(stats)
        except Exception as error:
            failed.append({"table": table_name, "error": str(error)})
            print(f"{table_name} failed: {error}")

    set_fk_checks(target_engine, target_dialect, enabled=True)

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
