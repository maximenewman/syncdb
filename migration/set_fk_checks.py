from sqlalchemy import Connection

from dialects import Dialect, FKCheckPermissionError


def set_fk_checks(connection: Connection, dialect: Dialect, enabled: bool) -> bool:
    """
    Toggle foreign key constraint checks on the target session.

    The setting is session-scoped, so this must run on the same connection
    that carries the inserts, and must be committed to survive the per-table
    transactions that follow.

    Returns True if the setting was applied, False if the server refused it.
    """
    state = "enabled" if enabled else "disabled"
    try:
        dialect.set_fk_checks(connection, enabled)
        connection.commit()
    except FKCheckPermissionError as error:
        connection.rollback()
        print(f"Warning: FK checks could not be {state} - {error}")
        print(
            "Continuing: tables load in FK-dependency order, so this only "
            "matters for circular FK groups."
        )
        return False

    print(f"FK checks {state}")
    return True
