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
    pass

@cli.command()
@click.option("--source", envvar="SOURCE_DB_URL", required=True, help="Source DB connection string")
@click.option("--target", envvar="TARGET_DB_URL", required=True, help="Target DB connection string")
def compare(source: str, target: str) -> None:
    """
    Compare the contents of the two databases, and output their differences
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
def migrate():
    pass

@cli.command()
def validate():
    pass