# NL2SQL

This repository contains a minimal Streamlit application for querying an
Oracle HeatWave instance using natural language. The app relies on a large 
language model to translate user prompts into SQL queries.

## Requirements

* Python 3.11
* `streamlit`
* `mysql-connector-python`

Install the dependencies using:

```bash
pip install -r requirements.txt
```

## Environment variables

The app expects the following variables to be defined:

- `HW_HOST` – hostname of the HeatWave service
- `HW_DB_USER` – database user name
- `HW_DB_PASS` – database password
- `HW_DB_NAME` – database schema to use
- `MODEL_ID` - HeatWave GenAI Model ID

## Running the app

Start the Streamlit server with:

```bash
streamlit run nl2sql_app.py
```

Enter a natural language query and the app will display the generated SQL
statement and query results from HeatWave.


## Example usage

1. Edit the configuration variables at the top of `nl2sql_app.py` to match your HeatWave credentials.
2. Launch the app:

```bash
streamlit run nl2sql_app.py
```

3. When the browser opens, type a question about your data, e.g.:

```text
Which airlines operate flights from SFO to JFK?
```

The app will generate a SQL query for your question, execute it and display the results. If the query returns fewer than 25 rows, a short natural language summary is also shown.
