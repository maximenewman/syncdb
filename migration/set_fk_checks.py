from sqlalchemy import text, Engine

def set_fk_checks(engine: Engine, enabled: bool) -> None:
    """
    Toggle foreign key constraint checks on the target database.
    """
    value = 1 if enabled else 0
    with engine.connect() as conn:
        conn.execute(text(f"SET FOREIGN_KEY_CHECKS = {value}"))
        conn.commit()
    state = "enabled" if enabled else "disabled"
    print(f"FK checks {state}")