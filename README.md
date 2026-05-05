# dspa-database

Database schema and ingestion tooling for the [DynaProt/DSPAtlas](https://www.dynaprot.org) platform. Stores Limited proteolysis (LiP) mass spectrometry experiments in a MySQL database (`dynaprotdbv2`).

## Tables

| Table | Description |
|---|---|
| `dynaprot_experiment` | Top-level experiment metadata |
| `dynaprot_experiment_comparison` | One row per comparison within an experiment |
| `differential_abundance` | Peptide-level LiP differential abundance data |
| `protein_scores` | Cumulative per-protein scores aggregated from differential abundance |
| `go_analysis` | GO term enrichment results per comparison |
| `go_term` | GO term reference data per organism |
| `organism` / `organism_proteome` / `organism_proteome_entries` | Reference proteomes |

## Setup

**Prerequisites:** [uv](https://docs.astral.sh/uv/), Docker

```bash
git clone https://github.com/DSPAtlas/dspa-database
cd dspa-database
uv sync
cp .env.example .env
```

Edit `.env` with your database credentials before running any ingestion commands.

## Development (local MySQL via Docker)

```bash
docker compose up -d
```

This starts:
- **MySQL 8** on `localhost:3306` — schema is applied automatically on first start
- **Adminer** on [http://localhost:8080](http://localhost:8080) — web UI for browsing the database

Adminer login: server `mysql`, user `dspa`, password `dspa`, database `dynaprotdbv2`.

The default `.env.example` credentials match this Docker setup, so no edits are needed for local development.

```bash
docker compose down          # stop containers (data persisted in Docker volume)
docker compose down -v       # stop and wipe the database volume
```

## Ingesting Experiments

An experiment folder must contain a `params.yaml` file plus one or more data files per comparison:
- `differential_abundance_{comp_id}_{comparison_name}.tsv`
- `go_term_{comp_id}_{comparison_name}.csv` *(tab-delimited)*
- `qc_plots.pdf` *(optional)*

```bash
# Ingest a single experiment folder
uv run dspa-ingest /path/to/LiP_School9_LiP

# Ingest all experiments found recursively under a root directory
uv run dspa-ingest /path/to/data/root

# Preview what would be ingested without writing anything to the database
uv run dspa-ingest /path/to/data/root --dry-run

# Point at a specific .env file (defaults to .env in the repo root)
uv run dspa-ingest /path/to/data/root --env-file /path/to/.env.production
```

Each folder is ingested in a single transaction: experiment metadata, comparisons, differential abundance, GO analysis, and protein scores are all committed together or not at all.

## Populating Reference Tables

`go_term`, `organism_proteome`, and `organism_proteome_entries` are reference data that can be populated in two ways:

### Option A — from a mysqldump

```bash
# Append rows from a production dump
uv run dspa-import-dump /path/to/dump.sql

# Wipe and replace (full refresh)
uv run dspa-import-dump /path/to/dump.sql --truncate
```

Only `INSERT` statements for the three reference tables are read from the dump — everything else is ignored. The file is streamed line by line so large dumps are handled without loading them into memory.

### Option B — directly from UniProt

Downloads reviewed (Swiss-Prot) proteins and GO annotations for the given NCBI taxonomy IDs via the UniProt REST API.

```bash
# One or more taxonomy IDs
uv run dspa-build-reference 9606 10090 559292 83333

# Wipe reference tables first, then rebuild
uv run dspa-build-reference 9606 10090 --truncate
```

Common taxonomy IDs: `9606` (human), `10090` (mouse), `559292` (yeast), `83333` (E. coli K-12).

`organism` rows are created or updated automatically. For each taxonomy, the reference proteome is resolved from UniProt, then all reviewed entries are downloaded with their sequences and GO term associations (molecular function, biological process, cellular component).

## Database Indexes

After a large bulk import, apply the performance indexes:

```bash
mysql -u $MYSQL_USER -p$MYSQL_PASSWORD -h $MYSQL_HOST -P $MYSQL_PORT $MYSQL_DATABASE < INDEXES.SQL
```
