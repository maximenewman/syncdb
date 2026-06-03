import pandas as pd
from sqlalchemy import Engine, text

from .base import Dialect

_ALL_TABLES = """
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = DATABASE();
"""

_COLUMNS_FOR_TABLE = """
SELECT
    COLUMN_NAME,
    COLUMN_TYPE,
    IS_NULLABLE,
    COLUMN_DEFAULT,
    EXTRA,
    ORDINAL_POSITION
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = :table_name
ORDER BY ORDINAL_POSITION;
"""

_FOREIGN_KEYS = """
SELECT
    TABLE_NAME,
    REFERENCED_TABLE_NAME
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE()
    AND REFERENCED_TABLE_NAME IS NOT NULL
GROUP BY TABLE_NAME, REFERENCED_TABLE_NAME;
"""

_PRIMARY_KEYS = """
SELECT COLUMN_NAME
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = :table_name
    AND CONSTRAINT_NAME = 'PRIMARY'
ORDER BY ORDINAL_POSITION;
"""


class MySQLDialect(Dialect):
    """MySQL implementation of the dialect interface."""

    def get_all_tables(self, engine: Engine) -> set[str]:
        df = pd.read_sql(text(_ALL_TABLES), engine)
        return set(df["TABLE_NAME"])

    def get_columns(self, engine: Engine, table_name: str) -> pd.DataFrame:
        with engine.connect() as conn:
            return pd.read_sql(
                text(_COLUMNS_FOR_TABLE), conn, params={"table_name": table_name}
            )

    def get_foreign_keys(self, engine: Engine) -> pd.DataFrame:
        return pd.read_sql(text(_FOREIGN_KEYS), engine)

    def get_primary_keys(self, engine: Engine, table_name: str) -> list[str]:
        with engine.connect() as conn:
            df = pd.read_sql(
                text(_PRIMARY_KEYS), conn, params={"table_name": table_name}
            )
        return df["COLUMN_NAME"].tolist()

    def set_fk_checks(self, engine: Engine, enabled: bool) -> None:
        value = 1 if enabled else 0
        with engine.connect() as conn:
            conn.execute(text(f"SET FOREIGN_KEY_CHECKS = {value}"))
            conn.commit()

    def insert_skipping_duplicates_sql(self, table_name: str, columns: list[str]) -> str:
        cols_sql = ", ".join(f"`{col}`" for col in columns)
        placeholders = ", ".join(f":{col}" for col in columns)
        return f"INSERT IGNORE INTO `{table_name}` ({cols_sql}) VALUES ({placeholders})"
