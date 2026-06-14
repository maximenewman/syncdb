import click
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, Engine

from dialects import Dialect, get_dialect
from comparison.comparison import compare_tables, compare_columns
from comparison.empty_tables import report_empty_tables
from migration.migrate import run_migration
from validation.run_validation import run_validation

load_dotenv()


def get_shared_tables(
    source_engine: Engine,
    target_engine: Engine,
    source_dialect: Dialect,
    target_dialect: Dialect,
) -> set:
    return source_dialect.get_all_tables(source_engine) & target_dialect.get_all_tables(target_engine)


@click.group()
def cli():
    """
    Sync data between two databases.
    """

@cli.command()
@click.option("--source", envvar="SOURCE_DB_URL", required=True, help="""SQLAlchemy connection string for the source database (e.g. mysql+pymysql://user:pass@host:3306/db).
Falls back to SOURCE_DB_URL env var.""")
@click.option("--target", envvar="TARGET_DB_URL", required=True, help="""SQLAlchemy connection string for the target database (e.g. mysql+pymysql://user:pass@host:3306/db).
Falls back to TARGET_DB_URL env var.""")
def compare(source: str, target: str) -> None:
    """
    Compare schemas and row counts between source and target. Reports missing tables,
    column differences, and empty tables.
    """
    source_engine = create_engine(source)
    target_engine = create_engine(target)
    source_dialect = get_dialect(source_engine)
    target_dialect = get_dialect(target_engine)

    compare_tables(source_engine, target_engine, source_dialect, target_dialect)

    shared = get_shared_tables(source_engine, target_engine, source_dialect, target_dialect)
    all_diffs = []
    for table in sorted(shared):
        diff = compare_columns(table, source_engine, target_engine, source_dialect, target_dialect)
        diff["table_name"] = table
        all_diffs.append(diff)

    full_report = pd.concat(all_diffs, ignore_index=True)

    problems = full_report[full_report["status"] != "matched"]
    output = problems[["table_name", "column_name", "column_type_source", "column_type_target", "status"]]

    if output.empty:
        print("No schema differences found.")
    else:
        print(output.to_string(index=False))

    report_empty_tables(source_engine, source_dialect, "Source Database")
    report_empty_tables(target_engine, target_dialect, "Target Database")


@cli.command()
@click.option("--source", envvar="SOURCE_DB_URL", required=True, help="""SQLAlchemy connection string for the source database (e.g. mysql+pymysql://user:pass@host:3306/db).
Falls back to SOURCE_DB_URL env var.""")
@click.option("--target", envvar="TARGET_DB_URL", required=True, help="""SQLAlchemy connection string for the target database (e.g. mysql+pymysql://user:pass@host:3306/db).
Falls back to TARGET_DB_URL env var.""")
@click.option("--tables", required=False, help="""Shared table list between the two databases.
Comma-separated list of tables to process (e.g. users,orders,products). Defaults to all shared tables.""")
@click.option("--dry-run", is_flag=True, default=False, required=False, help="""Safe mode, no migration is ran.
Preview which tables would be migrated without writing any data to the target.""")
@click.option("--batch-size", default=100, show_default=True, help="Rows per INSERT batch")
def migrate(source: str, target: str, tables: set, dry_run: bool, batch_size: int):
    """
    Migrate missing rows from source to target using INSERT IGNORE. Respects FK ordering
    and processes tables in configurable batches.
    """
    source_engine = create_engine(source)
    target_engine = create_engine(target)
    source_dialect = get_dialect(source_engine)
    target_dialect = get_dialect(target_engine)

    tables = (
        set(table.strip() for table in tables.split(","))
        if tables
        else get_shared_tables(source_engine, target_engine, source_dialect, target_dialect)
    )

    if dry_run:
        for table in tables:
            print(table)
        return

    run_migration(source_engine, target_engine, source_dialect, target_dialect, tables, batch_size)


@cli.command()
@click.option("--source", envvar="SOURCE_DB_URL", required=True, help="""SQLAlchemy connection string for the source database (e.g. mysql+pymysql://user:pass@host:3306/db).
Falls back to SOURCE_DB_URL env var.""")
@click.option("--target", envvar="TARGET_DB_URL", required=True, help="""SQLAlchemy connection string for the target database (e.g. mysql+pymysql://user:pass@host:3306/db).
Falls back to TARGET_DB_URL env var.""")
@click.option("--tables", required=False, help="""Shared table list between the two databases.
Comma-separated list of tables to process (e.g. users,orders,products). Defaults to all shared tables.""")
def validate(source: str, target: str, tables: set):
    """
    Verify migration completeness by comparing primary keys between source and target.
    Reports any rows present in source but missing from target.
    """
    source_engine = create_engine(source)
    target_engine = create_engine(target)
    source_dialect = get_dialect(source_engine)
    target_dialect = get_dialect(target_engine)

    tables = (
        set(table.strip() for table in tables.split(","))
        if tables
        else get_shared_tables(source_engine, target_engine, source_dialect, target_dialect)
    )

    run_validation(source_engine, target_engine, source_dialect, target_dialect, tables)


if __name__ == "__main__":
    cli()
