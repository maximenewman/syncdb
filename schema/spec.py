from dataclasses import dataclass, field
from enum import Enum


class CanonicalType(str, Enum):
    """
    Backend-neutral column types.

    Source dialects describe their columns in these terms and target dialects
    render DDL from them, so a type mapping is written once per dialect
    against this vocabulary instead of once per pair of backends.
    """

    BOOLEAN = "boolean"
    SMALLINT = "smallint"
    INTEGER = "integer"
    BIGINT = "bigint"
    NUMERIC = "numeric"
    REAL = "real"
    DOUBLE = "double"
    CHAR = "char"
    VARCHAR = "varchar"
    TEXT = "text"
    BINARY = "binary"
    DATE = "date"
    TIME = "time"
    TIMESTAMP = "timestamp"
    TIMESTAMPTZ = "timestamptz"
    JSON = "json"
    UUID = "uuid"


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    type: CanonicalType
    nullable: bool = True
    # Set only for the types that carry them: length for char/varchar/binary,
    # precision and scale for numeric.
    length: int | None = None
    precision: int | None = None
    scale: int | None = None
    default: str | None = None
    # True for MySQL AUTO_INCREMENT and Postgres identity/serial columns.
    is_identity: bool = False
    # The source's own type string, kept for diagnostics only.
    native_type: str | None = None


@dataclass(frozen=True)
class IndexSpec:
    name: str
    columns: tuple[str, ...]
    unique: bool = False


@dataclass(frozen=True)
class ForeignKeySpec:
    name: str
    columns: tuple[str, ...]
    referenced_table: str
    referenced_columns: tuple[str, ...]


@dataclass
class TableSpec:
    name: str
    columns: list[ColumnSpec] = field(default_factory=list)
    primary_key: tuple[str, ...] = ()
    indexes: list[IndexSpec] = field(default_factory=list)
    foreign_keys: list[ForeignKeySpec] = field(default_factory=list)
