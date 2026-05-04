"""Ingestion logic for a single experiment folder.

An experiment folder must contain params.yaml and one or more pairs of:
  differential_abundance_{comp_id}_{comparison_name}.tsv
  go_term_{comp_id}_{comparison_name}.csv  (tab-delimited despite .csv extension)
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _replace_missing(value, default=None):
    if value is None:
        return default
    if isinstance(value, float) and (math.isnan(value) or not math.isfinite(value)):
        return default
    if isinstance(value, str) and value.strip().upper() in {"NA", "NAN", ""}:
        return default
    return value


def _generate_next_id(cursor, table: str, column: str, prefix: str) -> str:
    cursor.execute(f"SELECT MAX({column}) FROM {table}")
    result = cursor.fetchone()[0]
    num = int(result.replace(prefix, "")) + 1 if result else 1
    return f"{prefix}{num:06d}"


def _get_diff_value(row: pd.Series):
    """Return diff or adj_diff, whichever is present."""
    return row.get("diff") if "diff" in row else row.get("adj_diff")


# ---------------------------------------------------------------------------
# Protein score calculation
# ---------------------------------------------------------------------------

_QVAL_CUTOFF = 0.05
_LOG2FC_CUTOFF = 0.2


def _compute_protein_scores(da_rows: list[dict]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for row in da_rows:
        diff_value = row["diff"] if row["diff"] is not None else 0.0
        log2fc = 0.0 if not math.isfinite(diff_value) else diff_value
        qvalue = row["adj_pval"]
        if qvalue is None:
            continue
        accession = row["pg_protein_accessions"]
        if accession not in scores:
            scores[accession] = 0.0
        if qvalue < _QVAL_CUTOFF and abs(log2fc) > _LOG2FC_CUTOFF:
            scores[accession] += -math.log10(qvalue + 1e-10) + abs(log2fc)
    return scores


# ---------------------------------------------------------------------------
# Main ingestion entry point
# ---------------------------------------------------------------------------

def ingest_experiment(folder: Path, connection, dry_run: bool = False) -> str:
    """Ingest one experiment folder. Returns the assigned dpx_id.

    Inserts into:
      dynaprot_experiment
      dynaprot_experiment_comparison  (one row per comparison)
      differential_abundance          (one row per peptide per comparison)
      go_analysis                     (one row per GO term per comparison)
      protein_scores                  (one row per protein per comparison)
    """
    params_file = folder / "params.yaml"
    if not params_file.exists():
        raise FileNotFoundError(f"No params.yaml in {folder}")

    with params_file.open() as f:
        params = yaml.safe_load(f)

    pdf_data = None
    pdf_path = folder / "qc_plots.pdf"
    if pdf_path.exists():
        pdf_data = pdf_path.read_bytes()

    cursor = connection.cursor()

    dpx_id = _generate_next_id(cursor, "dynaprot_experiment", "dynaprot_experiment", "DPX")

    if not dry_run:
        cursor.execute(
            """
            INSERT INTO dynaprot_experiment (
                dynaprot_experiment, perturbation, `condition`, taxonomy_id, strain,
                instrument, number_of_lip_files, number_of_tr_files, experiment,
                approach, reference_for_protocol, data_analysis, publication, doi,
                search_settings, fasta, data_re_analysis_settings, path_to_raw_files,
                digestion_protocol, e_s_ratio, pk_digestion_time_in_sec, protease,
                author, input_file, qc_pdf_file
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                dpx_id,
                _replace_missing(params.get("perturbation")),
                _replace_missing(params.get("condition")),
                int(params.get("taxonomy_id", 0)),
                _replace_missing(params.get("strain")),
                _replace_missing(params.get("instrument")),
                int(params.get("n_files", 0)),
                int(params.get("n_files_trp", 0)),
                _replace_missing(params.get("experiment")),
                _replace_missing(params.get("approach")),
                _replace_missing(params.get("reference_to_protocol")),
                _replace_missing(params.get("data_analysis")),
                _replace_missing(params.get("publication")),
                _replace_missing(params.get("doi")),
                _replace_missing(params.get("search_settings")),
                _replace_missing(params.get("fasta")),
                _replace_missing(params.get("data_reanalysis_settings")),
                _replace_missing(params.get("path_to_raw_files")),
                _replace_missing(params.get("digestion_protocol")),
                _replace_missing(params.get("e_s_ratio")),
                _replace_missing(params.get("pk_digestion_time")),
                _replace_missing(params.get("protease")),
                _replace_missing(params.get("author")),
                _replace_missing(params.get("input_file")),
                pdf_data,
            ),
        )

    comp_ids: list[str] = params.get("dpx_comparison", [])
    comp_names: list[str] = params.get("comparison", [])

    if len(comp_ids) != len(comp_names):
        raise ValueError(
            f"{folder}: dpx_comparison and comparison lists have different lengths"
        )

    for comp_id, comp_name in zip(comp_ids, comp_names):
        dpx_comp_id = f"{dpx_id}-{comp_id}"
        comp_name_safe = comp_name.replace("/", "_")

        if not dry_run:
            cursor.execute(
                """
                INSERT INTO dynaprot_experiment_comparison
                    (dpx_comparison, taxonomy_id, `condition`, dose, dynaprot_experiment)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (
                    dpx_comp_id,
                    int(params.get("taxonomy_id", 0)),
                    _replace_missing(params.get("condition")),
                    comp_name,
                    dpx_id,
                ),
            )

        # -- differential abundance --
        da_file = folder / f"differential_abundance_{comp_id}_{comp_name_safe}.tsv"
        da_rows: list[dict] = []
        if da_file.exists():
            df = pd.read_csv(da_file, sep="\t").where(pd.notnull, None)
            if "start" in df.columns:
                df = df.rename(columns={"start": "pos_start", "end": "pos_end"})
            for _, row in df.iterrows():
                da_rows.append(
                    {
                        "dpx_comparison": dpx_comp_id,
                        "pg_protein_accessions": _replace_missing(row.get("pg_protein_accessions")),
                        "pep_grouping_key": _replace_missing(row.get("eg_modified_peptide")),
                        "pos_start": _replace_missing(row.get("pos_start")),
                        "pos_end": _replace_missing(row.get("pos_end")),
                        "diff": _replace_missing(_get_diff_value(row)),
                        "adj_pval": _replace_missing(row.get("adj_pval")),
                    }
                )
            if not dry_run:
                cursor.executemany(
                    """
                    INSERT INTO differential_abundance
                        (dpx_comparison, pg_protein_accessions, pep_grouping_key,
                         pos_start, pos_end, diff, adj_pval)
                    VALUES (%(dpx_comparison)s, %(pg_protein_accessions)s, %(pep_grouping_key)s,
                            %(pos_start)s, %(pos_end)s, %(diff)s, %(adj_pval)s)
                    """,
                    da_rows,
                )

        # -- GO analysis --
        go_file = folder / f"go_term_{comp_id}_{comp_name_safe}.tsv"
        if go_file.exists():
            df = pd.read_csv(go_file, sep="\t").where(pd.notnull, None)
            go_rows = [
                {
                    "dpx_comparison": dpx_comp_id,
                    "term": _replace_missing(row.get("term")),
                    "go_id": _replace_missing(str(row["go_id"]).strip("[]")) if row.get("go_id") else None,
                    "pval": _replace_missing(row.get("pval")),
                    "adj_pval": _replace_missing(row.get("adj_pval")),
                    "n_detected_proteins": _replace_missing(row.get("n_detected_proteins")),
                    "n_detected_proteins_in_process": _replace_missing(row.get("n_detected_proteins_in_process")),
                    "n_significant_proteins": _replace_missing(row.get("n_significant_proteins")),
                    "n_significant_proteins_in_process": _replace_missing(row.get("n_significant_proteins_in_process")),
                    "n_proteins_expected": _replace_missing(row.get("n_proteins_expected")),
                    "enrichment_type": _replace_missing(row.get("enrichment_type")),
                    "go_type": _replace_missing(row.get("go_type")),
                }
                for _, row in df.iterrows()
            ]
            if not dry_run:
                cursor.executemany(
                    """
                    INSERT INTO go_analysis
                        (dpx_comparison, term, go_id, pval, adj_pval,
                         n_detected_proteins, n_detected_proteins_in_process,
                         n_significant_proteins, n_significant_proteins_in_process,
                         n_proteins_expected, enrichment_type, go_type)
                    VALUES (%(dpx_comparison)s, %(term)s, %(go_id)s, %(pval)s, %(adj_pval)s,
                            %(n_detected_proteins)s, %(n_detected_proteins_in_process)s,
                            %(n_significant_proteins)s, %(n_significant_proteins_in_process)s,
                            %(n_proteins_expected)s, %(enrichment_type)s, %(go_type)s)
                    """,
                    go_rows,
                )

        # -- protein scores (computed from differential abundance rows) --
        scores = _compute_protein_scores(da_rows)
        if scores and not dry_run:
            cursor.executemany(
                """
                INSERT INTO protein_scores
                    (pg_protein_accessions, protein_description, cumulativeScore, dpx_comparison)
                VALUES (%s, %s, %s, %s)
                """,
                [(acc, None, score, dpx_comp_id) for acc, score in scores.items()],
            )

    if not dry_run:
        connection.commit()

    cursor.close()
    return dpx_id
