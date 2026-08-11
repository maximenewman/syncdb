from sqlalchemy import Engine

from .base import Dialect, FKCheckPermissionError
from .mysql import MySQLDialect
from .postgres import PostgresDialect


_REGISTRY: dict[str, type[Dialect]] = {
    MySQLDialect.name: MySQLDialect,
    PostgresDialect.name: PostgresDialect,
}


def get_dialect(engine: Engine) -> Dialect:
    """Return a Dialect instance matching the engine's backend."""
    backend = engine.dialect.name
    try:
        return _REGISTRY[backend]()
    except KeyError:
        raise ValueError(
            f"Unsupported database backend: {backend!r}. "
            f"Supported: {sorted(_REGISTRY)}"
        )


__all__ = [
    "Dialect",
    "FKCheckPermissionError",
    "MySQLDialect",
    "PostgresDialect",
    "get_dialect",
]
