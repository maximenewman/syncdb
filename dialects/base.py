from abc import ABC, abstractmethod

import pandas as pd
from sqlalchemy import Engine


class Dialect(ABC):
    """
    Database-specific behaviour behind a single interface.

    Every method that returns a DataFrame guarantees a fixed set of column
    names, regardless of the underlying database. Consumers in migration/,
    comparison/, and validation/ rely on these names and must never see
    dialect-specific column naming.
    """

    @abstractmethod
    def get_all_tables(self, engine: Engine) -> set[str]:
        """Return the set of base table names in the connected database."""

    @abstractmethod
    def get_columns(self, engine: Engine, table_name: str) -> pd.DataFrame:
        """
        Return one row per column, ordered by position, with EXACTLY these
        columns:
            COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT,
            EXTRA, ORDINAL_POSITION
        """

    @abstractmethod
    def get_foreign_keys(self, engine: Engine) -> pd.DataFrame:
        """
        Return one row per foreign-key relationship with EXACTLY these
        columns:
            TABLE_NAME, REFERENCED_TABLE_NAME
        """

    @abstractmethod
    def get_primary_keys(self, engine: Engine, table_name: str) -> list[str]:
        """Return the primary-key column names for a table, in key order."""

    @abstractmethod
    def set_fk_checks(self, engine: Engine, enabled: bool) -> None:
        """Toggle foreign-key constraint enforcement on the connection."""

    @abstractmethod
    def insert_skipping_duplicates_sql(self, table_name: str, columns: list[str]) -> str:
        """
        Build an INSERT statement that silently skips rows that would violate
        a unique/primary-key constraint.
            MySQL    -> INSERT IGNORE INTO ...
            Postgres -> INSERT INTO ... ON CONFLICT DO NOTHING
        Values are bound with named placeholders matching the column names.
        """
