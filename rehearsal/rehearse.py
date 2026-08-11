from sqlalchemy import create_engine, text

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

        print("\n-- checking key sequences clear the migrated rows --")
        # A fault in the check itself must not throw away the report for a
        # run that otherwise succeeded, but it does count as a failure:
        # an unverified sequence is not a verified one.
        check_error = None
        try:
            stale = _stale_sequences(target_engine)
        except Exception as error:  # noqa: BLE001
            check_error = error
            stale = []
            print(f"!! sequence check could not run: {error}")

        if stale:
            print(f"!! {len(stale)} sequence(s) would collide on the next insert:")
            for table, column, next_value, highest in stale[:10]:
                print(f"   {table}.{column}: next={next_value}, but max is {highest}")
        else:
            print("   all sequences start past the highest migrated key")

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

        summary["stale_sequences"] = [f"{t}.{c}" for t, c, _, _ in stale]
        print(f"  sequences needing a reset: {len(stale)}")

        ok = (
            not missing
            and not failed_validation
            and reinserted == 0
            and not stale
            and check_error is None
        )
        print(f"\n  {'PASS - safe to run against a real target' if ok else 'FAIL - do not migrate yet'}")
        summary["passed"] = ok

    return summary


def _stale_sequences(engine) -> list[tuple]:
    """
    Find identity sequences that would hand out a key already in use.

    Reported per column as (table, column, next_value, highest_existing).
    """
    with engine.connect() as conn:
        columns = conn.execute(text("""
            SELECT c.table_name, c.column_name
            FROM information_schema.columns c
            JOIN information_schema.tables t
              ON t.table_schema = c.table_schema AND t.table_name = c.table_name
            WHERE c.table_schema = current_schema()
              AND t.table_type = 'BASE TABLE'
              AND (c.is_identity = 'YES' OR c.column_default LIKE 'nextval(%')
        """)).fetchall()

        stale = []
        for table, column in columns:
            sequence = conn.execute(
                text("SELECT pg_get_serial_sequence(:t, :c)"),
                {"t": f'"{table}"', "c": column},
            ).scalar()
            if sequence is None:
                continue

            highest = conn.execute(
                text(f'SELECT COALESCE(MAX("{column}"), 0) FROM "{table}"')
            ).scalar()
            if not highest:
                continue

            # is_called lives on the sequence relation, not on pg_sequences.
            # The name comes from pg_get_serial_sequence already quoted, so
            # interpolating it is safe and parameters are not accepted here.
            last_value, is_called = conn.execute(
                text(f"SELECT last_value, is_called FROM {sequence}")
            ).one()

            next_value = last_value + 1 if is_called else last_value
            if next_value <= highest:
                stale.append((table, column, next_value, highest))
    return stale
