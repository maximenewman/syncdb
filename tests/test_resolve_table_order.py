import pandas as pd
import pytest

from migration import resolve_table_order


def fk_graph(*edges) -> pd.DataFrame:
    """Build an FK DataFrame from (child, parent) pairs."""
    return pd.DataFrame(
        list(edges), columns=["table_name", "referenced_table_name"]
    )


def assert_before(ordered: list, earlier: str, later: str) -> None:
    assert ordered.index(earlier) < ordered.index(later), (
        f"expected {earlier!r} before {later!r} in {ordered}"
    )


def test_parents_load_before_children():
    graph = fk_graph(("orders", "users"), ("order_items", "orders"))
    ordered = resolve_table_order(graph, {"users", "orders", "order_items"})

    assert_before(ordered, "users", "orders")
    assert_before(ordered, "orders", "order_items")


def test_returns_every_requested_table():
    graph = fk_graph(("orders", "users"))
    tables = {"users", "orders", "unrelated"}

    assert set(resolve_table_order(graph, tables)) == tables


def test_ignores_edges_outside_the_requested_set():
    # An FK onto a table we are not migrating must not block its child.
    graph = fk_graph(("orders", "users"), ("orders", "archived_accounts"))
    ordered = resolve_table_order(graph, {"users", "orders"})

    assert set(ordered) == {"users", "orders"}
    assert_before(ordered, "users", "orders")


def test_self_reference_does_not_deadlock():
    # A table whose FK points at itself would otherwise never reach
    # in_degree 0 and get dropped from the ordering.
    graph = fk_graph(("employees", "employees"))
    ordered = resolve_table_order(graph, {"employees"})

    assert ordered == ["employees"]


def test_circular_dependency_is_reported_not_dropped(capsys):
    graph = fk_graph(("a", "b"), ("b", "a"))
    ordered = resolve_table_order(graph, {"a", "b"})

    assert set(ordered) == {"a", "b"}
    assert "Circular FK deps" in capsys.readouterr().out


def test_empty_graph_returns_all_tables():
    ordered = resolve_table_order(fk_graph(), {"a", "b", "c"})

    assert set(ordered) == {"a", "b", "c"}


def test_no_tables_returns_empty():
    assert resolve_table_order(fk_graph(("a", "b")), set()) == []
