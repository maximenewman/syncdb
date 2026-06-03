from sqlalchemy import Engine

from .base import Dialect
from .mysql import MySQLDialect


def get_dialect(engine: Engine) -> Dialect:
    """Return the Dialect implementation matching an engine's database."""
    name = engine.dialect.name
    if name == "mysql":
        return MySQLDialect()
    raise ValueError(f"Unsupported database dialect: {name}")
