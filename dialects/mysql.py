from typing import Sequence

import pandas as pd
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError

from schema.spec import (
    CanonicalType,
    ColumnSpec,
    ForeignKeySpec,
    IndexSpec,
    TableSpec,
)

from .base import Dialect, FKCheckPermissionError


_ALL_TABLES = """
SELECT TABLE_NAME AS table_name
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

_COLUMNS_FOR_DDL = """
SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT,
       EXTRA, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = :table_name
ORDER BY ORDINAL_POSITION
"""

_INDEXES_FOR_TABLE = """
SELECT INDEX_NAME, NON_UNIQUE,
       GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) AS columns
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = :table_name
  AND INDEX_NAME <> 'PRIMARY'
GROUP BY INDEX_NAME, NON_UNIQUE
"""

_FOREIGN_KEYS_FOR_TABLE = """
SELECT CONSTRAINT_NAME,
       GROUP_CONCAT(COLUMN_NAME ORDER BY ORDINAL_POSITION) AS columns,
       REFERENCED_TABLE_NAME,
       GROUP_CONCAT(REFERENCED_COLUMN_NAME ORDER BY ORDINAL_POSITION) AS ref_columns
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = :table_name
  AND REFERENCED_TABLE_NAME IS NOT NULL
GROUP BY CONSTRAINT_NAME, REFERENCED_TABLE_NAME
"""

# MySQL DATA_TYPE -> CanonicalType. tinyint is resolved separately, since
# tinyint(1) is how MySQL spells boolean and the width is only in COLUMN_TYPE.
_TYPE_MAP = {
    "smallint": "SMALLINT",
    "mediumint": "INTEGER",
    "int": "INTEGER",
    "integer": "INTEGER",
    "bigint": "BIGINT",
    "decimal": "NUMERIC",
    "numeric": "NUMERIC",
    "float": "REAL",
    "double": "DOUBLE",
    "char": "CHAR",
    "varchar": "VARCHAR",
    "tinytext": "TEXT",
    "text": "TEXT",
    "mediumtext": "TEXT",
    "longtext": "TEXT",
    "binary": "BINARY",
    "varbinary": "BINARY",
    "tinyblob": "BINARY",
    "blob": "BINARY",
    "mediumblob": "BINARY",
    "longblob": "BINARY",
    "date": "DATE",
    "time": "TIME",
    "datetime": "TIMESTAMP",
    "timestamp": "TIMESTAMP",
    "year": "SMALLINT",
    "json": "JSON",
    # enum and set have no portable equivalent; both become text.
    "enum": "TEXT",
    "set": "TEXT",
}


class MySQLDialect(Dialect):
    name = "mysql"

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
        value = 1 if enabled else 0
        try:
            connection.execute(text(f"SET FOREIGN_KEY_CHECKS = {value}"))
        except DBAPIError as error:
            raise FKCheckPermissionError(
                f"server refused SET FOREIGN_KEY_CHECKS = {value}: {error}"
            ) from error

    def insert_skipping_duplicates_sql(self, table: str, columns: Sequence[str]) -> str:
        cols_sql = ", ".join(self.quote_identifier(c) for c in columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        return (
            f"INSERT IGNORE INTO {self.quote_identifier(table)} "
            f"({cols_sql}) VALUES ({placeholders})"
        )

    def quote_identifier(self, name: str) -> str:
        escaped = name.replace("`", "``")
        return f"`{escaped}`"

    def describe_table(self, engine: Engine, table: str) -> TableSpec:
        with engine.connect() as conn:
            rows = conn.execute(
                text(_COLUMNS_FOR_DDL), {"table_name": table}
            ).fetchall()
            indexes = conn.execute(
                text(_INDEXES_FOR_TABLE), {"table_name": table}
            ).fetchall()
            fks = conn.execute(
                text(_FOREIGN_KEYS_FOR_TABLE), {"table_name": table}
            ).fetchall()

        columns = []
        for (name, data_type, column_type, nullable, default, extra,
             char_len, precision, scale) in rows:
            columns.append(
                ColumnSpec(
                    name=name,
                    type=self._canonical_type(data_type, column_type),
                    nullable=nullable == "YES",
                    length=char_len,
                    precision=precision,
                    scale=scale,
                    default=default,
                    is_identity="auto_increment" in (extra or "").lower(),
                    native_type=column_type,
                )
            )

        return TableSpec(
            name=table,
            columns=columns,
            primary_key=tuple(self.get_primary_keys(engine, table)),
            indexes=[
                IndexSpec(
                    name=index_name,
                    columns=tuple(cols.split(",")),
                    unique=not non_unique,
                )
                for index_name, non_unique, cols in indexes
            ],
            foreign_keys=[
                ForeignKeySpec(
                    name=name,
                    columns=tuple(cols.split(",")),
                    referenced_table=ref_table,
                    referenced_columns=tuple(ref_cols.split(",")),
                )
                for name, cols, ref_table, ref_cols in fks
            ],
        )

    @staticmethod
    def _canonical_type(data_type: str, column_type: str) -> CanonicalType:
        data_type = (data_type or "").lower()
        if data_type == "tinyint":
            # tinyint(1) is MySQL's boolean; wider tinyints are real integers.
            return (
                CanonicalType.BOOLEAN
                if "(1)" in (column_type or "")
                else CanonicalType.SMALLINT
            )
        if data_type == "bit":
            return CanonicalType.BOOLEAN
        try:
            return CanonicalType[_TYPE_MAP[data_type]]
        except KeyError:
            raise ValueError(
                f"no canonical mapping for MySQL type {data_type!r} "
                f"(COLUMN_TYPE={column_type!r})"
            ) from None
