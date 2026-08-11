from typing import Sequence

import pandas as pd
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError

from .base import Dialect, FKCheckPermissionError


# Postgres has no DATABASE()-style "current schema" function that matches
# MySQL's one-database-per-connection model, so every query is scoped to
# current_schema() -- the first writable entry on the connection's
# search_path. That keeps the dialect honest about search_path overrides
# instead of hard-coding 'public'.

_ALL_TABLES = """
SELECT table_name AS table_name
FROM information_schema.tables
WHERE table_type = 'BASE TABLE'
  AND table_schema = current_schema()
"""

# information_schema.columns supplies the standardized fields, but its
# data_type drops modifiers ('character varying' with no length). format_type
# on the pg_attribute row restores them, giving the closest analogue to
# MySQL's COLUMN_TYPE.
_COLUMNS_FOR_TABLE = """
SELECT
    c.column_name                        AS column_name,
    format_type(a.atttypid, a.atttypmod) AS column_type,
    c.is_nullable                        AS is_nullable,
    c.column_default                     AS column_default,
    c.ordinal_position                   AS ordinal_position
FROM information_schema.columns c
JOIN pg_namespace n
  ON n.nspname = c.table_schema
JOIN pg_class pc
  ON pc.relname = c.table_name
 AND pc.relnamespace = n.oid
JOIN pg_attribute a
  ON a.attrelid = pc.oid
 AND a.attname = c.column_name
WHERE c.table_schema = current_schema()
  AND c.table_name = :table_name
ORDER BY c.ordinal_position
"""

# pg_constraint rather than information_schema.referential_constraints: the
# catalog view hides constraints on tables the connected user doesn't own,
# which would silently drop edges from the dependency graph.
_FOREIGN_KEYS = """
SELECT DISTINCT
    child.relname  AS table_name,
    parent.relname AS referenced_table_name
FROM pg_constraint con
JOIN pg_class child
  ON child.oid = con.conrelid
JOIN pg_class parent
  ON parent.oid = con.confrelid
JOIN pg_namespace n
  ON n.oid = child.relnamespace
WHERE con.contype = 'f'
  AND n.nspname = current_schema()
"""

# indkey is an int2vector of column numbers in index order; unnesting it WITH
# ORDINALITY preserves that order for composite keys, which a plain
# `attnum = ANY(indkey)` join would scramble.
_PRIMARY_KEYS = """
SELECT a.attname AS column_name
FROM pg_index i
JOIN pg_class c
  ON c.oid = i.indrelid
JOIN pg_namespace n
  ON n.oid = c.relnamespace
CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord)
JOIN pg_attribute a
  ON a.attrelid = c.oid
 AND a.attnum = k.attnum
WHERE i.indisprimary
  AND n.nspname = current_schema()
  AND c.relname = :table_name
ORDER BY k.ord
"""


class PostgresDialect(Dialect):
    # Matches SQLAlchemy's backend name so the registry lookup in
    # dialects/__init__.py resolves it for both psycopg and psycopg2 URLs.
    name = "postgresql"

    def get_all_tables(self, engine: Engine) -> set[str]:
        df = pd.read_sql(text(_ALL_TABLES), engine)
        return set(df["table_name"])

    def get_columns(self, engine: Engine, table: str) -> pd.DataFrame:
        return pd.read_sql(
            text(_COLUMNS_FOR_TABLE),
            engine,
            params={"table_name": table},
        )

    def get_foreign_keys(self, engine: Engine) -> pd.DataFrame:
        return pd.read_sql(text(_FOREIGN_KEYS), engine)

    def get_primary_keys(self, engine: Engine, table: str) -> list[str]:
        df = pd.read_sql(
            text(_PRIMARY_KEYS),
            engine,
            params={"table_name": table},
        )
        return df["column_name"].tolist()

    def set_fk_checks(self, connection: Connection, enabled: bool) -> None:
        # Postgres has no per-constraint switch equivalent to MySQL's
        # FOREIGN_KEY_CHECKS. session_replication_role = replica suppresses
        # all triggers, FK triggers included, and is superuser-gated -- hence
        # the FKCheckPermissionError contract for managed instances.
        role = "origin" if enabled else "replica"
        try:
            connection.execute(text(f"SET session_replication_role = {role}"))
        except DBAPIError as error:
            raise FKCheckPermissionError(
                f"server refused SET session_replication_role = {role}: {error}"
            ) from error

    def insert_skipping_duplicates_sql(self, table: str, columns: Sequence[str]) -> str:
        cols_sql = ", ".join(self.quote_identifier(c) for c in columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        # A bare ON CONFLICT DO NOTHING covers every unique and exclusion
        # constraint, which is the closest match to INSERT IGNORE. Unlike
        # INSERT IGNORE it does not also swallow type or FK errors -- those
        # still raise, which is the safer behaviour.
        return (
            f"INSERT INTO {self.quote_identifier(table)} "
            f"({cols_sql}) VALUES ({placeholders}) "
            f"ON CONFLICT DO NOTHING"
        )

    def quote_identifier(self, name: str) -> str:
        escaped = name.replace('"', '""')
        return f'"{escaped}"'
