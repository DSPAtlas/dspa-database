"""CLI entry points for dspa tooling.

dspa-ingest   ROOT --user-id USER_ID [--dry-run] [--env-file]
dspa-import-dump  DUMP [--truncate] [--env-file]
"""
from __future__ import annotations

import signal
import threading
from contextlib import contextmanager, suppress
from pathlib import Path

import click

from dspa.db import get_connection
from dspa.ingest import ingest_experiment
from dspa.ownership import (
    allocate_experiment_id, bound_connection, create_import, finish_import, get_import,
)
from dspa.dump import import_reference_tables, REFERENCE_TABLES
from dspa.uniprot import populate_reference_tables


def _find_experiment_folders(root: Path) -> list[Path]:
    if (root / "params.yaml").exists():
        return [root]
    return sorted(p.parent for p in root.rglob("params.yaml"))


@contextmanager
def _handle_termination():
    """Let SIGTERM unwind transactions; SIGKILL still relies on socket closure."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def interrupted(*_):
        raise InterruptedError("Import cancelled")

    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


@click.command()
@click.argument("root", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--user-id", type=click.IntRange(1, 4294967295), required=True,
              help="Existing database user ID that owns every experiment in this import.")
@click.option("--import-id", type=click.IntRange(1, 18446744073709551615), default=None,
              help="An existing running import owned by this user; otherwise create one.")
@click.option("--dry-run", is_flag=True, help="Preview folders to be ingested; do not write to DB.")
@click.option("--env-file", type=click.Path(exists=True, path_type=Path), default=None,
              help="Path to .env file (default: .env in repo root).")
def main(root: Path, user_id: int, import_id: int | None, dry_run: bool, env_file: Path | None) -> None:
    folders = _find_experiment_folders(root)

    click.echo(f"Found {len(folders)} experiment folder(s):")
    for f in folders:
        click.echo(f"  {f}")

    if dry_run:
        click.echo("\n--dry-run: no data written.")
        return

    with _handle_termination():
        diagnostic = "ingestion failed"
        try:
            if import_id is None:
                import_id = create_import(user_id, root.name, env_file=env_file)
            record = get_import(user_id, import_id, env_file=env_file)
            if record["status"] != "running":
                raise ValueError("Import has already finished")
            click.echo(f"Import {import_id}")
            if not folders:
                diagnostic = "empty archive"
                raise ValueError("No experiment folders found")
            with bound_connection(user_id, env_file=env_file) as connection:
                for folder in folders:
                    click.echo(f"\nIngesting {folder} …")
                    dpx_id = allocate_experiment_id(env_file=env_file)
                    ingest_experiment(folder, connection, dry_run=False, user_id=user_id,
                                      import_id=import_id, dpx_id=dpx_id)
                    click.echo(f"  -> {dpx_id}")
            status = finish_import(user_id, import_id, env_file=env_file)
        except BaseException as error:
            interrupted = isinstance(error, (KeyboardInterrupt, InterruptedError))
            if import_id is not None:
                with suppress(Exception):
                    finish_import(user_id, import_id, failed=True,
                                  diagnostic="cancelled" if interrupted else diagnostic,
                                  env_file=env_file)
            if isinstance(error, SystemExit):
                raise
            message = "Import interrupted." if interrupted else "Import failed; consult its import status."
            raise click.ClickException(message) from None

    click.echo(f"\nDone: {status}.")


@click.command("import-dump")
@click.argument("dump", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--truncate", is_flag=True,
              help=f"Truncate {', '.join(REFERENCE_TABLES)} before importing.")
@click.option("--env-file", type=click.Path(exists=True, path_type=Path), default=None,
              help="Path to .env file (default: .env in repo root).")
def import_dump(dump: Path, truncate: bool, env_file: Path | None) -> None:
    """Import go_term, organism_proteome, and organism_proteome_entries from a mysqldump file."""
    click.echo(f"Reading {dump} …")
    connection = get_connection(env_file)
    try:
        counts = import_reference_tables(dump, connection, truncate=truncate)
    finally:
        connection.close()

    for table, n in counts.items():
        click.echo(f"  {table}: {n} rows inserted")
    click.echo("Done.")


@click.command("build-reference")
@click.argument("taxonomy_ids", nargs=-1, type=int, required=True)
@click.option("--truncate", is_flag=True,
              help="Truncate go_term, organism_proteome, and organism_proteome_entries before importing.")
@click.option("--env-file", type=click.Path(exists=True, path_type=Path), default=None,
              help="Path to .env file (default: .env in repo root).")
def build_reference(taxonomy_ids: tuple[int, ...], truncate: bool, env_file: Path | None) -> None:
    """Download reviewed proteins and GO terms from UniProt for given taxonomy IDs.

    Example: dspa-build-reference 9606 10090 559292
    """
    click.echo(f"Building reference tables for taxonomy IDs: {', '.join(str(t) for t in taxonomy_ids)}")
    connection = get_connection(env_file)
    try:
        counts = populate_reference_tables(list(taxonomy_ids), connection, truncate=truncate)
    finally:
        connection.close()

    for table, n in counts.items():
        click.echo(f"  {table}: {n} rows inserted")
    click.echo("Done.")
