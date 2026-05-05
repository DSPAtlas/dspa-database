"""Download reviewed proteome data and GO annotations from UniProt REST API."""
from __future__ import annotations

import re
from typing import Iterator

import requests

_BASE = "https://rest.uniprot.org"
_TIMEOUT = 60

_GO_COLUMNS = {
    "go_f": "Gene Ontology (molecular function)",
    "go_p": "Gene Ontology (biological process)",
    "go_c": "Gene Ontology (cellular component)",
}
_GO_TERM_RE = re.compile(r"(.+?)\s*\[GO:(\d+)\]")


def get_reference_proteome(taxonomy_id: int) -> dict:
    """Return {proteome_id, organism_name} for a taxonomy's reference proteome."""
    resp = requests.get(
        f"{_BASE}/proteomes/search",
        params={
            "query": f"taxonomy_id:{taxonomy_id} AND reference:true",
            "format": "json",
            "size": 1,
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        raise ValueError(f"No reference proteome found for taxonomy {taxonomy_id}")
    p = results[0]
    return {
        "proteome_id": p["id"],
        "organism_name": p["taxonomy"]["scientificName"],
    }


def _parse_go_column(text: str) -> list[tuple[str, str]]:
    """Parse 'term [GO:0000001]; ...' into [(go_id, term), ...]."""
    return [
        (f"GO:{m.group(2)}", m.group(1).strip().lstrip(";").strip())
        for m in _GO_TERM_RE.finditer(text)
    ]


def stream_proteins(proteome_id: str) -> Iterator[dict]:
    """Yield one dict per reviewed protein in the proteome (handles pagination)."""
    url = f"{_BASE}/uniprotkb/search"
    params = {
        "query": f"proteome:{proteome_id} AND reviewed:true",
        "format": "tsv",
        "fields": "accession,id,protein_name,gene_names,sequence,go_f,go_p,go_c",
        "size": 500,
    }
    while url:
        resp = requests.get(url, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        lines = resp.text.splitlines()
        if len(lines) < 2:
            break
        headers = lines[0].split("\t")
        for line in lines[1:]:
            if line.strip():
                yield dict(zip(headers, line.split("\t")))
        link = resp.headers.get("Link", "")
        m = re.search(r'<([^>]+)>;\s*rel="next"', link)
        url = m.group(1) if m else None
        params = {}


def populate_reference_tables(
    taxonomy_ids: list[int],
    connection,
    truncate: bool = False,
) -> dict[str, int]:
    """Fetch reviewed proteins + GO terms from UniProt and populate reference tables.

    Populates organism, organism_proteome, organism_proteome_entries, go_term.
    Returns a dict of {table: rows_inserted}.
    """
    cursor = connection.cursor()
    counts = {"organism_proteome": 0, "organism_proteome_entries": 0, "go_term": 0}

    if truncate:
        cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        for table in ("go_term", "organism_proteome_entries", "organism_proteome"):
            cursor.execute(f"TRUNCATE TABLE `{table}`")
        cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        connection.commit()

    for taxid in taxonomy_ids:
        info = get_reference_proteome(taxid)
        proteome_id = info["proteome_id"]
        organism_name = info["organism_name"]

        cursor.execute(
            "INSERT IGNORE INTO organism (taxonomy_id, organism_name) VALUES (%s, %s)",
            (taxid, organism_name),
        )
        cursor.execute(
            "INSERT IGNORE INTO organism_proteome (proteome_id, taxonomy_id) VALUES (%s, %s)",
            (proteome_id, taxid),
        )
        counts["organism_proteome"] += cursor.rowcount

        entry_batch: list[tuple] = []
        go_batch: list[tuple] = []

        for protein in stream_proteins(proteome_id):
            accession = protein.get("Entry", "")
            entry_name = protein.get("Entry Name", "")
            seq_id = f"sp|{accession}|{entry_name}"
            seq = protein.get("Sequence", "")
            description = protein.get("Protein names", "")[:255]
            gene_names = protein.get("Gene Names", "")
            gene_name = gene_names.split()[0] if gene_names.strip() else ""

            entry_batch.append((proteome_id, taxid, seq_id, seq, accession, description, gene_name))

            for col_header in _GO_COLUMNS.values():
                for go_id, term in _parse_go_column(protein.get(col_header, "")):
                    go_batch.append((go_id, term, accession, taxid))

        if entry_batch:
            cursor.executemany(
                """
                INSERT IGNORE INTO organism_proteome_entries
                    (proteome_id, taxonomy_id, seq_id, seq, protein_name, protein_description, gene_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                entry_batch,
            )
            counts["organism_proteome_entries"] += cursor.rowcount

        if go_batch:
            cursor.executemany(
                "INSERT INTO go_term (go_id, go_term, accessions, taxonomy_id) VALUES (%s, %s, %s, %s)",
                go_batch,
            )
            counts["go_term"] += cursor.rowcount

        connection.commit()

    cursor.close()
    return counts
