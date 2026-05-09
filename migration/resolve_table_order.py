import pandas as pd
from collections import defaultdict, deque


def resolve_table_order(fk_df: pd.DataFrame, tables: set) -> list:
    """
    Return tables sorted in FK-safe insertion order using topological sort,
    so parent tables are always migrated before their dependents.
    Tables with circular FK dependencies are appended at the end with a warning.
    """

    in_degree = defaultdict(int)
    dependents = defaultdict(list)

    for table in tables:
        in_degree[table] = 0

    for _, row in fk_df.iterrows():
        child = row["table_name"]
        parent = row["referenced_table_name"]

        if child in tables and parent in tables and child != parent:
            in_degree[child] += 1
            dependents[parent].append(child)

    queue = deque(table for table in tables if in_degree[table] == 0)
    ordered = []

    while queue:
        table = queue.popleft()
        ordered.append(table)
        for dependent in dependents[table]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    remaining = tables - set(ordered)
    if remaining:
        print(f"Warning: Circular FK deps among: {remaining}")
        ordered.extend(sorted(remaining))

    return ordered
