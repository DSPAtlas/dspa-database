"""Import selected tables from a mysqldump file.

Streams the dump line by line and executes only the INSERT statements
for the requested tables, leaving the rest of the database untouched.
"""
from __future__ import annotations

import re
from pathlib import Path

import click

REFERENCE_TABLES = ("go_term", "organism_proteome", "organism_proteome_entries")

_INSERT_RE = re.compile(
    r"^INSERT INTO `(" + "|".join(re.escape(t) for t in REFERENCE_TABLES) + r")` VALUES ",
    re.IGNORECASE,
)


def import_reference_tables(
    dump_path: Path,
    connection,
    truncate: bool = False,
) -> dict[str, int]:
    """Execute INSERT statements for reference tables from a mysqldump file.

    Returns a dict of {table: rows_inserted}.
    """
    cursor = connection.cursor()

    if truncate:
        cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        for table in REFERENCE_TABLES:
            cursor.execute(f"TRUNCATE TABLE `{table}`")
            click.echo(f"  Truncated {table}")
        cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        connection.commit()

    counts: dict[str, int] = {t: 0 for t in REFERENCE_TABLES}

    with dump_path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = _INSERT_RE.match(line)
            if not m:
                continue
            table = m.group(1).lower()
            cursor.execute(line.rstrip().rstrip(";"))
            counts[table] += cursor.rowcount

    connection.commit()
    cursor.close()
    return counts
