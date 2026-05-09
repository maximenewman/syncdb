import pandas as pd
from sqlalchemy import Engine, text

from dialects import Dialect


def _bar(n, max_n, width=30):
    filled = int(n / max_n * width) if max_n else 0
    return "#" * filled + "." * (width - filled)


def report_empty_tables(engine: Engine, dialect: Dialect, label: str) -> None:
    tables = sorted(dialect.get_all_tables(engine))

    with engine.connect() as conn:
        rows = [
            {
                "table": table,
                "row_count": conn.execute(text(dialect.count_rows_sql(table))).scalar(),
            }
            for table in tables
        ]

    df        = pd.DataFrame(rows).sort_values("row_count")
    empty     = df[df["row_count"] == 0]
    populated = df[df["row_count"] >  0]
    col_w     = max(len(t) for t in df["table"]) + 2 if not df.empty else 10
    max_rows  = populated["row_count"].max() if not populated.empty else 1
    sep       = "-" * (col_w + 45)

    print(f"\n{sep}")
    print(f"  {label}")
    print(f"  {'TABLE':<{col_w}} {'ROWS':>8}   DISTRIBUTION")
    print(f"{sep}")

    for _, r in populated.sort_values("row_count", ascending=False).iterrows():
        print(f"  {r['table']:<{col_w}} {r['row_count']:>8,}   {_bar(r['row_count'], max_rows)}")

    if not empty.empty:
        print(f"\n  -- EMPTY TABLES ({len(empty)}) --")
        for _, r in empty.iterrows():
            print(f"  {r['table']:<{col_w}} {r['row_count']:>8,}   (no data)")

    print(f"{sep}")
    print(f"  Total tables : {len(df)}")
    print(f"  Populated    : {len(populated)}")
    print(f"  Empty        : {len(empty)}\n")
