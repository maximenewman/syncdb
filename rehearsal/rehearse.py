from sqlalchemy import create_engine

from dialects import get_dialect
from migration.migrate import run_migration
from schema.translate import generate_ddl
from validation.run_validation import run_validation

from .docker_postgres import DisposablePostgres


def run_rehearsal(
    source_url: str,
    image: str = "postgres:16",
    port: int = 15432,
    tables: set | None = None,
    batch_size: int = 100,
    keep: bool = False,
) -> dict:
    """
    Rehearse a migration end to end against a disposable Postgres container.

    Runs the same code path as a real migration, against a database that can
    be thrown away, so schema translation and type coercion are proven before
    anything touches a real target. Returns a summary dict and prints a
    verdict.
    """
    source_engine = create_engine(source_url)
    source_dialect = get_dialect(source_engine)

    if tables is None:
        tables = source_dialect.get_all_tables(source_engine)

    print(f"{'=' * 60}")
    print(f"REHEARSAL: {len(tables)} tables from a {source_dialect.name} source")
    print(f"{'=' * 60}")

    with DisposablePostgres(image=image, port=port, keep=keep) as container:
        target_engine = create_engine(container.url)
        target_dialect = get_dialect(target_engine)

        print("\n-- translating schema --")
        ddl = generate_ddl(source_engine, source_dialect, target_dialect, tables)
        container.apply_sql(ddl)

        created = target_dialect.get_all_tables(target_engine)
        print(f"created {len(created)} tables on the rehearsal target")

        missing = set(tables) - created
        if missing:
            print(f"!! {len(missing)} tables failed to translate: {sorted(missing)}")

        print("\n-- migrating --")
        results = run_migration(
            source_engine,
            target_engine,
            source_dialect,
            target_dialect,
            set(tables) & created,
            batch_size,
        )

        print("\n-- validating --")
        validation = run_validation(
            source_engine,
            target_engine,
            source_dialect,
            target_dialect,
            set(tables) & created,
        )

        print("\n-- re-running to confirm the migration is repeatable --")
        repeat = run_migration(
            source_engine,
            target_engine,
            source_dialect,
            target_dialect,
            set(tables) & created,
            batch_size,
        )
        reinserted = sum(stats["inserted"] for stats in repeat)

        failed_validation = [r for r in validation if r["status"] == "fail"]
        summary = {
            "tables_requested": len(tables),
            "tables_created": len(created),
            "tables_missing": sorted(missing),
            "rows_inserted": sum(stats["inserted"] for stats in results),
            "rows_reinserted_on_second_run": reinserted,
            "validation_failures": [r["table"] for r in failed_validation],
        }

        print(f"\n{'=' * 60}")
        print("REHEARSAL VERDICT")
        print(f"{'=' * 60}")
        print(f"  tables translated : {len(created)}/{len(tables)}")
        print(f"  rows inserted     : {summary['rows_inserted']:,}")
        print(f"  validation failures: {len(failed_validation)}")
        print(f"  rows on re-run    : {reinserted} (must be 0 to be repeatable)")

        ok = not missing and not failed_validation and reinserted == 0
        print(f"\n  {'PASS - safe to run against a real target' if ok else 'FAIL - do not migrate yet'}")
        summary["passed"] = ok

    return summary
