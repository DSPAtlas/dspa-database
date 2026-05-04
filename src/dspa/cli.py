"""CLI entry point for dspa-ingest.

Usage:
  dspa-ingest /path/to/data/root          # walk tree, ingest all experiment folders
  dspa-ingest /path/to/single/experiment  # ingest a single folder
  dspa-ingest /path/to/data/root --dry-run
"""
from __future__ import annotations

from pathlib import Path

import click

from dspa.db import get_connection
from dspa.ingest import ingest_experiment


def _find_experiment_folders(root: Path) -> list[Path]:
    """Return all directories under root that contain a params.yaml."""
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
