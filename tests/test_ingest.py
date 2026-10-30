"""Ownership regression tests using actual archive parsing and captured SQL."""
from __future__ import annotations

import re
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import MagicMock

import yaml

from dspa.ingest import ingest_experiment


class IngestOwnershipTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.folder = Path(temporary_directory.name)

    def write_experiment(self, publication=None, doi=None):
        params = {
            "taxonomy_id": 9606,
            "dpx_comparison": ["1", "2"],
            "comparison": ["treated/control", "second"],
            "publication": publication,
            "doi": doi,
            "user_id": 999,
            "owner_id": 998,
            "is_hidden": False,
        }
        (self.folder / "params.yaml").write_text(yaml.safe_dump(params))
        for comparison_id, name in zip(params["dpx_comparison"], params["comparison"]):
            suffix = f"{comparison_id}_{name.replace('/', '_')}.tsv"
            (self.folder / f"differential_abundance_{suffix}").write_text(
                "pg_protein_accessions\teg_modified_peptide\tstart\tend\tdiff\tadj_pval\tpval\tuser_id\n"
                "P12345\tPEPTIDE\t1\t7\t1.5\t0.01\t0.005\t997\n"
                "P67890\tANOTHER\t8\t14\t-1.0\t0.02\t0.01\t996\n"
            )
            (self.folder / f"go_term_{suffix}").write_text(
                "term\tgo_id\tpval\tadj_pval\tn_detected_proteins\t"
                "n_detected_proteins_in_process\tn_significant_proteins\t"
                "n_significant_proteins_in_process\tn_proteins_expected\t"
                "enrichment_type\tgo_type\tuser_id\n"
                "example process\tGO:0000001\t0.01\t0.02\t2\t1\t2\t1\t1\t"
                "overrepresented\tBP\t995\n"
            )

    def connection(self):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = (None,)
        return connection

    def inserted_rows(self, connection):
        """Decode SQL bindings so a wrong column or placeholder fails the test."""
        rows = defaultdict(list)
        for call in connection.cursor.return_value.method_calls:
            method, arguments, _ = call
            if method not in {"execute", "executemany"}:
                continue
            statement = arguments[0]
            if statement.lstrip().startswith("SELECT"):
                continue
            match = re.fullmatch(
                r"\s*INSERT INTO (\w+)\s*\((.*?)\)\s*VALUES\s*\((.*?)\)\s*",
                statement,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(match, statement)
            table, columns, placeholders = match.groups()
            columns = [column.strip().strip("`") for column in columns.split(",")]
            placeholders = [placeholder.strip() for placeholder in placeholders.split(",")]
            self.assertEqual(len(columns), len(placeholders))
            parameters = [arguments[1]] if method == "execute" else arguments[1]
            for parameter in parameters:
                if isinstance(parameter, dict):
                    keys = []
                    for placeholder in placeholders:
                        key = re.fullmatch(r"%\((\w+)\)s", placeholder)
                        self.assertIsNotNone(key, placeholder)
                        keys.append(key.group(1))
                    values = [parameter[key] for key in keys]
                else:
                    self.assertEqual(placeholders, ["%s"] * len(columns))
                    self.assertEqual(len(parameter), len(columns))
                    values = parameter
                rows[table].append(dict(zip(columns, values)))
        return dict(rows)

    def test_every_private_row_uses_supplied_owner_despite_archive_metadata(self):
        self.write_experiment()
        expected_counts = {
            "dynaprot_experiment": 1,
            "dynaprot_experiment_comparison": 2,
            "differential_abundance": 4,
            "go_analysis": 2,
            "protein_scores": 4,
        }
        for owner in (1, 73, 4294967295):
            with self.subTest(user_id=owner, import_id=41, dpx_id="DPX000001"):
                connection = self.connection()
                experiment_id = ingest_experiment(self.folder, connection, user_id=owner, import_id=41, dpx_id="DPX000001")
                rows = self.inserted_rows(connection)
                self.assertEqual(experiment_id, "DPX000001")
                self.assertEqual({table: len(data) for table, data in rows.items()}, expected_counts)
                for table, data in rows.items():
                    for row in data:
                        self.assertEqual(row["user_id"], owner, table)
                self.assertEqual(rows["dynaprot_experiment"][0]["import_id"], 41)
                connection.commit.assert_called_once_with()
                connection.cursor.return_value.close.assert_called_once_with()

    def test_visibility_still_follows_publication_and_doi(self):
        cases = (
            (None, None, True),
            (" Unpublished ", None, True),
            (" NA ", "", True),
            ("A published paper", None, False),
            (None, "10.1234/example", False),
            ("unpublished", "10.1234/example", False),
        )
        for publication, doi, expected_hidden in cases:
            with self.subTest(publication=publication, doi=doi):
                self.write_experiment(publication=publication, doi=doi)
                connection = self.connection()
                ingest_experiment(self.folder, connection, user_id=73, import_id=41, dpx_id="DPX000001")
                rows = self.inserted_rows(connection)
                for table in ("dynaprot_experiment", "dynaprot_experiment_comparison"):
                    for row in rows[table]:
                        self.assertIs(row["is_hidden"], expected_hidden)

    def test_organism_name_is_preserved_on_owned_experiment(self):
        for name in ("  Escherichia coli  ", "Saccharomyces cerevisiae", "Organism ü", "x" * 255):
            with self.subTest(name=name):
                self.write_experiment()
                params_path = self.folder / "params.yaml"
                params = yaml.safe_load(params_path.read_text())
                params["organism"] = name
                params_path.write_text(yaml.safe_dump(params))
                connection = self.connection()
                ingest_experiment(self.folder, connection, user_id=73,
                                  import_id=41, dpx_id="DPX000001")
                rows = self.inserted_rows(connection)
                experiment = rows["dynaprot_experiment"][0]
                self.assertEqual(experiment["organism_name"], name.strip())
                self.assertEqual(experiment["taxonomy_id"], 9606)
                self.assertEqual(experiment["user_id"], 73)
                self.assertNotIn("organism", rows)
                connection.commit.assert_called_once_with()

    def test_missing_organism_name_is_stored_as_null(self):
        for value in (None, "", "  ", " NA ", "nan"):
            with self.subTest(value=value):
                self.write_experiment()
                params_path = self.folder / "params.yaml"
                params = yaml.safe_load(params_path.read_text())
                if value is not None:
                    params["organism"] = value
                params_path.write_text(yaml.safe_dump(params))
                connection = self.connection()
                ingest_experiment(self.folder, connection, user_id=73,
                                  import_id=41, dpx_id="DPX000001")
                self.assertIsNone(self.inserted_rows(connection)["dynaprot_experiment"][0]["organism_name"])
                connection.commit.assert_called_once_with()

    def test_invalid_organism_name_rejects_experiment_without_commit(self):
        for value in (9606, True, [], {"name": "Homo sapiens"}, "x" * 256):
            for dry_run in (False, True):
                with self.subTest(value=value, dry_run=dry_run):
                    self.write_experiment()
                    params_path = self.folder / "params.yaml"
                    params = yaml.safe_load(params_path.read_text())
                    params["organism"] = value
                    params_path.write_text(yaml.safe_dump(params))
                    connection = self.connection()
                    with self.assertRaisesRegex(ValueError, "organism"):
                        ingest_experiment(self.folder, connection, dry_run=dry_run,
                                          user_id=73, import_id=41, dpx_id="DPX000001")
                    self.assertEqual(self.inserted_rows(connection), {})
                    connection.commit.assert_not_called()
                    connection.rollback.assert_called_once_with()
                    connection.cursor.return_value.close.assert_called_once_with()

    def test_comparison_files_ignore_case_and_preserve_metadata(self):
        self.write_experiment()
        params_path = self.folder / "params.yaml"
        params = yaml.safe_load(params_path.read_text())
        original_names = params["comparison"]
        params["comparison"] = ["cAMP_0.1mM_vs_CTR_LiP", "IPTG 100 uM_vs_H20 - control"]
        params_path.write_text(yaml.safe_dump(params))
        for comparison_id, old_name, new_name, change_case in zip(
            params["dpx_comparison"], original_names, params["comparison"], (str.lower, str.upper)
        ):
            safe_name = new_name.replace("/", "_")
            for prefix in ("differential_abundance", "go_term"):
                old_path = self.folder / f"{prefix}_{comparison_id}_{old_name.replace('/', '_')}.tsv"
                old_path.rename(self.folder / change_case(f"{prefix}_{comparison_id}_{safe_name}.tsv"))

        connection = self.connection()
        ingest_experiment(self.folder, connection, user_id=73, import_id=41, dpx_id="DPX000001")
        rows = self.inserted_rows(connection)
        self.assertEqual({table: len(data) for table, data in rows.items()}, {
            "dynaprot_experiment": 1,
            "dynaprot_experiment_comparison": 2,
            "differential_abundance": 4,
            "go_analysis": 2,
            "protein_scores": 4,
        })
        self.assertEqual([row["dose"] for row in rows["dynaprot_experiment_comparison"]],
                         params["comparison"])
        self.assertEqual({row["pg_protein_accessions"] for row in rows["differential_abundance"]},
                         {"P12345", "P67890"})
        connection.commit.assert_called_once_with()

    def test_uppercase_metadata_and_qc_filenames_are_imported(self):
        self.write_experiment()
        (self.folder / "params.yaml").rename(self.folder / "PARAMS.YAML")
        pdf = b"%PDF-1.7\nCase-sensitive fixture content\n%%EOF"
        (self.folder / "QC_PLOTS.PDF").write_bytes(pdf)
        connection = self.connection()
        ingest_experiment(self.folder, connection, user_id=73, import_id=41, dpx_id="DPX000001")
        rows = self.inserted_rows(connection)
        self.assertEqual(rows["dynaprot_experiment"][0]["qc_pdf_file"], pdf)
        self.assertEqual(len(rows["differential_abundance"]), 4)
        connection.commit.assert_called_once_with()

    def test_ambiguous_result_filename_case_rolls_back(self):
        self.write_experiment()
        for prefix in ("differential_abundance", "go_term"):
            with self.subTest(prefix=prefix):
                original = self.folder / f"{prefix}_1_treated_control.tsv"
                duplicate = self.folder / original.name.upper()
                duplicate.write_bytes(original.read_bytes())
                if original.samefile(duplicate):
                    self.skipTest("Filesystem cannot store filenames differing only by case")
                try:
                    connection = self.connection()
                    with self.assertRaisesRegex(ValueError, "Ambiguous"):
                        ingest_experiment(self.folder, connection, user_id=73,
                                          import_id=41, dpx_id="DPX000001")
                    connection.commit.assert_not_called()
                    connection.rollback.assert_called_once_with()
                    connection.cursor.return_value.close.assert_called_once_with()
                finally:
                    duplicate.unlink()

    def test_ambiguous_params_filename_rejected_before_database_access(self):
        self.write_experiment()
        original = self.folder / "params.yaml"
        duplicate = self.folder / "PARAMS.YAML"
        duplicate.write_bytes(original.read_bytes())
        if original.samefile(duplicate):
            self.skipTest("Filesystem cannot store filenames differing only by case")
        connection = self.connection()
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            ingest_experiment(self.folder, connection, user_id=73, import_id=41, dpx_id="DPX000001")
        connection.cursor.assert_not_called()
        connection.commit.assert_not_called()

    def test_missing_optional_go_files_still_import_abundance_and_scores(self):
        self.write_experiment()
        for path in self.folder.glob("go_term_*.tsv"):
            path.unlink()
        connection = self.connection()
        ingest_experiment(self.folder, connection, user_id=73, import_id=41, dpx_id="DPX000001")
        rows = self.inserted_rows(connection)
        self.assertNotIn("go_analysis", rows)
        self.assertEqual(len(rows["differential_abundance"]), 4)
        self.assertEqual(len(rows["protein_scores"]), 4)
        connection.commit.assert_called_once_with()

    def test_invalid_user_id_fails_before_file_or_database_access(self):
        invalid_ids = (None, True, False, 0, -1, 4294967296, "73", 73.0, [], {})
        for user_id in invalid_ids:
            for dry_run in (False, True):
                with self.subTest(user_id=user_id, dry_run=dry_run):
                    folder = MagicMock(spec=Path)
                    connection = MagicMock()
                    with self.assertRaisesRegex(ValueError, "user_id"):
                        ingest_experiment(folder, connection, dry_run=dry_run, user_id=user_id, import_id=41, dpx_id="DPX000001")
                    self.assertEqual(folder.mock_calls, [])
                    self.assertEqual(connection.mock_calls, [])

    def test_user_id_is_required_and_keyword_only(self):
        folder = MagicMock(spec=Path)
        connection = MagicMock()
        with self.assertRaises(TypeError):
            ingest_experiment(folder, connection, import_id=41, dpx_id="DPX000001")
        with self.assertRaises(TypeError):
            ingest_experiment(folder, connection, False, 73)
        self.assertEqual(folder.mock_calls, [])
        self.assertEqual(connection.mock_calls, [])

    def test_invalid_import_and_allocated_ids_fail_before_io(self):
        for import_id, dpx_id in ((0, "DPX000001"), (True, "DPX000001"),
                                   (18446744073709551616, "DPX000001"),
                                   (41, "forged"), (41, None)):
            with self.subTest(import_id=import_id, dpx_id=dpx_id):
                folder = MagicMock(spec=Path)
                connection = MagicMock()
                with self.assertRaises(ValueError):
                    ingest_experiment(folder, connection, user_id=73,
                                      import_id=import_id, dpx_id=dpx_id)
                self.assertEqual(folder.mock_calls, [])
                self.assertEqual(connection.mock_calls, [])

    def test_database_failure_and_interrupt_roll_back_the_experiment(self):
        self.write_experiment()
        for failure in (RuntimeError("database failed"), KeyboardInterrupt()):
            with self.subTest(error=type(failure).__name__):
                connection = self.connection()
                connection.cursor.return_value.executemany.side_effect = failure
                with self.assertRaises(type(failure)):
                    ingest_experiment(self.folder, connection, user_id=73,
                                      import_id=41, dpx_id="DPX000001")
                connection.rollback.assert_called_once_with()
                connection.commit.assert_not_called()
                connection.cursor.return_value.close.assert_called_once_with()

    def test_supplied_id_is_used_without_reading_maximum(self):
        self.write_experiment()
        connection = self.connection()
        result = ingest_experiment(self.folder, connection, user_id=73,
                                   import_id=41, dpx_id="DPX1000001")
        self.assertEqual(result, "DPX1000001")
        rows = self.inserted_rows(connection)
        self.assertEqual(rows["dynaprot_experiment"][0]["dynaprot_experiment"], result)
        self.assertEqual({row["dynaprot_experiment"] for row in rows["dynaprot_experiment_comparison"]},
                         {result})
        for call in connection.cursor.return_value.execute.call_args_list:
            self.assertNotIn("SELECT", call.args[0].upper())

    def test_valid_dry_run_does_not_insert_or_commit(self):
        self.write_experiment()
        connection = self.connection()
        ingest_experiment(self.folder, connection, dry_run=True, user_id=73, import_id=41, dpx_id="DPX000001")
        self.assertEqual(self.inserted_rows(connection), {})
        connection.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
