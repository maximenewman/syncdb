from sqlalchemy import Engine

from dialects import get_dialect


def set_fk_checks(engine: Engine, enabled: bool) -> None:
    """
    Toggle foreign key constraint checks on the target database.
    """
    get_dialect(engine).set_fk_checks(engine, enabled)
    state = "enabled" if enabled else "disabled"
    print(f"FK checks {state}")
