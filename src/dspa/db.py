import os
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv


def connection_settings(env_file: Path | None = None) -> dict:
    """Load shared server settings without overriding explicitly supplied environment."""
    load_dotenv(env_file or Path(__file__).parents[2] / ".env")
    settings = {
        "host": os.environ["MYSQL_HOST"],
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "connection_timeout": 10,
    }
    if os.environ.get("MYSQL_UNIX_SOCKET"):
        settings["unix_socket"] = os.environ["MYSQL_UNIX_SOCKET"]
    return settings


def get_connection(env_file: Path | None = None) -> mysql.connector.MySQLConnection:
    """Return a connection for administrative reference-data commands."""
    settings = connection_settings(env_file)
    return mysql.connector.connect(**settings, user=os.environ["MYSQL_USER"],
                                   password=os.environ["MYSQL_PASSWORD"],
                                   database=os.environ["MYSQL_DATABASE"])
