# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Dev Setup

```bash
cp .env.example .env && uv sync
docker compose up -d   # MySQL :3306 + Adminer :8080
```

Adminer: http://localhost:8080 — server `mysql`, user/password `dspa`, database `dynaprotdbv2`. Schema is applied automatically from `docker/init/01_schema.sql` on first start. Credentials live in `.env` (loaded via `python-dotenv`; never hardcode them).

## CLI Commands

```bash
uv run dspa-ingest /path/to/root          # ingest all experiment folders recursively
uv run dspa-ingest /path/to/folder        # ingest a single experiment folder
uv run dspa-ingest /path/to/root --dry-run

uv run dspa-import-dump /path/to/dump.sql            # import reference tables from mysqldump
uv run dspa-import-dump /path/to/dump.sql --truncate # wipe first, then import

uv run dspa-build-reference 9606 10090 559292         # fetch from UniProt by taxonomy ID
uv run dspa-build-reference 9606 --truncate
```

## Architecture

### Package (`src/dspa/`)

- **`db.py`** — `get_connection()`: loads `.env`, returns MySQL connection
- **`ingest.py`** — `ingest_experiment(folder, connection)`: full pipeline for one experiment folder; reads `params.yaml`, bulk-inserts into `differential_abundance` and `go_analysis`, computes and inserts `protein_scores`; single commit per folder
- **`dump.py`** — `import_reference_tables()`: streams a mysqldump and executes only INSERT statements for `go_term`, `organism_proteome`, `organism_proteome_entries`
- **`uniprot.py`** — `populate_reference_tables()`: fetches reviewed proteins + GO annotations from UniProt REST API for given taxonomy IDs; handles pagination
- **`cli.py`** — Click entry points for all three commands above

### Ingestion Details

Experiment input files (all in the folder alongside `params.yaml`):
- `differential_abundance_{comp_id}_{comp_name}.tsv` — comparison names with `/` are sanitised to `_` for filenames
- `go_term_{comp_id}_{comp_name}.tsv` — tab-delimited; `go_id` values arrive as `[GO:0000001]` and are stored stripped as `GO:0000001`
- `qc_plots.pdf` — optional, stored as LONGBLOB

`params.yaml` key fields: `dpx_comparison` (list of short IDs), `comparison` (list of human-readable names, same length), `taxonomy_id`, plus remaining fields mapping 1:1 to `dynaprot_experiment` columns.

ID scheme: experiment `DPX000001` (auto-incremented), comparison `DPX000001-C01`.

Protein score formula: `-log10(adj_pval + 1e-10) + |diff|`, summed per protein, only for rows where `adj_pval < 0.05` and `|diff| > 0.2`.

### Schema

```
organism ──< organism_proteome ──< organism_proteome_entries
dynaprot_experiment ──< dynaprot_experiment_comparison ──< differential_abundance
                                                       ──< protein_scores
                                                       ──< go_analysis ──> go_term
```

Key indexes (apply after bulk imports via `INDEXES.SQL`): `idx_ope_taxonomy_protein`, `idx_da_comparison_accession_pos`, `idx_ps_dpx_protein_score`.

## Legacy Code

`databaseSetUp/` and `uploadNewExperiment/` are reference only — buggy and use hardcoded credentials. All active code is in `src/dspa/`.
