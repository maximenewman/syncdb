import click
import pandas as pd                                                                             
from dotenv import load_dotenv                                                                   
from sqlalchemy import create_engine, Engine

from queries.information_schema import ALL_TABLES, COLUMNS_FOR_TABLE
from comparison.comparison import compare_tables, compare_columns
from comparison.empty_tables import report_empty_tables
from migration.migrate import run_migration
from validation.run_validation import run_validation

load_dotenv()

def get_shared_tables(source_engine: Engine, target_engine:Engine)-> set:
    source_tables = set(pd.read_sql(ALL_TABLES, source_engine)["TABLE_NAME"])
    target_tables = set(pd.read_sql(ALL_TABLES, target_engine)["TABLE_NAME"])
    return source_tables & target_tables

@click.group()
def cli():
    """
    Sync data between two MySQL databases.
    """

@cli.command()
@click.option("--source", envvar="SOURCE_DB_URL", required=True, help="""MySQL connection string for the source database (e.g. mysql+pymysql://user:pass@host:3306/db).  
Falls back to SOURCE_DB_URL env var.""")
@click.option("--target", envvar="TARGET_DB_URL", required=True, help="""MySQL connection string for the source database (e.g. mysql+pymysql://user:pass@host:3306/db).  
Falls back to SOURCE_DB_URL env var.""")
def compare(source: str, target: str) -> None:
    """
    Compare schemas and row counts between source and target. Reports missing tables,    
    column differences, and empty tables.
    """
    source_engine = create_engine(source)
    target_engine = create_engine(target)

   
    compare_tables(ALL_TABLES, [source_engine, target_engine])

    shared = get_shared_tables(source_engine, target_engine)
    all_diffs = []
    for table in sorted(shared):
        diff = compare_columns(COLUMNS_FOR_TABLE, table, [source_engine, target_engine])
        diff["TABLE_NAME"] = table
        all_diffs.append(diff)
    
    full_report = pd.concat(all_diffs, ignore_index=True)

    problems = full_report[full_report["status"] != "matched"]
    output = problems[["TABLE_NAME", "COLUMN_NAME", "COLUMN_TYPE_old", "COLUMN_TYPE_new", "status"]]

    if output.empty:
        print("No schema differences found.")
    else:
        print(output.to_string(index=False))

    report_empty_tables(source_engine, "Source Database")
    report_empty_tables(target_engine, "Target Database")

    return

@cli.command()
@click.option("--source", envvar="SOURCE_DB_URL", required=True, help="""MySQL connection string for the source database (e.g. mysql+pymysql://user:pass@host:3306/db).  
Falls back to SOURCE_DB_URL env var.""")
@click.option("--target", envvar="TARGET_DB_URL", required=True, help="""MySQL connection string for the source database (e.g. mysql+pymysql://user:pass@host:3306/db).  
Falls back to SOURCE_DB_URL env var.""")
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
    tables = set(table.strip() for table in tables.split(",")) if tables else get_shared_tables(source_engine, target_engine)

    if dry_run:
        for table in tables:
            print(table)
        return

    run_migration(source_engine, target_engine, tables, batch_size)
    return

@cli.command()
@click.option("--source", envvar="SOURCE_DB_URL", required=True, help="""MySQL connection string for the source database (e.g. mysql+pymysql://user:pass@host:3306/db).  
Falls back to SOURCE_DB_URL env var.""")
@click.option("--target", envvar="TARGET_DB_URL", required=True, help="""MySQL connection string for the source database (e.g. mysql+pymysql://user:pass@host:3306/db).  
Falls back to SOURCE_DB_URL env var.""")
@click.option("--tables", required=False, help="""Shared table list between the two databases.
Comma-separated list of tables to process (e.g. users,orders,products). Defaults to all shared tables.""")
def validate(source: str, target: str, tables: set):
    """
    Verify migration completeness by comparing primary keys between source and target.  
    Reports any rows present in source but missing from target.
    """
    source_engine = create_engine(source)
    target_engine = create_engine(target)

    tables = set(table.strip() for table in tables.split(",")) if tables else get_shared_tables(source_engine, target_engine)

    run_validation(source_engine, target_engine, tables)

    return

if __name__ == "__main__":
    cli()