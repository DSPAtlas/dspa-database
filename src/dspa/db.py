import os
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv


def get_connection(env_file: Path | None = None) -> mysql.connector.MySQLConnection:
    """Return an open MySQL connection, loading credentials from .env."""
    load_dotenv(env_file or Path(__file__).parents[2] / ".env")
    return mysql.connector.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
    )
