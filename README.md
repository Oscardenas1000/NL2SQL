# NL2SQL

This repository contains a minimal Streamlit application for querying an
Oracle HeatWave instance using natural language. The app relies on a
language model to translate user prompts into SQL queries.

## Requirements

* Python 3.11
* `streamlit`
* `mysql-connector-python`
* `openai`

Install the dependencies using:

```bash
pip install -r requirements.txt
```

## Environment variables

The app expects the following variables to be defined:

- `HW_HOST` – hostname of the MySQL HeatWave service
- `HW_DB_USER` – database user name
- `HW_DB_PASS` – database password
- `HW_DB_NAME` – database schema to use
- `OPENAI_API_KEY` – API key for the language model service
- `OPENAI_MODEL` (optional) – model name, default is `gpt-4`

## Running the app

Start the Streamlit server with:

```bash
streamlit run nl2sql_app.py
```

Enter a natural language query and the app will display the generated SQL
statement and query results from HeatWave.
