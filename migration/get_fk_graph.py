import pandas as pd
from sqlalchemy import Engine

from dialects import get_dialect


def get_fk_graph(engine: Engine) -> pd.DataFrame:
    """Fetch the foreign key dependency graph from the database."""
    return get_dialect(engine).get_foreign_keys(engine)
