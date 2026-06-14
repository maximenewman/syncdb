from sqlalchemy import Engine

from .base import Dialect
from .mysql import MySQLDialect


_REGISTRY: dict[str, type[Dialect]] = {
    "mysql": MySQLDialect,
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


__all__ = ["Dialect", "MySQLDialect", "get_dialect"]
