# syncdb

A command-line tool for migrating data between MySQL databases. Built for the common real-world scenario: you have an old database and a new one with the same (or similar) schema, and you need to bring them in sync — without overwriting data that already exists in the target.

## What it does

syncdb connects to two MySQL databases, figures out what's different between them, and moves the missing rows from source to target. It handles the details that make database migrations tricky: foreign key ordering, schema comparison, batch processing, conflict handling, and post-migration validation.

```
syncdb compare  --source $SOURCE_DB_URL --target $TARGET_DB_URL    # See schema differences
syncdb migrate  --source $SOURCE_DB_URL --target $TARGET_DB_URL    # Move missing rows
syncdb validate --source $SOURCE_DB_URL --target $TARGET_DB_URL    # Verify everything landed
```

## Why this exists

Most database migration tools fall into two camps: full-featured ETL frameworks that require a week of configuration, or raw `mysqldump` which gives you no control over what happens when schemas don't perfectly match or the target already has data.

syncdb sits in between. It's a focused tool that does one thing well: sync data between two MySQL databases with full visibility into what's happening at each step.

## Features

- **Auto-discovery** — Finds shared tables between source and target automatically. No config files to maintain.
- **Schema comparison** — Compares every column across both databases and reports differences: missing columns, type changes, tables that exist in only one side.
- **Foreign key ordering** — Resolves the dependency graph so parent tables load before children. No FK violations during migration.
- **INSERT IGNORE** — Skips rows that already exist in the target. Existing data is never overwritten.
- **Batch processing** — Configurable batch size (default 100 rows) to control memory usage and provide progress visibility.
- **Per-table error handling** — If one table fails, the rest continue. You get a clear report of what succeeded and what needs attention.
- **Primary key validation** — After migration, verifies that every primary key from the source exists in the target. Reports exactly which rows are missing if any.
- **Dry run mode** — Preview the full table list without writing anything to the target.

## Installation

```bash
git clone https://github.com/maximenewman/syncdb.git
cd syncdb
uv sync
```

### Requirements

- Python 3.12+
- Access to both MySQL databases (source and target)

## Quick start

### 1. Configure connections

Connection strings can be passed directly as flags or set via environment variables in a `.env` file:

```
SOURCE_DB_URL=mysql+pymysql://user:pass@source-host:3306/mydb
TARGET_DB_URL=mysql+pymysql://user:pass@target-host:3306/mydb
```

### 2. Compare schemas

Before migrating, see what's different between your databases:

```bash
syncdb compare \
  --source "mysql+pymysql://user:pass@source-host:3306/mydb" \
  --target "mysql+pymysql://user:pass@target-host:3306/mydb"
```

This outputs a table-by-table and column-by-column diff showing:
- Tables that exist in only one database
- Columns that were added, removed, or changed type
- Row counts for every table in both databases

### 3. Dry run

Preview which tables would be migrated without writing anything:

```bash
syncdb migrate \
  --source "mysql+pymysql://user:pass@source-host:3306/mydb" \
  --target "mysql+pymysql://user:pass@target-host:3306/mydb" \
  --dry-run
```

### 4. Migrate

Run the actual migration:

```bash
syncdb migrate \
  --source "mysql+pymysql://user:pass@source-host:3306/mydb" \
  --target "mysql+pymysql://user:pass@target-host:3306/mydb"
```

### 5. Validate

Confirm every source row exists in the target:

```bash
syncdb validate \
  --source "mysql+pymysql://user:pass@source-host:3306/mydb" \
  --target "mysql+pymysql://user:pass@target-host:3306/mydb"
```

## Options

| Flag | Description | Default |
|---|---|---|
| `--source` | MySQL connection string for the source database | `$SOURCE_DB_URL` env var |
| `--target` | MySQL connection string for the target database | `$TARGET_DB_URL` env var |
| `--tables` | Comma-separated list of specific tables to process | All shared tables |
| `--batch-size` | Number of rows per INSERT batch | 100 |
| `--dry-run` | Preview tables to migrate without writing any data | Off |

## How it works

syncdb runs in five phases:

1. **Introspect** — Queries `INFORMATION_SCHEMA` on both databases to pull table and column metadata.
2. **Diff** — Compares schemas to identify matched columns, type changes, and missing fields.
3. **Order** — Builds a foreign key dependency graph and topologically sorts tables so parents load before children.
4. **Migrate** — Extracts rows from source and inserts into target using `INSERT IGNORE` in configurable batches. FK constraints are temporarily disabled during loading for safety and performance, then re-enabled after.
5. **Validate** — Compares primary keys between source and target to verify every source row exists in the target.

## Limitations

- **MySQL only** — Currently supports MySQL-to-MySQL migrations.
- **Same schema assumed** — Works best when source and target share the same table and column structure. Column renames and computed transformations are not supported.
- **INSERT IGNORE only** — Existing rows in the target are never updated. If you need to overwrite target data with source data, this tool is not the right fit.
- **No streaming for large tables** — Each table is fully read into memory before inserting. For tables with millions of rows, consider increasing batch size or running on a machine with sufficient RAM.

## Project structure

```
syncdb/
├── main.py                        # CLI entry point
├── migration/
│   ├── get_fk_graph.py            # Fetch FK dependency graph
│   ├── resolve_table_order.py     # Topological sort on FK graph
│   ├── migrate_table.py           # Extract + INSERT IGNORE for one table
│   ├── set_fk_checks.py           # Toggle FK constraints
│   └── migrate.py                 # Orchestrates full migration
├── validation/
│   ├── validate.py                # PK comparison for one table
│   └── run_validation.py          # Runs validation across all tables
├── comparison/
│   ├── comparison.py              # Schema diff logic
│   └── empty_tables.py            # Row count report
├── queries/
│   └── information_schema.py      # All SQL queries
└── pyproject.toml
```

## License

MIT
