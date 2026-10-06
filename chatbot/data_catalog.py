import re
import time

import oracledb

# pyrefly: ignore [missing-import]
from chatbot.settings import (
    ORACLE_DATA_OWNER_SCHEMA,
    ORACLE_DSN,
    ORACLE_PASSWORD,
    ORACLE_USER,
)

CATALOGUE_CACHE_SECONDS = 300

_cached_catalogue: list[dict] = []
_cached_at = 0.0


def get_connection() -> oracledb.Connection:
    """Create one connection using the read-only chatbot account."""
    return oracledb.connect(
        user=ORACLE_USER,
        password=ORACLE_PASSWORD,
        dsn=ORACLE_DSN,
    )


def quoted_identifier(identifier: str) -> str:
    """Quote a validated Oracle identifier."""
    if not re.fullmatch(r"[A-Z][A-Z0-9_$#]*", identifier):
        raise ValueError(f"Unsafe Oracle identifier: {identifier}")

    return f'"{identifier}"'


def refresh_database() -> list[dict]:
    """Read available table metadata from Oracle."""
    global _cached_at, _cached_catalogue

    if time.monotonic() - _cached_at < CATALOGUE_CACHE_SECONDS:
        return _cached_catalogue

    catalogue: list[dict] = []
    schema = quoted_identifier(ORACLE_DATA_OWNER_SCHEMA)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM all_tables
                WHERE owner = :owner
                ORDER BY table_name
                """,
                owner=ORACLE_DATA_OWNER_SCHEMA,
            )
            table_names = [row[0] for row in cursor.fetchall()]

            for table_name in table_names:
                safe_table = quoted_identifier(table_name)

                cursor.execute(
                    """
                    SELECT column_name, data_type
                    FROM all_tab_columns
                    WHERE owner = :owner
                      AND table_name = :table_name
                    ORDER BY column_id
                    """,
                    owner=ORACLE_DATA_OWNER_SCHEMA,
                    table_name=table_name,
                )

                columns = [
                    f"{column_name} ({data_type})"
                    for column_name, data_type in cursor.fetchall()
                ]

                cursor.execute(
                    f"SELECT COUNT(*) FROM {schema}.{safe_table}"
                )
                row_count = cursor.fetchone()[0]

                catalogue.append(
                    {
                        "table": table_name,
                        "columns": columns,
                        "row_count": row_count,
                    }
                )

    _cached_catalogue = catalogue
    _cached_at = time.monotonic()

    return catalogue