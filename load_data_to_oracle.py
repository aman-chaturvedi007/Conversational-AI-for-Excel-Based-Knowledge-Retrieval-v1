import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.dialects import oracle

# Load Oracle credentials from .env.
load_dotenv()

# Source folder containing the original CSV files.
DATA_DIR = Path(__file__).parent / "data"

# Build localhost:1521/FREEPDB1 from .env values.
dsn = (
    f"{os.environ['ORACLE_HOST']}:"
    f"{os.environ.get('ORACLE_PORT', '1521')}/"
    f"{os.environ['ORACLE_SERVICE_NAME']}"
)

# Connect using the data-owner account.
engine = create_engine(
    "oracle+oracledb://@",
    connect_args={
        "user": os.environ["ORACLE_DATA_OWNER_USER"],
        "password": os.environ["ORACLE_DATA_OWNER_PASSWORD"],
        "dsn": dsn,
    },
)

# Load each CSV into an Oracle table with the same base name.
for csv_file in sorted(DATA_DIR.glob("*.csv")):
    table_name = csv_file.stem.upper()
    first_chunk = True

    # TIME_TO_REACH_PEAK_POINT has duration text such as 25:46.
    # Keep it as text instead of allowing Pandas to infer a number.
    read_options = {}

    if table_name == "T_MCH_COKE":
        read_options["dtype"] = {
            "TIME_TO_REACH_PEAK_POINT": "string",
        }

    print(f"Loading {csv_file.name} into {table_name}...")

    # Read large source files in manageable batches.
    for chunk in pd.read_csv(
        csv_file,
        chunksize=5_000,
        **read_options,
    ):
        # Remove accidental exported index columns such as Unnamed: 0.
        chunk = chunk.loc[
            :,
            ~chunk.columns.astype(str).str.match(r"^Unnamed:"),
        ]

        # Convert date/time columns into Oracle-compatible values.
        for column in chunk.columns:
            if column.upper().startswith("DT_"):
                chunk[column] = pd.to_datetime(
                    chunk[column],
                    format="mixed",
                    errors="coerce",
                )

        # Oracle needs a native floating-point type for decimal columns.
        oracle_dtypes = {
            column: oracle.BINARY_DOUBLE()
            for column in chunk.columns
            if pd.api.types.is_float_dtype(chunk[column])
        }

        # Preserve duration text such as 00:00 and 25:46.
        if "TIME_TO_REACH_PEAK_POINT" in chunk.columns:
            oracle_dtypes["TIME_TO_REACH_PEAK_POINT"] = oracle.VARCHAR2(32)

        # Create the table for the first chunk and append later chunks.
        chunk.to_sql(
            name=table_name,
            con=engine,
            if_exists="fail" if first_chunk else "append",
            index=False,
            chunksize=1_000,
            dtype=oracle_dtypes,
        )

        first_chunk = False

    print(f"Finished {table_name}.")

print("All CSV files were loaded into Oracle.")