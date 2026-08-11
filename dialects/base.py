from abc import ABC, abstractmethod
from typing import Sequence

import pandas as pd
from sqlalchemy import Connection, Engine


class FKCheckPermissionError(Exception):
    """
    Raised when the server refuses to toggle foreign key enforcement.

    Postgres gates `session_replication_role` behind superuser, so this is
    expected on managed instances. Callers should treat it as a downgrade
    (rely on FK-ordered loading) rather than a fatal error.
    """


class Dialect(ABC):
    """
    Database-specific operations consumed by syncdb's migration, comparison,
    and validation modules. Implementations normalize results to a common
    shape so callers don't have to know which engine they're talking to.

    Standardized DataFrame column names:
      - get_columns: column_name, column_type, is_nullable, column_default,
        ordinal_position
      - get_foreign_keys: table_name, referenced_table_name

    Standardized value conventions:
      - is_nullable is the string 'YES' or 'NO', matching INFORMATION_SCHEMA.
      - column_type is the full type including modifiers ('varchar(255)' on
        MySQL, 'character varying(255)' on Postgres). Types are NOT normalized
        across backends; comparing them across dialects is the mapping layer's
        job, not this one's.
      - Table and column names are returned exactly as the catalog stores them.
        No case folding is applied, so a MySQL `Users` and a Postgres `users`
        are distinct names to every caller.
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
    def set_fk_checks(self, connection: Connection, enabled: bool) -> None:
        """
        Enable or disable FK constraint enforcement.

        Takes a Connection rather than an Engine because the underlying switch
        is session-scoped on every supported backend: the caller must run its
        inserts on this same connection for the setting to apply, and must
        commit for it to outlive the current transaction.

        Raises FKCheckPermissionError if the server refuses the change.
        """

    @abstractmethod
    def insert_skipping_duplicates_sql(self, table: str, columns: Sequence[str]) -> str:
        """SQL that inserts a row and silently skips on PK/unique conflict."""

    @abstractmethod
    def quote_identifier(self, name: str) -> str:
        """Quote a table or column name for safe interpolation."""

    def select_all_sql(self, table: str) -> str:
        """SQL to read every row of a table."""
        return f"SELECT * FROM {self.quote_identifier(table)}"

    def count_rows_sql(self, table: str) -> str:
        """SQL to count rows in a table."""
        return f"SELECT COUNT(*) FROM {self.quote_identifier(table)}"
