from __future__ import annotations

from src.db import DB_PATH, get_connection


def check_foreign_keys() -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

    return [
        (
            f"table={row[0]}, "
            f"rowid={row[1]}, "
            f"parent={row[2]}"
        )
        for row in rows
    ]


def check_duplicate_daily_assignments() -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                target_date,
                employee_id,
                COUNT(*) AS assignment_count
            FROM schedules
            GROUP BY
                target_date,
                employee_id
            HAVING COUNT(*) > 1
            """
        ).fetchall()

    return [
        (
            f"{row['target_date']} "
            f"{row['employee_id']} "
            f"{row['assignment_count']}件"
        )
        for row in rows
    ]


def check_invalid_shift_types() -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                target_date,
                employee_id,
                shift_type
            FROM schedules
            WHERE shift_type NOT IN (
                'early',
                'late'
            )
            """
        ).fetchall()

    return [
        (
            f"{row['target_date']} "
            f"{row['employee_id']} "
            f"{row['shift_type']}"
        )
        for row in rows
    ]


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database file does not exist: {DB_PATH}"
        )

    checks = {
        "外部キー違反": (
            check_foreign_keys()
        ),
        "同日重複配置": (
            check_duplicate_daily_assignments()
        ),
        "不正シフト種別": (
            check_invalid_shift_types()
        ),
    }
    has_errors = False

    for label, errors in checks.items():
        if errors:
            has_errors = True
            print(f"[NG] {label}")

            for error in errors:
                print(f"  - {error}")
        else:
            print(f"[OK] {label}")

    if has_errors:
        raise SystemExit(1)

    with get_connection() as connection:
        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        print(f"Database: {DB_PATH}")

        for table in tables:
            table_name = table["name"]
            print(f"\n[{table_name}]")

            columns = connection.execute(
                f"PRAGMA table_info({table_name})"
            ).fetchall()

            for column in columns:
                nullable = "NOT NULL" if column["notnull"] else "NULL"
                print(
                    f"- {column['name']}: "
                    f"{column['type']} {nullable}"
                )


if __name__ == "__main__":
    main()
