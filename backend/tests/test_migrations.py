import sqlite3

from migrations import apply, rollback_to, status


def test_migrations_apply_and_rollback():
    conn = sqlite3.connect(":memory:")
    assert apply(conn) == 2
    assert status(conn)["up_to_date"] is True
    assert rollback_to(conn, 1) == 1
    assert status(conn)["current"] == 1
    assert apply(conn) == 2
    assert status(conn)["current"] == 2
