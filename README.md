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

This is the legacy shared-schema development stack. It supports reference-data
work with its administrative credentials; it does not provide the ownership
schema, scoped importer account, or control accounts required by ingestion.
For the complete importer use the main DSPA database stack and provision the
credentials shown in `.env.example`.

```bash
docker compose down          # stop containers (data persisted in Docker volume)
docker compose down -v       # stop and wipe the database volume
```

## Ingesting Experiments

Imports require the per-user schema installed by the main DSPA database image,
an active numeric ID from `users`, and all three account credentials in
`.env.example`. Set `MYSQL_DATABASE=dspa_import` and use `dspa_importer` as the
data account. The identity and context accounts execute their narrow management
procedures through separate connections to the same MySQL server.

An experiment folder must contain a `params.yaml` file plus one or more data files per comparison:
- `differential_abundance_{comp_id}_{comparison_name}.tsv`
- `go_term_{comp_id}_{comparison_name}.tsv`
- `qc_plots.pdf` *(optional)*

Filenames are matched without regard to case, including `params.yaml`, comparison
TSVs, and the QC PDF. For example, `cAMP_0.1mM_vs_CTR_LiP` in the YAML can use
`differential_abundance_1_camp_0.1mm_vs_ctr_lip.tsv`. Comparison names stored in the
database retain their original spelling. If multiple files differ only by case,
the import rejects the ambiguous match instead of selecting one.

The optional `organism` name in `params.yaml` is stored as `organism_name` on the
owned experiment alongside `taxonomy_id`. Names are trimmed and limited to 255
characters; missing, blank, `NA`, and `NaN` names are stored as null. Uploads do not
write to the shared organism reference table. Private visualization reads use the
uploaded name when available and fall back to the reference name otherwise.
Existing installations need the `setup_organism_names.sql` schema extension before
running this importer version.

```bash
# Ingest a single experiment folder
uv run dspa-ingest /path/to/LiP_School9_LiP --user-id 42

# Ingest all experiments found recursively under a root directory
uv run dspa-ingest /path/to/data/root --user-id 42

# Preview what would be ingested without writing anything to the database
uv run dspa-ingest /path/to/data/root --user-id 42 --dry-run

# Point at a specific .env file (defaults to .env in the repo root)
uv run dspa-ingest /path/to/data/root --user-id 42 --env-file /path/to/.env.production

# Web workers pass the already-created import record; it must belong to user 42
uv run dspa-ingest /path/to/data/root --user-id 42 --import-id 123
```

`--user-id` is required, including for previews, and must be between 1 and
4294967295 (`INT UNSIGNED`). Every experiment, comparison, differential-abundance,
GO-analysis, and protein-score row receives this owner. Ownership fields in uploaded
metadata are ignored. The existing publication/DOI rules for `is_hidden` still apply.

The caller must obtain this ID from authenticated server context or a trusted
administrative invocation. The CLI binds the actual data connection to this owner
using the separate context account. Both connections must report the same MySQL
server UUID. Scoped writable views enforce the owner with `WITH CHECK OPTION`;
the importer account has no direct privileges on private base tables. The CLI
does not authenticate an arbitrary human who has access to its service credentials.

Each run creates an owned `imports` record unless `--import-id` supplies an
existing running record owned by the same user. Every experiment links to it.
Each folder commits as one transaction and rolls back on errors or interruption.
Earlier committed folders survive a later failure: the record becomes `partial`
when any experiment committed, otherwise `failed`. Successful runs become
`succeeded`; repeated finalization preserves an existing terminal status.

Experiment IDs are reserved through `dspa_security.allocate_experiment_id` on a
separate autocommit connection. Failed imports may leave gaps. Archive fields
cannot choose an owner, import record, or experiment ID.

`dspa.ownership` exposes the shared synchronous APIs used by the CLI and web
importer: `resolve_user(issuer, subject)`, `bound_connection(user_id)`,
`create_import(user_id, filename)`, `get_import(user_id, import_id)`, and
`finish_import(user_id, import_id, failed=False, diagnostic="")`. They accept an
optional `env_file`. Identity resolution requires a previously verified OIDC
issuer and subject. `get_import` returns metadata and the committed experiment
count; `finish_import` returns the terminal status. Stored failure diagnostics use
fixed safe messages, never raw database or subprocess errors.

Bindings refresh before SQL statements and commit, with an eight-hour lease.
Connections are never pooled or reconnected. Normal exit, Python exceptions, and
SIGTERM attempt rollback, context removal, and connection disposal. After a hard
kill, MySQL closes the session and any surviving context expires; its thread ID
cannot authorize a replacement connection. A parent worker should finalize the
import after waiting for the terminated child.

Run the CLI and ingestion regression tests after installing the project dependencies:

```bash
uv run python -m unittest discover -s tests -v
```

`tests/test_mysql_import.py` additionally uses disposable socket-only MySQL when
local `mysqld`/`mysql` binaries and the sibling `dspa-mcp` checkout are available.
It runs the real CLI with scoped service credentials and verifies isolation,
partial imports, and context cleanup. Otherwise it reports an explicit skip.
The HTTP-to-subprocess flow is covered by the sibling project's
`tests/test_importer_flow.py`; run it from `dspa-mcp` with
`importer/.venv/bin/python -m unittest discover -s tests -p test_importer_flow.py -v`.

## Populating Reference Tables

`go_term`, `organism_proteome`, and `organism_proteome_entries` are reference data that can be populated in two ways:

Use a separate administrative `--env-file` for these commands, with
`MYSQL_DATABASE=dynaprotdbv2` and reference-table write privileges. The scoped
importer credentials intentionally cannot populate reference tables.

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
