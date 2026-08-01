from __future__ import annotations

import pytest

from src import db


@pytest.fixture
def initialized_test_db(
    tmp_path,
    monkeypatch,
):
    test_db_path = tmp_path / "test_shift_scheduler.db"
    monkeypatch.setattr(db, "DB_PATH", test_db_path)

    db.init_db()

    return test_db_path