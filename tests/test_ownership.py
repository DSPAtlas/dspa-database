"""Verify physical connection binding, cleanup, and durable import statuses."""
from contextlib import contextmanager
import os
import unittest
from unittest.mock import MagicMock, call, patch

import mysql.connector
from dspa import ownership


class BoundConnectionTests(unittest.TestCase):
    def setUp(self):
        self.data, self.control = MagicMock(), MagicMock()
        self.data.cursor.return_value.fetchone.return_value = ("server-a", 73, 101)
        self.control.cursor.return_value.fetchone.return_value = ("server-a",)
        self.control.cursor.return_value.with_rows = False
        self.control.cursor.return_value.nextset.return_value = None
        patcher = patch("dspa.ownership._connect", side_effect=[self.data, self.control])
        self.connect = patcher.start()
        self.addCleanup(patcher.stop)

    def test_actual_connection_is_bound_and_refreshed_before_operations(self):
        with ownership.bound_connection(42) as connection:
            cursor = connection.cursor()
            cursor.execute("INSERT INTO imports VALUES (%s)", (42,))
            cursor.executemany("INSERT INTO example VALUES (%s)", [(42,)])
            connection.commit()
        self.assertEqual(self.connect.call_args_list, [
            call("data", None), call("context", None, autocommit=True)])
        binds = [args for args in self.control.cursor.return_value.execute.call_args_list
                 if "bind_context" in args.args[0]]
        self.assertEqual(binds, [call("CALL dspa_security.bind_context(%s,%s,%s,%s)",
                                     (73, 101, 42, 3600))] * 4)
        self.control.cursor.return_value.execute.assert_any_call(
            "CALL dspa_security.clear_context(%s,%s)", (73, 101))
        self.data.rollback.assert_called_once_with()
        self.data.close.assert_called_once_with()
        self.control.close.assert_called_once_with()

    def test_server_mismatch_fails_before_binding(self):
        self.control.cursor.return_value.fetchone.return_value = ("server-b",)
        with self.assertRaises(RuntimeError):
            with ownership.bound_connection(42):
                self.fail("Mismatched connections must never be returned")
        for args in self.control.cursor.return_value.execute.call_args_list:
            self.assertNotIn("bind_context", args.args[0])
        self.data.close.assert_called_once_with()
        self.control.close.assert_called_once_with()

    def test_missing_performance_schema_thread_fails_closed(self):
        self.data.cursor.return_value.fetchone.return_value = ("server-a", 73, None)
        with self.assertRaises(RuntimeError):
            with ownership.bound_connection(42):
                self.fail("Uninstrumented connections must never be returned")
        self.data.close.assert_called_once_with()

    def test_interruption_rolls_back_clears_and_closes(self):
        with self.assertRaises(KeyboardInterrupt):
            with ownership.bound_connection(42):
                raise KeyboardInterrupt()
        self.data.rollback.assert_called_once_with()
        self.control.cursor.return_value.execute.assert_any_call(
            "CALL dspa_security.clear_context(%s,%s)", (73, 101))
        self.data.close.assert_called_once_with()
        self.control.close.assert_called_once_with()

    def test_cleanup_failure_preserves_original_error_and_closes(self):
        with self.assertRaisesRegex(ValueError, "original"):
            with ownership.bound_connection(42):
                self.control.cursor.return_value.execute.side_effect = RuntimeError("control unavailable")
                self.data.rollback.side_effect = RuntimeError("data unavailable")
                raise ValueError("original")
        self.data.close.assert_called_once_with()
        self.control.close.assert_called_once_with()

    def test_invalid_owner_never_connects(self):
        for user_id in (True, None, "42", 0, 4294967296):
            with self.subTest(user_id=user_id), self.assertRaises(ValueError):
                with ownership.bound_connection(user_id):
                    self.fail("Invalid owner")
        self.connect.assert_not_called()


class IdentityAndAllocationTests(unittest.TestCase):
    def test_identity_uses_separate_account_and_same_server(self):
        data, identity = MagicMock(), MagicMock()
        with patch("dspa.ownership._connect", side_effect=[data, identity]) as connect, \
                patch("dspa.ownership._server_uuid", return_value="same"), \
                patch("dspa.ownership._call", return_value=[(42,)]) as procedure:
            self.assertEqual(ownership.resolve_user("https://issuer.example", "subject-a"), 42)
        self.assertEqual(connect.call_args_list, [call("data", None, autocommit=True),
                                                call("identity", None, autocommit=True)])
        procedure.assert_called_once_with(identity.cursor.return_value,
                                          "CALL dspa_security.ensure_user(%s,%s)",
                                          ("https://issuer.example", "subject-a"))
        data.close.assert_called_once_with()
        identity.close.assert_called_once_with()

    def test_disabled_identity_raises_safe_permission_error(self):
        error = mysql.connector.Error("sensitive database details", errno=1644)
        with patch("dspa.ownership._connect", side_effect=[MagicMock(), MagicMock()]), \
                patch("dspa.ownership._server_uuid", return_value="same"), \
                patch("dspa.ownership._call", side_effect=error), \
                self.assertRaisesRegex(PermissionError, "Identity is unavailable or disabled"):
            ownership.resolve_user("https://issuer.example", "subject-a")

    def test_invalid_external_identity_never_connects(self):
        with patch("dspa.ownership._connect") as connect:
            for issuer, subject in (("", "a"), ("https://issuer", " "),
                                    ("urn:dspa:internal", "a"), (None, "a")):
                with self.subTest(issuer=issuer, subject=subject), self.assertRaises(ValueError):
                    ownership.resolve_user(issuer, subject)
            connect.assert_not_called()

    def test_allocator_uses_separate_autocommit_connection(self):
        connection = MagicMock()
        with patch("dspa.ownership._connect", return_value=connection) as connect, \
                patch("dspa.ownership._call", return_value=[(123, "DPX000123")]) as procedure:
            self.assertEqual(ownership.allocate_experiment_id(), "DPX000123")
        connect.assert_called_once_with("data", None, autocommit=True)
        procedure.assert_called_once_with(connection.cursor.return_value,
                                          "CALL dspa_security.allocate_experiment_id()")
        connection.close.assert_called_once_with()

    def test_control_credentials_do_not_inherit_data_schema_or_account(self):
        environment = {"MYSQL_HOST": "mysql", "MYSQL_DATABASE": "dspa_import",
                       "MYSQL_USER": "dspa_importer", "MYSQL_PASSWORD": "data-secret",
                       "DSPA_CONTEXT_DB_USER": "dspa_context_manager", "DSPA_CONTEXT_DB_PASSWORD": "control-secret",
                       "DSPA_IDENTITY_DB_USER": "dspa_user_manager", "DSPA_IDENTITY_DB_PASSWORD": "identity-secret",
                       "MYSQL_UNIX_SOCKET": "/tmp/test.sock"}
        with patch.dict(os.environ, environment, clear=True), patch("dspa.db.load_dotenv"), \
                patch("dspa.ownership.mysql.connector.connect") as connect:
            for role, account in (("identity", "dspa_user_manager"), ("context", "dspa_context_manager")):
                ownership._connect(role, autocommit=True)
                self.assertEqual(connect.call_args.kwargs["user"], account)
                self.assertEqual(connect.call_args.kwargs["unix_socket"], "/tmp/test.sock")
                self.assertNotIn("database", connect.call_args.kwargs)
            ownership._connect("data")
            self.assertEqual(connect.call_args.kwargs["database"], "dspa_import")
            self.assertEqual(connect.call_args.kwargs["user"], "dspa_importer")


class ImportLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value

        @contextmanager
        def bound(user_id, env_file=None):
            self.assertEqual(user_id, 42)
            yield self.connection

        patcher = patch("dspa.ownership.bound_connection", side_effect=bound)
        self.bound = patcher.start()
        self.addCleanup(patcher.stop)

    def test_create_import_binds_owner_and_commits(self):
        self.cursor.lastrowid = 31
        self.assertEqual(ownership.create_import(42, "upload.zip"), 31)
        self.cursor.execute.assert_called_once_with(
            "INSERT INTO imports (user_id, original_filename) VALUES (%s,%s)", (42, "upload.zip"))
        self.connection.commit.assert_called_once_with()

    def test_status_uses_committed_rows_and_never_stores_raw_errors(self):
        for failed, committed, expected in ((False, 3, "succeeded"), (True, 3, "partial"), (True, 0, "failed")):
            with self.subTest(failed=failed, committed=committed):
                self.connection.reset_mock()
                self.cursor.reset_mock()
                record = {"status": "running", "committed_experiments": committed}
                with patch("dspa.ownership._import_record", return_value=record) as read:
                    status = ownership.finish_import(42, 31, failed=failed,
                                                     diagnostic="password=must-not-persist")
                self.assertEqual(status, expected)
                read.assert_called_once_with(self.connection, 42, 31, for_update=True)
                values = self.cursor.execute.call_args.args[1]
                self.assertEqual(values[0], expected)
                self.assertNotIn("must-not-persist", str(values))
                self.connection.commit.assert_called_once_with()

    def test_repeated_finish_preserves_terminal_status(self):
        for status in ("succeeded", "partial", "failed"):
            with self.subTest(status=status):
                self.connection.reset_mock()
                self.cursor.reset_mock()
                with patch("dspa.ownership._import_record", return_value={"status": status}):
                    self.assertEqual(ownership.finish_import(42, 31, failed=True), status)
                    self.assertEqual(ownership.finish_import(42, 31, failed=False), status)
                self.cursor.execute.assert_not_called()
                self.connection.commit.assert_not_called()

    def test_foreign_import_is_rejected_before_counting(self):
        self.cursor.fetchone.return_value = None
        with self.assertRaises(PermissionError):
            ownership.get_import(42, 99)
        self.cursor.execute.assert_called_once()
        self.assertEqual(self.cursor.execute.call_args.args[1], (99, 42))


if __name__ == "__main__":
    unittest.main()
