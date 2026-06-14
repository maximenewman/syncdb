from sqlalchemy import Engine

from dialects import Dialect
from .validate import validate_table


def run_validation(
    source_engine: Engine,
    target_engine: Engine,
    source_dialect: Dialect,
    target_dialect: Dialect,
    tables: set,
) -> list:
    """
    Compare primary keys for every table between source and target.
    Prints a per-table pass/fail summary and a final totals report.
    Returns a list of per-table result dicts.
    """

    results = []
    for table_name in sorted(tables):
        result = validate_table(
            table_name,
            source_engine,
            target_engine,
            source_dialect,
            target_dialect,
        )
        results.append(result)

    passed = sum(1 for result in results if result["status"] == "pass")
    failed = [result for result in results if result["status"] == "fail"]
    skipped = sum(1 for result in results if result["status"] == "no_pk")
    total_missing = sum(result.get("missing_in_new", 0) for result in results)

    print(f"{'='*20}")
    print(f"RESULTS")
    print(f"Passed: {passed}")
    print(f"Failed: {len(failed)}")
    print(f"Skipped: {skipped} (no primary key)")

    if failed:
        print(f"Tables still missing rows ({total_missing} total):")
        for table_result in failed:
            print(f"{table_result['table']}: {table_result['missing_in_new']} rows missing")
        print(f"{'='*20}")

    return results
