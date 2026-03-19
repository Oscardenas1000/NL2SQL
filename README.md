# NL2SQL
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

This repository contains a Streamlit app for querying an Oracle HeatWave instance with natural language. The app supports three modes:

- `Auto`: routes each prompt through `demo.smart_ask` when the router bundle is available
- `Chat`: uses `sys.ML_GENERATE` for conversational responses with memory
- `SQL`: uses `sys.NL_SQL` to generate and execute SQL against selected schemas

The app also supports optional result explanations, schema scoping, and thumbs up/down feedback for router outputs.

---

## Requirements

### Network

- The VCN should include at least one public subnet and one private subnet.
- The HeatWave database must be reachable from the app host on the configured MySQL port.
- The app is served on port `8501`, so that port must be open to the browser clients that need access.

### Host

- RHEL 8 or newer is recommended for the bootstrap scripts.
- The app host must be able to reach the HeatWave instance and, if you use the setup scripts, the internet for package installation.

---

## Setup

### Install dependencies

From the repository root:

```bash
pip install -r requirements.txt
```

### Optional OS bootstrap

The `setup.sh` script is intended for RHEL / Oracle Linux hosts. It installs the basic Python and Streamlit runtime, then opens port `8501` in `firewalld`.

```bash
chmod +x setup.sh
./setup.sh
```

### Optional OCI CLI helper

The `oci_cli_setup.sh` helper assumes the OCI CLI is installed and available as `oci`. It bootstraps the local OCI config if needed, then walks through the HeatWave connection setup and writes the app connection settings to `.streamlit/secrets.toml` in the repository root.

```bash
chmod +x oci_cli_setup.sh
./oci_cli_setup.sh
```

If you use the OCI helper, follow Oracle's API key documentation:
[Signing Requests with API Key](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/apisigningkey.htm#How2)

---

## Configuration

The app reads connection settings from environment variables first and falls back to Streamlit secrets when available. If you use `oci_cli_setup.sh`, it writes the database keys below to `.streamlit/secrets.toml`.

Required database variables:

- `DB_HOST` - HeatWave host name or IP address
- `DB_PORT` - MySQL port, usually `3306`
- `DB_USER` - database user name
- `DB_PASSWORD` - database password
- `DB_NAME` - default schema name

Optional model preset overrides:

- `MODEL_PRESET_SMALL`
- `MODEL_PRESET_MEDIUM`
- `MODEL_PRESET_LARGE`

If the model preset variables are unset, the app uses built-in defaults and resolves them against `sys.ML_SUPPORTED_LLMS` in the database catalog.

---

## Run

Start the app with:

```bash
streamlit run nl2sql_app.py
```

The sidebar loads available models from `sys.ML_SUPPORTED_LLMS`, lets you choose a model preset or catalog entry, and lets you pick one or more schemas for `SQL` inference.

---

## Runtime Behavior

- `Auto` mode routes database-oriented prompts through `demo.smart_ask` when the router bundle is available, and falls back to `Chat` for conversational input or when the router objects are unavailable.
- `Chat` mode sends the conversation history to `sys.ML_GENERATE`.
- `SQL` mode sends the prompt to `sys.NL_SQL` and renders the result table when one is returned.
- If `Explain result in natural language` is enabled, the app explains small SQL result sets with `sys.ML_GENERATE`.
- When `Show generated SQL?` is enabled, the UI prints the generated SQL below the result.
- The router bundle in `sql/router/` creates the `demo` schema objects used for caching, route metrics, schema hints, and feedback.

The current flow is summarized in [docs/app_flowchart.md](/Users/oscarden/Desktop/AutoML/NL2SQL/docs/app_flowchart.md) and illustrated by [resources/diagram.svg](/Users/oscarden/Desktop/AutoML/NL2SQL/resources/diagram.svg).

---

## Database Requirements

The app works at the database/schema level. It queries the selected schema and uses table and column metadata, including column comments, to improve SQL generation.

If your schema does not already include useful comments, add them before using `SQL` mode. The app is much more reliable when columns have concise descriptions.

### Example table definition

| TABLE_NAME | COLUMN_NAME | COLUMN_TYPE | COLUMN_COMMENT |
| --- | --- | --- | --- |
| airline | airline_id | smallint | Unique identifier for each airline. |
| airline | iata | char(2) | Two-character IATA code assigned to the airline. |
| airline | airlinename | varchar(30) | The full name of the airline. |

### Adding column comments

```sql
ALTER TABLE your_table_name
MODIFY COLUMN column_name column_definition COMMENT 'Your comment here';
```

Use `SHOW FULL COLUMNS FROM your_table_name;` to verify the comments.

---

## License

This project is licensed under the MIT License. See [LICENSE](/Users/oscarden/Desktop/AutoML/NL2SQL/LICENSE) for details.
