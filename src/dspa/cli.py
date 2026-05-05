"""CLI entry points for dspa tooling.

dspa-ingest   ROOT [--dry-run] [--env-file]
dspa-import-dump  DUMP [--truncate] [--env-file]
"""
from __future__ import annotations

from pathlib import Path

import click

from dspa.db import get_connection
from dspa.ingest import ingest_experiment
from dspa.dump import import_reference_tables, REFERENCE_TABLES
from dspa.uniprot import populate_reference_tables


def _find_experiment_folders(root: Path) -> list[Path]:
    if (root / "params.yaml").exists():
        return [root]
    return sorted(p.parent for p in root.rglob("params.yaml"))


@click.command()
@click.argument("root", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--dry-run", is_flag=True, help="Preview folders to be ingested; do not write to DB.")
@click.option("--env-file", type=click.Path(exists=True, path_type=Path), default=None,
              help="Path to .env file (default: .env in repo root).")
def main(root: Path, dry_run: bool, env_file: Path | None) -> None:
    folders = _find_experiment_folders(root)

    if not folders:
        click.echo(f"No experiment folders (containing params.yaml) found under {root}")
        return

    click.echo(f"Found {len(folders)} experiment folder(s):")
    for f in folders:
        click.echo(f"  {f}")

    if dry_run:
        click.echo("\n--dry-run: no data written.")
        return

    connection = get_connection(env_file)
    try:
        for folder in folders:
            click.echo(f"\nIngesting {folder} …")
            dpx_id = ingest_experiment(folder, connection, dry_run=False)
            click.echo(f"  -> {dpx_id}")
    finally:
        connection.close()

    click.echo("\nDone.")


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
