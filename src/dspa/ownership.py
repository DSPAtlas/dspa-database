"""Trusted importer identity, connection binding, and import lifecycle.

Only authenticated server code may choose an issuer/subject or numeric owner.
Input archives never provide identity. SQL views enforce the binding on writes.
"""
from __future__ import annotations

import os
import re
from contextlib import contextmanager, suppress
from pathlib import Path

import mysql.connector

from dspa.db import connection_settings

CONTEXT_TTL_SECONDS = 28_800
_TERMINAL_STATUSES = {"succeeded", "failed", "partial"}
_SAFE_DIAGNOSTICS = {
    "timeout": "Import exceeded its time limit.",
    "cancelled": "Import was cancelled.",
    "ingestion failed": "Import failed while processing experiment data.",
    "empty archive": "No experiment folders were found.",
    "spawn failed": "Import worker could not be started.",
}


def validate_user_id(user_id: int) -> None:
    if isinstance(user_id, bool) or not isinstance(user_id, int) or not 1 <= user_id <= 4294967295:
        raise ValueError("user_id must be an integer between 1 and 4294967295")


def validate_import_id(import_id: int) -> None:
    if isinstance(import_id, bool) or not isinstance(import_id, int) or not 1 <= import_id <= 18446744073709551615:
        raise ValueError("import_id must be a positive unsigned 64-bit integer")


def _connect(role: str, env_file=None, *, autocommit=False):
    settings = connection_settings(env_file)
    if os.environ.get("MYSQL_DATABASE") != "dspa_import":
        raise ValueError("Importer MYSQL_DATABASE must be dspa_import")
    prefix = {"data": "MYSQL", "identity": "DSPA_IDENTITY_DB", "context": "DSPA_CONTEXT_DB"}[role]
    settings.update(user=os.environ[f"{prefix}_USER"],
                    password=os.environ[f"{prefix}_PASSWORD"], autocommit=autocommit)
    if role == "data":
        settings["database"] = "dspa_import"
    return mysql.connector.connect(**settings)


def _call(cursor, statement, parameters=()):
    """Consume every procedure result, including the trailing empty result set."""
    cursor.execute(statement, parameters)
    rows = cursor.fetchall() if cursor.with_rows else []
    while cursor.nextset():
        if cursor.with_rows:
            cursor.fetchall()
    return rows


def _server_uuid(connection):
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT @@server_uuid")
        return cursor.fetchone()[0]
    finally:
        cursor.close()


class _BoundCursor:
    def __init__(self, connection, cursor):
        self._connection = connection
        self._cursor = cursor

    def execute(self, *args, **kwargs):
        self._connection.refresh()
        return self._cursor.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        self._connection.refresh()
        return self._cursor.executemany(*args, **kwargs)

    def callproc(self, *args, **kwargs):
        self._connection.refresh()
        return self._cursor.callproc(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class _BoundConnection:
    def __init__(self, data, control, user_id, connection_id, thread_id):
        self._data = data
        self._control = control
        self.user_id = user_id
        self._target = (connection_id, thread_id)

    def refresh(self):
        cursor = self._control.cursor()
        try:
            _call(cursor, "CALL dspa_security.bind_context(%s,%s,%s,%s)",
                  (*self._target, self.user_id, CONTEXT_TTL_SECONDS))
        finally:
            cursor.close()

    def clear(self):
        cursor = self._control.cursor()
        try:
            _call(cursor, "CALL dspa_security.clear_context(%s,%s)", self._target)
        finally:
            cursor.close()

    def cursor(self, *args, **kwargs):
        return _BoundCursor(self, self._data.cursor(*args, **kwargs))

    def commit(self):
        self.refresh()
        self._data.commit()

    def rollback(self):
        self._data.rollback()


@contextmanager
def bound_connection(user_id: int, env_file: Path | None = None):
    """Bind one fresh data connection, refresh before statements, always dispose it.

    Control and data sessions must reach the same physical MySQL server. There is
    no reconnect or pool reuse. SIGKILL closes the socket; any surviving context
    lease expires within eight hours and cannot authorize a replacement thread.
    """
    validate_user_id(user_id)
    data = control = bound = None
    try:
        data = _connect("data", env_file)
        control = _connect("context", env_file, autocommit=True)
        cursor = data.cursor()
        try:
            cursor.execute("SELECT @@server_uuid, CONNECTION_ID(), PS_CURRENT_THREAD_ID()")
            server_uuid, connection_id, thread_id = cursor.fetchone()
        finally:
            cursor.close()
        if not thread_id or not server_uuid or server_uuid != _server_uuid(control):
            raise RuntimeError("Data and context connections must use the same instrumented MySQL server")
        bound = _BoundConnection(data, control, user_id, connection_id, thread_id)
        bound.refresh()
        yield bound
    finally:
        if data is not None:
            with suppress(Exception):
                data.rollback()
        if bound is not None:
            with suppress(Exception):
                bound.clear()
        if data is not None:
            with suppress(Exception):
                data.close()
        if control is not None:
            with suppress(Exception):
                control.close()


def resolve_user(issuer: str, subject: str, env_file: Path | None = None) -> int:
    """Resolve a gateway-verified OIDC identity; never call with archive metadata."""
    if (not isinstance(issuer, str) or not issuer.strip() or len(issuer) > 512
            or issuer == "urn:dspa:internal" or not isinstance(subject, str)
            or not subject.strip() or len(subject) > 255):
        raise ValueError("A verified external issuer and subject are required")
    data = identity = None
    try:
        data = _connect("data", env_file, autocommit=True)
        identity = _connect("identity", env_file, autocommit=True)
        if _server_uuid(data) != _server_uuid(identity):
            raise RuntimeError("Data and identity connections must use the same MySQL server")
        cursor = identity.cursor()
        try:
            rows = _call(cursor, "CALL dspa_security.ensure_user(%s,%s)", (issuer, subject))
            return int(rows[0][0])
        except mysql.connector.Error as error:
            if error.errno == 1644:
                raise PermissionError("Identity is unavailable or disabled") from None
            raise
        finally:
            cursor.close()
    finally:
        for connection in (identity, data):
            if connection is not None:
                with suppress(Exception):
                    connection.close()


def allocate_experiment_id(env_file: Path | None = None) -> str:
    """Reserve a global ID on a separate autocommit session; gaps are intentional."""
    connection = _connect("data", env_file, autocommit=True)
    try:
        cursor = connection.cursor()
        try:
            rows = _call(cursor, "CALL dspa_security.allocate_experiment_id()")
            experiment_id = rows[0][1]
            if not isinstance(experiment_id, str) or not re.fullmatch(r"DPX[0-9]{6,8}", experiment_id):
                raise RuntimeError("Invalid allocated experiment ID")
            return experiment_id
        finally:
            cursor.close()
    finally:
        connection.close()


def create_import(user_id: int, filename: str, env_file: Path | None = None) -> int:
    if not isinstance(filename, str) or not filename or len(filename) > 255:
        raise ValueError("Import filename must contain between 1 and 255 characters")
    with bound_connection(user_id, env_file) as connection:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO imports (user_id, original_filename) VALUES (%s,%s)",
                           (user_id, filename))
            import_id = cursor.lastrowid
        connection.commit()
        return int(import_id)


def _import_record(connection, user_id, import_id, *, for_update=False):
    with connection.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT id,user_id,original_filename,status,started_at,finished_at,diagnostic_summary "
                       "FROM imports WHERE id=%s AND user_id=%s" + (" FOR UPDATE" if for_update else ""),
                       (import_id, user_id))
        record = cursor.fetchone()
        if record is None:
            raise PermissionError("Import is unavailable for this user")
        cursor.execute("SELECT COUNT(*) AS committed_experiments FROM dynaprot_experiment "
                       "WHERE user_id=%s AND import_id=%s", (user_id, import_id))
        record["committed_experiments"] = int(cursor.fetchone()["committed_experiments"])
        return record


def get_import(user_id: int, import_id: int, env_file: Path | None = None) -> dict:
    validate_import_id(import_id)
    with bound_connection(user_id, env_file) as connection:
        return _import_record(connection, user_id, import_id)


def finish_import(user_id: int, import_id: int, failed: bool = False,
                  diagnostic: str = "", env_file: Path | None = None) -> str:
    """Finish a running import using committed rows; preserve any terminal result."""
    validate_import_id(import_id)
    with bound_connection(user_id, env_file) as connection:
        record = _import_record(connection, user_id, import_id, for_update=True)
        if record["status"] in _TERMINAL_STATUSES:
            return record["status"]
        status = "succeeded" if not failed else ("partial" if record["committed_experiments"] else "failed")
        summary = (_SAFE_DIAGNOSTICS.get(diagnostic, "Import failed.") if failed else None)
        with connection.cursor() as cursor:
            cursor.execute("UPDATE imports SET status=%s,finished_at=CURRENT_TIMESTAMP(6),"
                           "diagnostic_summary=%s WHERE id=%s AND user_id=%s AND status='running'",
                           (status, summary, import_id, user_id))
        connection.commit()
        return status
