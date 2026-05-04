# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Dev Setup

```bash
cp .env.example .env          # fill in credentials
uv sync                       # install package + deps into .venv
docker compose up -d          # spin up MySQL (port 3306) + Adminer (port 8080)
uv run dspa-ingest --help
```

Adminer: http://localhost:8080 — server `mysql`, user `dspa`, password `dspa`, database `dynaprotdbv2`.

The Docker MySQL container auto-applies `docker/init/01_schema.sql` on first start.

## Overview

This repo manages the MySQL database (`dynaprotdbv2`) for the [DynaProt/DSPAtlas](https://www.dynaprot.org) platform, which stores Limited proteolysis (LiP) mass spectrometry experiment data. The database lives on a remote VM at `sysbc-lx-s03.ethz.ch` and is accessed at port 3307.

## Ingesting Experiments

```bash
# Ingest all experiment folders under a root directory (recursive):
uv run dspa-ingest /path/to/data/root

# Ingest a single experiment folder:
uv run dspa-ingest /path/to/LiP_School9_LiP

# Preview what would be ingested without writing to the DB:
uv run dspa-ingest /path/to/data/root --dry-run
```

The CLI walks the tree, finds every subfolder containing a `params.yaml`, and runs the full ingestion pipeline (metadata → differential abundance → GO analysis → protein scores) for each.

The old shell-based upload to the remote VM lives in `uploadNewExperiment/` (kept for reference).

## Database Connection

All scripts expect these environment variables (never hardcode credentials):

```bash
export MYSQL_USER=root
export MYSQL_PASSWORD=...
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3307
export MYSQL_DATABASE=dynaprotdbv2
```

## Architecture

### Ingestion Pipeline (`src/dspa/`)

The canonical code lives in the `src/dspa/` package:

- **`db.py`** — `get_connection()` loads `.env` via `python-dotenv` and returns a MySQL connection
- **`ingest.py`** — `ingest_experiment(folder, connection)` handles one experiment folder end-to-end:
  - reads `params.yaml` → inserts `dynaprot_experiment` + `dynaprot_experiment_comparison` rows
  - reads `differential_abundance_{comp_id}_{comp_name}.tsv` → bulk-inserts into `differential_abundance`
  - reads `go_term_{comp_id}_{comp_name}.csv` (tab-delimited) → bulk-inserts into `go_analysis`
  - computes protein scores in-memory from the DA rows → inserts into `protein_scores`
  - commits once per folder
- **`cli.py`** — Click CLI (`dspa-ingest`); walks a root directory for `params.yaml` files, calls `ingest_experiment` for each

Score formula: `-log10(adj_pval + 1e-10) + |diff|`, accumulated per protein, only for rows where `adj_pval < 0.05` and `|diff| > 0.2`.

### ID Scheme

- Experiment ID: `DPX000001` (auto-incremented from `MAX(dynaprot_experiment)`)
- Comparison ID: `DPX000001-COMP01` (concatenated from `dpx_id` + `-` + comp_id from `params.yaml`)

### Schema

```
organism ──< organism_proteome ──< organism_proteome_entries
dynaprot_experiment ──< dynaprot_experiment_comparison ──< differential_abundance
                                                       ──< protein_scores
                                                       ──< go_analysis ──> go_term
```

`dpx_comparison` (VARCHAR 11) is the FK joining comparisons to their data rows across `differential_abundance`, `protein_scores`, and `go_analysis`.

### Indexes

After any bulk upload, apply or verify the indexes in `INDEXES.SQL`. The most performance-critical are:
- `idx_ope_taxonomy_protein` on `organism_proteome_entries(taxonomy_id, protein_name)`
- `idx_da_comparison_accession_pos` on `differential_abundance(dpx_comparison, pg_protein_accessions, pos_start)`
- `idx_ps_dpx_protein_score` on `protein_scores(dpx_comparison, pg_protein_accessions, cumulativeScore)`

### `params.yaml` Format

Key fields read by `metadata.py`:
- `dpx_comparison`: list of short comparison IDs (e.g. `["C01", "C02"]`)
- `comparison`: list of human-readable names matching the TSV/CSV filenames (same length as `dpx_comparison`)
- `taxonomy_id`: NCBI taxonomy integer (9606=human, 10090=mouse, 559292=yeast, 83333/562=E. coli)
- All other fields map 1:1 to `dynaprot_experiment` columns

## Legacy Code

`databaseSetUp/` and `uploadNewExperiment/` are kept for reference only. Do not use them as templates — they have hardcoded credentials, a bug where `dpx_id` is used without being assigned, and a missing `import os`. All new work goes through `src/dspa/`.
