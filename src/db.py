from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = (
    PROJECT_ROOT
    / "data"
    / "shift_scheduler.db"
)


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS employees (
                employee_id TEXT PRIMARY KEY,
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                is_manager INTEGER NOT NULL DEFAULT 0
                    CHECK (is_manager IN (0, 1)),
                contract_days INTEGER NOT NULL
                    CHECK (contract_days BETWEEN 0 AND 31),
                can_work_early INTEGER NOT NULL DEFAULT 1
                    CHECK (can_work_early IN (0, 1)),
                can_work_late INTEGER NOT NULL DEFAULT 1
                    CHECK (can_work_late IN (0, 1)),
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK (can_work_early = 1 OR can_work_late = 1)
            );

            CREATE TABLE IF NOT EXISTS day_off_requests (
                day_off_request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT NOT NULL,
                target_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (employee_id, target_date),
                FOREIGN KEY (employee_id)
                    REFERENCES employees(employee_id)
                    ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS staffing_requirements (
                staffing_requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_date TEXT NOT NULL,
                shift_type TEXT NOT NULL
                    CHECK (shift_type IN ('early', 'late')),
                required_count INTEGER NOT NULL
                    CHECK (required_count >= 0),
                required_manager_count INTEGER NOT NULL
                    CHECK (required_manager_count >= 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (target_date, shift_type),
                CHECK (required_manager_count <= required_count)
            );

            CREATE TABLE IF NOT EXISTS schedule_generations (
                generation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_month TEXT NOT NULL,
                solver_status TEXT NOT NULL
                    CHECK (
                        solver_status IN (
                            'OPTIMAL',
                            'FEASIBLE',
                            'INFEASIBLE',
                            'MODEL_INVALID',
                            'UNKNOWN'
                        )
                    ),
                objective_value INTEGER,
                max_deviation INTEGER,
                total_deviation INTEGER,
                generated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS schedules (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                generation_id INTEGER,
                target_date TEXT NOT NULL,
                shift_type TEXT NOT NULL
                    CHECK (shift_type IN ('early', 'late')),
                employee_id TEXT NOT NULL,
                is_manual INTEGER NOT NULL DEFAULT 0
                    CHECK (is_manual IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (target_date, employee_id),
                FOREIGN KEY (generation_id)
                    REFERENCES schedule_generations(generation_id)
                    ON DELETE SET NULL,
                FOREIGN KEY (employee_id)
                    REFERENCES employees(employee_id)
                    ON DELETE RESTRICT
            );
            """
        )


if __name__ == "__main__":
    init_db()
    print(f"Database initialized: {DB_PATH}")