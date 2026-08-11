"""Backend-neutral schema description and DDL generation.

Only the spec types are re-exported here. generate_ddl lives in
schema.translate and must be imported from there: dialects imports
schema.spec, so pulling translate (which imports dialects) into this
__init__ would make the two packages circular.
"""
from .spec import (
    CanonicalType,
    ColumnSpec,
    ForeignKeySpec,
    IndexSpec,
    TableSpec,
)

__all__ = [
    "CanonicalType",
    "ColumnSpec",
    "ForeignKeySpec",
    "IndexSpec",
    "TableSpec",
]
