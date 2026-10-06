import os

# pyrefly: ignore [missing-import]
import oracledb
from dotenv import load_dotenv

load_dotenv()

with oracledb.connect(
    user=os.environ["ORACLE_DATA_OWNER_USER"],
    password=os.environ["ORACLE_DATA_OWNER_PASSWORD"],
    host=os.environ["ORACLE_HOST"],
    port=int(os.environ["ORACLE_PORT"]),
    service_name=os.environ["ORACLE_SERVICE_NAME"],
) as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT USER, SYSDATE FROM dual")
        print(cursor.fetchone())