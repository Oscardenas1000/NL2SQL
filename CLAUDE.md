# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
streamlit run nl2sql_app.py
```

The app runs on port `8501`. On RHEL/OCI VMs, `setup.sh` handles Python 3.11 installation and firewall configuration.

## Installing Dependencies

```bash
pip install -r requirements.txt
```

Key pinned dependency: `mysql-connector-python==9.3.0`.

## Architecture

This is a single-file Streamlit app (`nl2sql_app.py`) that wraps Oracle HeatWave's built-in NL→SQL stored procedure.

### Connection Model

Each query opens a fresh MySQL connection (`get_db_connection`) and closes it immediately after — there is no connection pooling. This is intentional for concurrency correctness in Streamlit's multi-threaded execution model.

### Core Pipeline (`full_pipeline`)

1. **`run_nl_sql`** — calls `sys.NL_SQL(...)` stored procedure with `verbose=1` to get both the generated SQL and tabular results. Parses the `nl_sql_info` result set (JSON stream) to extract the validated SQL from the `stage=validated_sql` entry.
2. **`generate_natural_language_answer`** — calls `sys.ML_GENERATE(...)` to convert small result sets (≤ `max_nl_lines` rows) into a natural language response in the user's selected language.
3. **`full_pipeline`** — orchestrates both steps, with logic to skip NL generation for `restricted_models` (HeatWave-native models) unless the user explicitly overrides via the sidebar checkbox.

### Model Discovery

Model options are dynamically loaded from `sys.ML_SUPPORTED_LLMS` at sidebar render time via `refresh_model_catalog()`. The default model is whichever row has `default_model=1`.

### Configuration

Database credentials are hardcoded at the top of `nl2sql_app.py` (`DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`). The `oci_cli_setup.sh` script automates patching these values via `sed` during deployment by fetching the HeatWave instance IP from OCI CLI.

The `DBSYSTEM_SCHEMA` global is updated at runtime when the user switches schemas from the sidebar.

## Deployment (OCI/RHEL)

1. Run `./setup.sh` — installs Python 3.11 from source, pip dependencies, and opens firewall port 8501.
2. Run `./oci_cli_setup.sh` — configures OCI CLI, retrieves HeatWave endpoint via `oci mysql db-system get`, and patches `nl2sql_app.py` with the correct `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`.

## HeatWave Schema Requirement

`sys.NL_SQL` uses column comments as semantic context. Every column in the target schema should have a descriptive `COMMENT` clause. Without comments, SQL generation quality degrades significantly. Use `SHOW FULL COLUMNS FROM <table>` to verify.
