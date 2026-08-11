from sqlalchemy import Engine

from dialects import Dialect
from migration import resolve_table_order


def generate_ddl(
    source_engine: Engine,
    source_dialect: Dialect,
    target_dialect: Dialect,
    tables: set | None = None,
) -> str:
    """
    Render DDL that recreates the source's tables on the target backend.

    syncdb moves rows but never creates schema, so a migration into an empty
    target needs this first. Tables are emitted in FK-dependency order and
    foreign keys are appended at the end, so the script applies top to bottom
    without forward references.

    Raises NotImplementedError if either dialect lacks the capability, naming
    which one is missing.
    """
    if tables is None:
        tables = source_dialect.get_all_tables(source_engine)

    ordered = resolve_table_order(
        source_dialect.get_foreign_keys(source_engine), set(tables)
    )

    specs = [source_dialect.describe_table(source_engine, name) for name in ordered]

    statements = [
        f"-- {len(specs)} tables, generated from a {source_dialect.name} source",
        f"-- for a {target_dialect.name} target",
        "",
    ]

    for spec in specs:
        statements.append(target_dialect.render_create_table(spec))
        statements.append("")

    index_statements = [
        line
        for spec in specs
        for line in target_dialect.render_indexes(spec)
    ]
    if index_statements:
        statements.append("-- indexes")
        statements.extend(index_statements)
        statements.append("")

    fk_statements = [
        line
        for spec in specs
        for line in target_dialect.render_foreign_keys(spec)
    ]
    if fk_statements:
        statements.append("-- foreign keys")
        statements.extend(fk_statements)

    return "\n".join(statements) + "\n"
