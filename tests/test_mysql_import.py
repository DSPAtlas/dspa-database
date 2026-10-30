"""Real importer CLI regression using a disposable Unix-socket MySQL server.

From dspa-database run:
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p test_mysql_import.py -v

Requires local mysql/mysqld binaries, project dependencies, and the sibling
DSPA MCP SQL fixture. No Docker, network listener, or existing database is used.
"""

import importlib.util
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


DATABASE_ROOT = Path(__file__).resolve().parents[1]
MCP_ROOT = DATABASE_ROOT.parent / 'dspa-mcp'
HARNESS = MCP_ROOT / 'tests/test_multiuser_sql.py'
SQL_FILES = [MCP_ROOT / name for name in (
    'schema.sql', 'setup_mcp_account_db.sql', 'setup_multiuser.sql', 'setup_organism_names.sql',
)]


def dependencies_available():
    try:
        return all(importlib.util.find_spec(name) is not None for name in (
            'click', 'mysql.connector', 'pandas', 'yaml', 'dotenv', 'requests',
        ))
    except ModuleNotFoundError:
        return False


@unittest.skipUnless(HARNESS.is_file() and all(path.is_file() for path in SQL_FILES),
                     'Sibling dspa-mcp SQL files and disposable MySQL harness are required')
@unittest.skipUnless(shutil.which('mysqld') and shutil.which('mysql'), 'Local MySQL server/client binaries are required')
@unittest.skipUnless(dependencies_available(), 'Install dspa-database project dependencies to run MySQL integration')
class MysqlImportTests(unittest.TestCase):
    @staticmethod
    def fixture(root, name, forged_owner, *, bad=False):
        folder = root / name
        folder.mkdir()
        (folder / 'params.yaml').write_text(
            f'taxonomy_id: {"invalid" if bad else "9606"}\ncondition: Test\npublication: Test publication\n'
            'dpx_comparison: [COMP01]\ncomparison: [test]\n'
            f'organism: {name} organism\n'
            f'user_id: {forged_owner}\nimport_id: 999999\n'
        )
        (folder / 'differential_abundance_comp01_test.tsv').write_text(
            'pg_protein_accessions\teg_modified_peptide\tstart\tend\tdiff\tadj_pval\tpval\tuser_id\n'
            f'P12345\tPEPTIDE\t1\t8\t2.0\t0.01\t0.02\t{forged_owner}\n'
        )
        (folder / 'go_term_comp01_test.tsv').write_text(
            'term\tgo_id\tpval\tadj_pval\tn_detected_proteins\tn_detected_proteins_in_process\t'
            'n_significant_proteins\tn_significant_proteins_in_process\tn_proteins_expected\tenrichment_type\tgo_type\tuser_id\n'
            f'Test term\tGO:0000001\t0.01\t0.02\t10\t5\t3\t2\t1.5\tover\tBP\t{forged_owner}\n'
        )
        return folder

    def test_scoped_cli_imports_ownership_failures_and_partial_completion(self):
        sys.path.insert(0, str(DATABASE_ROOT / 'src'))
        self.addCleanup(sys.path.remove, str(DATABASE_ROOT / 'src'))
        from click.testing import CliRunner
        from dspa.cli import main
        from dspa.ownership import bound_connection, create_import, get_import, resolve_user
        import mysql.connector

        specification = importlib.util.spec_from_file_location('dspa_import_mysql_fixture', HARNESS)
        harness = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(harness)
        with tempfile.TemporaryDirectory(prefix='dspa-import-cli-test-') as directory, harness.DisposableMysql() as database:
            database.sql(SQL_FILES[0].read_text())
            setup = SQL_FILES[1].read_text()
            for role in ('AI', 'AI_EXPLAINER', 'AI_DEFINER'):
                setup = setup.replace('__DSPA_DB_' + role + '_PASSWORD__', 'scoped-test-only')
            database.sql(setup)
            database.sql(SQL_FILES[2].read_text())
            database.sql(SQL_FILES[3].read_text())
            for account in ('dspa_importer', 'dspa_user_manager', 'dspa_context_manager'):
                database.sql(f"ALTER USER '{account}'@'%' IDENTIFIED BY 'scoped-test-only' ACCOUNT UNLOCK")
            fixtures = Path(directory)
            empty_environment = fixtures / 'empty.env'
            empty_environment.write_text('')
            environment = {key: value for key, value in os.environ.items() if not key.startswith(('MYSQL_', 'DSPA_'))}
            environment.update(
                MYSQL_HOST='localhost', MYSQL_PORT='3306', MYSQL_UNIX_SOCKET=str(database.socket),
                MYSQL_DATABASE='dspa_import', MYSQL_USER='dspa_importer', MYSQL_PASSWORD='scoped-test-only',
                DSPA_IDENTITY_DB_USER='dspa_user_manager', DSPA_IDENTITY_DB_PASSWORD='scoped-test-only',
                DSPA_CONTEXT_DB_USER='dspa_context_manager', DSPA_CONTEXT_DB_PASSWORD='scoped-test-only',
            )
            with patch.dict(os.environ, environment, clear=True):
                alice = resolve_user('verified-issuer', 'alice', env_file=empty_environment)
                bob = resolve_user('verified-issuer', 'bob', env_file=empty_environment)
                runner = CliRunner()
                folders = [self.fixture(fixtures, 'alice', bob), self.fixture(fixtures, 'bob', alice)]
                for owner, folder in zip((alice, bob), folders):
                    result = runner.invoke(main, [str(folder), '--user-id', str(owner), '--env-file', str(empty_environment)])
                    self.assertEqual(result.exit_code, 0, result.output + repr(result.exception))
                for table in harness.PRIVATE_TABLES:
                    self.assertEqual(database.rows(f'SELECT user_id,COUNT(*) FROM dynaprotdbv2.{table} GROUP BY user_id ORDER BY user_id'),
                                     [[str(alice), '1'], [str(bob), '1']], table)
                self.assertEqual(database.rows('SELECT user_id,status FROM dynaprotdbv2.imports ORDER BY user_id'),
                                 [[str(alice), 'succeeded'], [str(bob), 'succeeded']])
                self.assertEqual(database.rows('SELECT COUNT(*) FROM dynaprotdbv2.dynaprot_experiment WHERE import_id IS NULL'), [['0']])
                self.assertEqual(database.rows(
                    'SELECT user_id,taxonomy_id,organism_name FROM dynaprotdbv2.dynaprot_experiment ORDER BY user_id'),
                    [[str(alice), '9606', 'alice organism'], [str(bob), '9606', 'bob organism']])
                self.assertEqual(database.rows('SELECT COUNT(*) FROM dynaprotdbv2.organism'), [['0']])
                for owner, name in ((alice, 'alice organism'), (bob, 'bob organism')):
                    with bound_connection(owner, env_file=empty_environment) as connection:
                        with connection.cursor() as cursor:
                            cursor.execute('SELECT organism_name FROM dynaprot_experiment')
                            self.assertEqual(cursor.fetchall(), [(name,)])

                foreign_import = create_import(bob, 'foreign.zip', env_file=empty_environment)
                before = database.rows('SELECT COUNT(*) FROM dynaprotdbv2.dynaprot_experiment')
                result = runner.invoke(main, [str(folders[0]), '--user-id', str(alice), '--import-id', str(foreign_import),
                                              '--env-file', str(empty_environment)])
                self.assertNotEqual(result.exit_code, 0)
                self.assertEqual(database.rows('SELECT COUNT(*) FROM dynaprotdbv2.dynaprot_experiment'), before)
                self.assertEqual(get_import(bob, foreign_import, env_file=empty_environment)['status'], 'running')
                with self.assertRaises(PermissionError):
                    get_import(alice, foreign_import, env_file=empty_environment)

                with bound_connection(alice, env_file=empty_environment) as connection:
                    with connection.cursor() as cursor, self.assertRaises(mysql.connector.DatabaseError) as rejected:
                        cursor.execute('INSERT INTO dynaprot_experiment (dynaprot_experiment,user_id) VALUES (%s,%s)',
                                       ('DPX999999', bob))
                    self.assertEqual(rejected.exception.errno, 1369)
                with mysql.connector.connect(unix_socket=str(database.socket), user='dspa_importer',
                                             password='scoped-test-only', database='dspa_import') as unbound:
                    with unbound.cursor() as cursor, self.assertRaises(mysql.connector.DatabaseError) as rejected:
                        cursor.execute('INSERT INTO dynaprot_experiment (dynaprot_experiment,user_id) VALUES (%s,%s)',
                                       ('DPX999999', alice))
                    self.assertEqual(rejected.exception.errno, 1369)

                partial = fixtures / 'partial'
                partial.mkdir()
                self.fixture(partial, '01-good', bob)
                self.fixture(partial, '02-bad', bob, bad=True)
                result = runner.invoke(main, [str(partial), '--user-id', str(alice), '--env-file', str(empty_environment)])
                self.assertNotEqual(result.exit_code, 0)
                records = database.rows("SELECT id,status FROM dynaprotdbv2.imports WHERE original_filename='partial'")
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0][1], 'partial')
                partial_import = int(records[0][0])
                self.assertEqual(get_import(alice, partial_import, env_file=empty_environment)['committed_experiments'], 1)
                self.assertEqual(database.rows(f'SELECT COUNT(*) FROM dynaprotdbv2.dynaprot_experiment WHERE import_id={partial_import}'), [['1']])
                self.assertEqual(database.rows('SELECT COUNT(*) FROM dspa_security.connection_context'), [['0']])


if __name__ == '__main__':
    unittest.main()
