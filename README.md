# syncdb

A command-line tool for migrating data between SQL databases. Built for the common real-world scenario: you have an old database and a new one with the same (or similar) schema, and you need to bring them in sync — without overwriting data that already exists in the target.

Supports **MySQL** and **PostgreSQL** on either side, so MySQL → MySQL, MySQL → Postgres, and Postgres → Postgres migrations all work through the same commands.

## What it does

syncdb connects to two databases, figures out what's different between them, and moves the missing rows from source to target. It handles the details that make database migrations tricky: foreign key ordering, schema comparison, batch processing, conflict handling, and post-migration validation.

```
syncdb compare       --source $SOURCE_DB_URL --target $TARGET_DB_URL   # See schema differences
syncdb create-schema --source $SOURCE_DB_URL --target $TARGET_DB_URL   # Translate DDL for the target
syncdb rehearse      --source $SOURCE_DB_URL                           # Full dry run in Docker
syncdb migrate       --source $SOURCE_DB_URL --target $TARGET_DB_URL   # Move missing rows
syncdb validate      --source $SOURCE_DB_URL --target $TARGET_DB_URL   # Verify everything landed
```

## Why this exists

Most database migration tools fall into two camps: full-featured ETL frameworks that require a week of configuration, or raw `mysqldump` which gives you no control over what happens when schemas don't perfectly match or the target already has data.

syncdb sits in between. It's a focused tool that does one thing well: sync data between two databases with full visibility into what's happening at each step.

## Features

- **Auto-discovery** — Finds shared tables between source and target automatically. No config files to maintain.
- **Pluggable dialects** — Each backend's introspection and SQL generation lives behind one `Dialect` interface, so source and target can be different engines.
- **Schema comparison** — Compares every column across both databases and reports differences: missing columns, type changes, tables that exist in only one side.
- **Foreign key ordering** — Resolves the dependency graph so parent tables load before children. No FK violations during migration.
- **Conflict-skipping inserts** — Rows that already exist in the target are skipped, never overwritten (`INSERT IGNORE` on MySQL, `ON CONFLICT DO NOTHING` on Postgres).
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
- Access to both databases (source and target)
- **Every table must have a primary key.** syncdb uses primary keys for both row-skip semantics (`INSERT IGNORE`/`ON CONFLICT DO NOTHING`) and post-migration validation. Tables without a PK are skipped during validation and cannot be safely re-run.
- **Postgres URLs must name the driver.** syncdb ships psycopg 3, so use `postgresql+psycopg://…`. A bare `postgresql://…` makes SQLAlchemy reach for psycopg2 and fail at startup.
- **Disabling FK checks on Postgres needs superuser.** `session_replication_role = replica` is superuser-gated, and managed providers (DigitalOcean, RDS, Cloud SQL) do not grant it. syncdb detects the refusal, prints a warning, and continues — tables still load in FK-dependency order, so this only matters if your schema has *circular* FK dependencies. MySQL targets only need normal write access.

## Quick start

### 1. Configure connections

Connection strings can be passed directly as flags or set via environment variables in a `.env` file:

```
SOURCE_DB_URL=mysql+pymysql://user:pass@source-host:3306/mydb
TARGET_DB_URL=postgresql+psycopg://user:pass@target-host:5432/mydb?sslmode=require
```

Both sides accept either backend:

| Backend | Connection string |
|---|---|
| MySQL / MariaDB | `mysql+pymysql://user:pass@host:3306/dbname` |
| PostgreSQL | `postgresql+psycopg://user:pass@host:5432/dbname` |

Postgres connections are scoped to `current_schema()` — the first writable entry on the connection's `search_path`, normally `public`. Set `?options=-csearch_path%3Dmyschema` in the URL to target a different one.

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

### 3. Create the target schema

**`migrate` only moves rows between tables that already exist on both sides.** Pointed at an empty target it reports success while doing nothing, because there are no shared tables. If the target is empty, translate the schema first:

```bash
syncdb create-schema \
  --source "mysql+pymysql://user:pass@source-host:3306/mydb" \
  --target "postgresql+psycopg://user:pass@target-host:5432/mydb"
```

This prints the DDL for review. Add `--apply` to execute it. Tables are emitted in FK-dependency order with foreign keys last, so the script runs top to bottom without forward references.

### 4. Rehearse

Before touching a real target, run the whole migration against a disposable Postgres in Docker:

```bash
syncdb rehearse --source "mysql+pymysql://user:pass@source-host:3306/mydb" \
                --image postgres:15.18
```

This translates the schema, migrates every row, validates by primary key, then **migrates a second time and asserts that zero rows are inserted** — proving the run is repeatable and conflict-skipping works. Match `--image` to your real target's version. Nothing touches a real database, so this is where type and schema problems should surface. Use `--keep` to leave the container up for inspection.

### 5. Dry run

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
| `--source` | SQLAlchemy connection string for the source database | `$SOURCE_DB_URL` env var |
| `--target` | SQLAlchemy connection string for the target database | `$TARGET_DB_URL` env var |
| `--tables` | Comma-separated list of specific tables to process | All shared tables |
| `--batch-size` | Number of rows per INSERT batch | 100 |
| `--dry-run` | Preview tables to migrate without writing any data | Off |

## How it works

syncdb runs in five phases:

1. **Introspect** — Queries each backend's catalog (`INFORMATION_SCHEMA` on MySQL, `information_schema` plus `pg_catalog` on Postgres) to pull table and column metadata.
2. **Diff** — Compares schemas to identify matched columns, type changes, and missing fields.
3. **Order** — Builds a foreign key dependency graph and topologically sorts tables so parents load before children.
4. **Migrate** — Extracts rows from source and inserts into target with conflict-skipping inserts in configurable batches. FK constraints are temporarily disabled during loading, then re-enabled after. All writes share one connection, because the FK switch is session-scoped on both backends.
5. **Validate** — Compares primary keys between source and target to verify every source row exists in the target.

## Limitations

- **Identical names assumed** — Source and target must use the same table and column names, compared case-sensitively. A MySQL `Users` table will not match a Postgres `users` table. Renames and computed transformations are not supported.
- **Types are not translated** — `compare` reports each column's native type verbatim, so every column of a MySQL → Postgres pair shows as `type_changed` (`int(11)` vs `integer`). The target's tables must already exist with types the source data fits into; syncdb moves rows, it does not create or alter schema.
- **Inserts only** — Existing rows in the target are never updated. If you need to overwrite target data with source data, this tool is not the right fit.
- **NUL bytes are stripped** — MySQL stores `0x00` inside character columns; Postgres text types cannot hold them and reject the entire batch. Migrating to Postgres removes them and reports how many values were changed per batch. This is the one place syncdb alters a value rather than copying it.
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
├── dialects/
│   ├── base.py                    # Dialect abstract interface
│   └── mysql.py                   # MySQL implementation
└── pyproject.toml
```

## License

MIT
