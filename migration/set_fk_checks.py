from sqlalchemy import Engine

from dialects import Dialect


def set_fk_checks(engine: Engine, dialect: Dialect, enabled: bool) -> None:
    """Toggle foreign key constraint checks on the target database."""
    dialect.set_fk_checks(engine, enabled)
    state = "enabled" if enabled else "disabled"
    print(f"FK checks {state}")
