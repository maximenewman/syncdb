from abc import ABC, abstractmethod
from typing import Sequence

import pandas as pd
from sqlalchemy import Engine


class Dialect(ABC):
    """
    Database-specific operations consumed by syncdb's migration, comparison,
    and validation modules. Implementations normalize results to a common
    shape so callers don't have to know which engine they're talking to.

    Standardized DataFrame column names:
      - get_columns: column_name, column_type, is_nullable, column_default,
        ordinal_position
      - get_foreign_keys: table_name, referenced_table_name
    """

    name: str

    @abstractmethod
    def get_all_tables(self, engine: Engine) -> set[str]:
        """Return the set of base-table names in the connected schema."""

    @abstractmethod
    def get_columns(self, engine: Engine, table: str) -> pd.DataFrame:
        """Return column metadata for a table."""

    @abstractmethod
    def get_foreign_keys(self, engine: Engine) -> pd.DataFrame:
        """Return the FK dependency graph (child -> parent) for the schema."""

    @abstractmethod
    def get_primary_keys(self, engine: Engine, table: str) -> list[str]:
        """Return ordered PK column names, or empty list if no PK."""

    @abstractmethod
    def set_fk_checks(self, engine: Engine, enabled: bool) -> None:
        """Enable or disable FK constraint enforcement on this connection."""

    @abstractmethod
    def select_all_sql(self, table: str) -> str:
        """SQL to read every row of a table."""

    @abstractmethod
    def count_rows_sql(self, table: str) -> str:
        """SQL to count rows in a table."""

    @abstractmethod
    def insert_ignore_sql(self, table: str, columns: Sequence[str]) -> str:
        """SQL that inserts a row and silently skips on PK/unique conflict."""

    @abstractmethod
    def quote_identifier(self, name: str) -> str:
        """Quote a table or column name for safe interpolation."""
