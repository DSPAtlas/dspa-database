"""Verify trusted owner propagation and the CLI import lifecycle."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

from click.testing import CliRunner

from dspa.cli import main


class IngestionCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dspa-cli-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.experiment = self.create_experiment("first")
        self.runner = CliRunner()
        self.connection = MagicMock(name="database_connection")
        for name, result in (
            ("bound_connection", None), ("create_import", 31),
            ("get_import", {"id": 31, "user_id": 73, "status": "running"}),
            ("finish_import", "succeeded"), ("allocate_experiment_id", "DPX000123"),
            ("ingest_experiment", "DPX000123"),
        ):
            patcher = patch(f"dspa.cli.{name}", return_value=result)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)
        self.bound_connection.return_value = MagicMock()
        self.bound_connection.return_value.__enter__.return_value = self.connection

    def create_experiment(self, relative_path):
        folder = self.root / relative_path
        folder.mkdir(parents=True)
        (folder / "params.yaml").write_text("experiment: CLI test\n")
        return folder

    def test_invalid_or_missing_ids_are_rejected_before_database_access(self):
        cases = [[], ["--user-id", "0"], ["--user-id", "-1"],
                 ["--user-id", "not-an-integer"], ["--user-id", "1.5"],
                 ["--user-id", "4294967296"],
                 ["--user-id", "73", "--import-id", "0"],
                 ["--user-id", "73", "--import-id", "18446744073709551616"]]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result = self.runner.invoke(main, [str(self.experiment), *arguments])
                self.assertEqual(result.exit_code, 2, result.output)
                self.bound_connection.assert_not_called()
                self.create_import.assert_not_called()
                self.ingest_experiment.assert_not_called()

    def test_new_cli_import_creates_owned_record_and_finishes(self):
        result = self.runner.invoke(main, [str(self.experiment), "--user-id", "73"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.create_import.assert_called_once_with(73, "first", env_file=None)
        self.get_import.assert_called_once_with(73, 31, env_file=None)
        self.bound_connection.assert_called_once_with(73, env_file=None)
        self.ingest_experiment.assert_called_once_with(
            self.experiment, self.connection, user_id=73, import_id=31,
            dpx_id="DPX000123", dry_run=False)
        self.finish_import.assert_called_once_with(73, 31, env_file=None)
        self.bound_connection.return_value.__exit__.assert_called_once()

    def test_supplied_import_is_reused_and_owner_propagates_to_all_folders(self):
        second = self.create_experiment("nested/second")
        self.allocate_experiment_id.side_effect = ["DPX000123", "DPX000124"]
        result = self.runner.invoke(main, [str(self.root), "--user-id", "73", "--import-id", "31"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.create_import.assert_not_called()
        self.get_import.assert_called_once_with(73, 31, env_file=None)
        self.assertEqual(self.ingest_experiment.call_args_list, [
            call(folder, self.connection, user_id=73, import_id=31,
                 dpx_id=dpx_id, dry_run=False)
            for folder, dpx_id in zip(sorted([self.experiment, second]), ["DPX000123", "DPX000124"])
        ])

    def test_uppercase_params_filename_discovers_single_experiment(self):
        (self.experiment / "params.yaml").rename(self.experiment / "PARAMS.YAML")
        result = self.runner.invoke(main, [str(self.experiment), "--user-id", "73"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.ingest_experiment.assert_called_once_with(
            self.experiment, self.connection, user_id=73, import_id=31,
            dpx_id="DPX000123", dry_run=False)

    def test_mixed_case_params_filenames_discover_nested_experiments(self):
        second = self.create_experiment("nested/second")
        (self.experiment / "params.yaml").rename(self.experiment / "PARAMS.YAML")
        (second / "params.yaml").rename(second / "Params.Yaml")
        self.allocate_experiment_id.side_effect = ["DPX000123", "DPX000124"]
        result = self.runner.invoke(main, [str(self.root), "--user-id", "73"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.ingest_experiment.call_args_list, [
            call(folder, self.connection, user_id=73, import_id=31,
                 dpx_id=dpx_id, dry_run=False)
            for folder, dpx_id in zip(sorted([self.experiment, second]), ["DPX000123", "DPX000124"])
        ])

    def test_foreign_owned_import_cannot_start_ingestion(self):
        self.get_import.side_effect = PermissionError("Import is unavailable for this user")
        result = self.runner.invoke(main, [str(self.experiment), "--user-id", "73", "--import-id", "99"])
        self.assertEqual(result.exit_code, 1, result.output)
        self.bound_connection.assert_not_called()
        self.allocate_experiment_id.assert_not_called()
        self.ingest_experiment.assert_not_called()

    def test_finished_import_cannot_be_reused(self):
        self.get_import.return_value["status"] = "succeeded"
        result = self.runner.invoke(main, [str(self.experiment), "--user-id", "73", "--import-id", "31"])
        self.assertEqual(result.exit_code, 1, result.output)
        self.ingest_experiment.assert_not_called()

    def test_dry_run_requires_owner_but_does_not_touch_database(self):
        missing = self.runner.invoke(main, [str(self.experiment), "--dry-run"])
        self.assertEqual(missing.exit_code, 2)
        preview = self.runner.invoke(main, [str(self.experiment), "--user-id", "73", "--dry-run"])
        self.assertEqual(preview.exit_code, 0, preview.output)
        self.assertIn("no data written", preview.output)
        self.bound_connection.assert_not_called()
        self.create_import.assert_not_called()
        self.ingest_experiment.assert_not_called()

    def test_failure_finalizes_without_disclosing_database_exception(self):
        self.ingest_experiment.side_effect = RuntimeError("password=must-not-be-disclosed")
        result = self.runner.invoke(main, [str(self.experiment), "--user-id", "73"])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertNotIn("must-not-be-disclosed", result.output)
        self.finish_import.assert_called_once_with(73, 31, failed=True,
                                                   diagnostic="ingestion failed", env_file=None)
        self.bound_connection.return_value.__exit__.assert_called_once()

    def test_interrupt_finalizes_and_exits_nonzero(self):
        self.ingest_experiment.side_effect = InterruptedError()
        result = self.runner.invoke(main, [str(self.experiment), "--user-id", "73"])
        self.assertEqual(result.exit_code, 1, result.output)
        self.finish_import.assert_called_once_with(73, 31, failed=True,
                                                   diagnostic="cancelled", env_file=None)
        self.bound_connection.return_value.__exit__.assert_called_once()

    def test_empty_input_records_failed_import(self):
        empty = self.root / "empty"
        empty.mkdir()
        result = self.runner.invoke(main, [str(empty), "--user-id", "73"])
        self.assertEqual(result.exit_code, 1, result.output)
        self.ingest_experiment.assert_not_called()
        self.finish_import.assert_called_once_with(73, 31, failed=True,
                                                   diagnostic="empty archive", env_file=None)


if __name__ == "__main__":
    unittest.main()
