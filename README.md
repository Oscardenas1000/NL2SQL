# NL2SQL

This repository contains a minimal Streamlit application for querying an
Oracle HeatWave instance using natural language. The app relies on a large
language model (LLM) to translate user prompts into SQL queries.

---

## Requirements

* Python 3.11
* `streamlit`
* `mysql-connector-python`

Install the dependencies using:

```bash
pip install -r requirements.txt
```

---

## Environment Variables

The app expects the following environment variables to be defined:

* `HW_HOST` – hostname of the HeatWave service
* `HW_DB_USER` – database user name
* `HW_DB_PASS` – database password
* `HW_DB_NAME` – database schema to use
* `MODEL_ID` – HeatWave GenAI Model ID

---

## Running the App

Start the Streamlit server with:

```bash
streamlit run nl2sql_app.py
```

Enter a natural language query, and the app will display the generated SQL
statement and the query results from HeatWave.

---

## Example Usage

1. Edit the configuration variables at the top of `nl2sql_app.py` to match your HeatWave credentials.

2. Launch the app:

   ```bash
   streamlit run nl2sql_app.py
   ```

3. When the browser opens, type a question about your data, for example:

   ```text
   Which airlines operate flights from SFO to JFK?
   ```

The app will generate a SQL query, execute it, and display the results.
If the query returns fewer than 25 rows, a short natural language summary
is also shown.

---

## Database Requirements

The app works at the **database/schema** level.
It queries into the selected schema and pulls metadata like table names,
column names, column types, **and a required column comment** that explains
why each column is important.

---

### Example Table Definition

| TABLE\_NAME    | COLUMN\_NAME  | COLUMN\_TYPE       | COLUMN\_COMMENT                                                                                                    |
| -------------- | ------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------ |
| airline        | airline\_id   | smallint           | Unique identifier for each airline.                                                                                |
| airline        | iata          | char(2)            | Two-character IATA code assigned to the airline, used globally for identification.                                 |
| airline        | airlinename   | varchar(30)        | The full name of the airline.                                                                                      |
| airline        | base\_airport | smallint           | ID of the base airport for the airline, referring to the primary operational hub.                                  |
| airplane       | airplane\_id  | int                | Unique identifier for each airplane. This is the primary key and is auto-incremented.                              |
| airplane       | capacity      | mediumint unsigned | Maximum number of passengers that the airplane can accommodate.                                                    |
| airplane       | type\_id      | int                | Identifier for the airplane model/type. This is a foreign key referencing the airplane\_type table.                |
| airplane       | airline\_id   | int                | Identifier of the airline that owns or operates the airplane. This is a foreign key referencing the airline table. |
| airplane\_type | type\_id      | int                | Unique identifier for each airplane type or model.                                                                 |
| airplane\_type | identifier    | varchar(50)        | Model identifier or code for the airplane type.                                                                    |
| airplane\_type | description   | text               | Additional details or specifications about the airplane type.                                                      |
| airport        | airport\_id   | smallint           | Unique identifier for each airport.                                                                                |

---

## How to Add Column Comments in MySQL

If your table doesn’t have column comments yet, follow these steps.

---

### 1️⃣ Check Your Table

Check the current structure and see which columns lack comments:

```sql
SHOW FULL COLUMNS FROM your_table_name;
```

This will display a `Comment` column at the end.

---

### 2️⃣ Add Comments to Existing Columns

In MySQL, you **must** modify the column definition to add a comment.
You cannot just attach a comment separately.

Use this syntax:

```sql
ALTER TABLE your_table_name
MODIFY COLUMN column_name column_definition COMMENT 'Your comment here';
```

⚠️ **Important**: You must re-specify the full column definition (type,
NULL/NOT NULL, keys, etc.) — otherwise MySQL will throw an error.

---

### Example

Given this table:

```sql
CREATE TABLE employees (
    employee_id INT PRIMARY KEY,
    name VARCHAR(100),
    hire_date DATE
);
```

To add comments:

* Add to `employee_id`:

  ```sql
  ALTER TABLE employees
  MODIFY COLUMN employee_id INT PRIMARY KEY COMMENT 'Unique identifier for each employee';
  ```

* Add to `name`:

  ```sql
  ALTER TABLE employees
  MODIFY COLUMN name VARCHAR(100) COMMENT 'Full name of the employee';
  ```

* Add to `hire_date`:

  ```sql
  ALTER TABLE employees
  MODIFY COLUMN hire_date DATE COMMENT 'The date the employee was hired';
  ```

---

### 3️⃣ Verify the Changes

Run:

```sql
SHOW FULL COLUMNS FROM employees;
```

You should now see your comments listed.

