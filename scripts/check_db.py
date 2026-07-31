from __future__ import annotations

from src.db import DB_PATH, get_connection


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database file does not exist: {DB_PATH}"
        )

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