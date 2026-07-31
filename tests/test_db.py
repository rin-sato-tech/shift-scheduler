from __future__ import annotations

import sqlite3

from src import db


def test_init_db_creates_required_tables(
    tmp_path,
    monkeypatch,
) -> None:
    test_db_path = tmp_path / "test_shift_scheduler.db"
    monkeypatch.setattr(db, "DB_PATH", test_db_path)

    db.init_db()

    with sqlite3.connect(test_db_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()

    table_names = {row[0] for row in rows}

    assert table_names == {
        "employees",
        "day_off_requests",
        "staffing_requirements",
        "schedule_generations",
        "schedules",
    }