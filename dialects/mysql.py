from typing import Sequence

import pandas as pd
from sqlalchemy import Engine, text

from .base import Dialect


_ALL_TABLES = """
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE'
  AND TABLE_SCHEMA = DATABASE()
"""

_COLUMNS_FOR_TABLE = """
SELECT
    COLUMN_NAME       AS column_name,
    COLUMN_TYPE       AS column_type,
    IS_NULLABLE       AS is_nullable,
    COLUMN_DEFAULT    AS column_default,
    ORDINAL_POSITION  AS ordinal_position
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = :table_name
ORDER BY ORDINAL_POSITION
"""

_FOREIGN_KEYS = """
SELECT
    TABLE_NAME            AS table_name,
    REFERENCED_TABLE_NAME AS referenced_table_name
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE()
  AND REFERENCED_TABLE_NAME IS NOT NULL
GROUP BY TABLE_NAME, REFERENCED_TABLE_NAME
"""

_PRIMARY_KEYS = """
SELECT COLUMN_NAME AS column_name
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = :table_name
  AND CONSTRAINT_NAME = 'PRIMARY'
ORDER BY ORDINAL_POSITION
"""


class MySQLDialect(Dialect):
    name = "mysql"

    def get_all_tables(self, engine: Engine) -> set[str]:
        df = pd.read_sql(text(_ALL_TABLES), engine)
        return set(df["TABLE_NAME"])

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

    def set_fk_checks(self, engine: Engine, enabled: bool) -> None:
        value = 1 if enabled else 0
        with engine.connect() as conn:
            conn.execute(text(f"SET FOREIGN_KEY_CHECKS = {value}"))
            conn.commit()

    def select_all_sql(self, table: str) -> str:
        return f"SELECT * FROM {self.quote_identifier(table)}"

    def count_rows_sql(self, table: str) -> str:
        return f"SELECT COUNT(*) FROM {self.quote_identifier(table)}"

    def insert_ignore_sql(self, table: str, columns: Sequence[str]) -> str:
        cols_sql = ", ".join(self.quote_identifier(c) for c in columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        return (
            f"INSERT IGNORE INTO {self.quote_identifier(table)} "
            f"({cols_sql}) VALUES ({placeholders})"
        )

    def quote_identifier(self, name: str) -> str:
        escaped = name.replace("`", "``")
        return f"`{escaped}`"
