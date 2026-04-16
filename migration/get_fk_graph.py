import pandas as pd
from sqlalchemy import text, Engine
from queries.information_schema import FOREIGN_KEYS

def get_fk_graph(engine: Engine) -> pd.DataFrame:
    """Fetch the foreing key dependency graph from the database."""
    return pd.read_sql(text(FOREIGN_KEYS), engine)