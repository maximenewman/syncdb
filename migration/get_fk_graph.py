import pandas as pd
from sqlalchemy import Engine

from dialects import Dialect


def get_fk_graph(engine: Engine, dialect: Dialect) -> pd.DataFrame:
    """Fetch the foreign key dependency graph from the database."""
    return dialect.get_foreign_keys(engine)
