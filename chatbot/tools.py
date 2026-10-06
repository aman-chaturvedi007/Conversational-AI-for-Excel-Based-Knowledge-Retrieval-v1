import json
import re

import oracledb
import pandas as pd
import plotly.express as px
from langchain_core.tools import tool
from plotly.utils import PlotlyJSONEncoder

# pyrefly: ignore [missing-import]
from chatbot.data_catalog import get_connection
# pyrefly: ignore [missing-import]
from chatbot.settings import ORACLE_DATA_OWNER_SCHEMA

MAX_QUERY_ROWS = 100
MAX_CHART_ROWS = 5_000
MAX_QUERY_RESPONSE_CHARACTERS = 6_000


def validate_select_query(sql: str) -> str:
    """Allow exactly one read-only SELECT or WITH query."""
    cleaned_sql = sql.strip()

    fenced_query = re.fullmatch(
        r"```(?:sql)?\s*(.*?)\s*```",
        cleaned_sql,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if fenced_query:
        cleaned_sql = fenced_query.group(1).strip()

    cleaned_sql = re.sub(
        r"(?m)^\s*--[^\n]*\n",
        "",
        cleaned_sql,
    ).strip()

    normalized_sql = cleaned_sql.lower()

    if not normalized_sql.startswith(("select", "with")):
        raise ValueError("Only SELECT queries are allowed.")

    if ";" in cleaned_sql:
        raise ValueError("Multiple SQL statements are not allowed.")

    blocked_words = (
        "insert",
        "update",
        "delete",
        "merge",
        "drop",
        "alter",
        "create",
        "grant",
        "revoke",
        "execute",
        "begin",
        "declare",
    )

    if any(
        re.search(rf"\b{word}\b", normalized_sql)
        for word in blocked_words
    ):
        raise ValueError("This SQL operation is not allowed.")

    return cleaned_sql


def query_rows(sql: str, row_limit: int) -> tuple[list[str], list[tuple]]:
    """Run a safe Oracle query with a maximum row count."""
    safe_sql = validate_select_query(sql)

    limited_sql = (
        f"SELECT * FROM ({safe_sql}) query_result "
        "WHERE ROWNUM <= :row_limit"
    )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(limited_sql, row_limit=row_limit)

            columns = [
                column[0]
                for column in cursor.description
            ]
            rows = cursor.fetchall()

    return columns, rows


@tool
def list_tables() -> str:
    """List the Oracle tables approved for chatbot analysis."""
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
            rows = cursor.fetchall()

    return "\n".join(
        f"{ORACLE_DATA_OWNER_SCHEMA}.{row[0]}"
        for row in rows
    )


@tool
def run_data_query(sql: str) -> str:
    """Run one read-only Oracle query and return a compact table preview."""
    try:
        columns, rows = query_rows(sql, MAX_QUERY_ROWS)
    except (ValueError, oracledb.Error) as error:
        return f"Query could not be run: {error}"

    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    response_lines = [header, separator]

    for row in rows:
        line = "| " + " | ".join(
            str(value).replace("|", "\\|")[:300]
            for value in row
        ) + " |"

        if len("\n".join(response_lines + [line])) > MAX_QUERY_RESPONSE_CHARACTERS:
            response_lines.append(
                "\n_Result preview shortened for safety._"
            )
            break

        response_lines.append(line)

    if len(rows) == MAX_QUERY_ROWS:
        response_lines.append(
            f"\n_Showing the first {MAX_QUERY_ROWS} rows only._"
        )

    return "\n".join(response_lines)


@tool
def create_chart(
    sql: str,
    chart_type: str,
    x_column: str,
    y_column: str,
    title: str,
) -> str:
    """Create an interactive Plotly bar, line, pie, box, scatter, or histogram chart."""
    allowed_chart_types = {
        "bar",
        "line",
        "pie",
        "box",
        "scatter",
        "histogram",
    }

    if chart_type not in allowed_chart_types:
        raise ValueError("Unsupported chart type.")

    columns, rows = query_rows(sql, MAX_CHART_ROWS)

    if not rows:
        raise ValueError("The chart query returned no rows.")

    frame = pd.DataFrame(rows, columns=columns)

    available_columns = {
        column.lower(): column
        for column in frame.columns
    }

    if x_column.lower() not in available_columns:
        raise ValueError(f"Unknown x-axis column: {x_column}")

    if y_column.lower() not in available_columns:
        raise ValueError(f"Unknown y-axis column: {y_column}")

    x_column = available_columns[x_column.lower()]
    y_column = available_columns[y_column.lower()]

    chart_frame = frame[[x_column, y_column]].dropna()

    if chart_frame.empty:
        raise ValueError("No complete x/y values are available for this chart.")

    if chart_type == "bar":
        figure = px.bar(
            chart_frame,
            x=x_column,
            y=y_column,
            title=title,
        )
    elif chart_type == "line":
        figure = px.line(
            chart_frame,
            x=x_column,
            y=y_column,
            title=title,
            markers=True,
        )
    elif chart_type == "pie":
        figure = px.pie(
            chart_frame,
            names=x_column,
            values=y_column,
            title=title,
        )
    elif chart_type == "box":
        figure = px.box(
            chart_frame,
            x=x_column,
            y=y_column,
            title=title,
            points="outliers",
        )
    elif chart_type == "scatter":
        figure = px.scatter(
            chart_frame,
            x=x_column,
            y=y_column,
            title=title,
        )
    else:
        figure = px.histogram(
            chart_frame,
            x=x_column,
            title=title,
            nbins=30,
        )

    figure.update_layout(
        template="plotly_white",
        margin={"l": 48, "r": 24, "t": 64, "b": 48},
        hovermode="closest",
    )

    return json.dumps(
        {"chart": figure.to_plotly_json()},
        cls=PlotlyJSONEncoder,
    )


ANALYTICS_TOOLS = [
    list_tables,
    run_data_query,
    create_chart,
]