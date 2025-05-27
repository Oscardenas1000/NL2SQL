# nl2sql_app.py

"""
Streamlit app for Natural Language to SQL conversion.

Before running, install required packages in your `streamlit-env` with:

pip install streamlit mysql-connector-python pandas seaborn matplotlib
"""

import streamlit as st
import re
import mysql.connector
import pandas as pd
import json
import matplotlib.pyplot as plt
import seaborn as sns

# --- Configuration (update as needed) ---
DB_HOST = "10.0.1.54"
DB_PORT = 3306
DB_USER = "admin"
DB_PASSWORD = "@Mysqlse2025"
DB_NAME = "airportdb"
# Schema context for information_schema queries
DBSYSTEM_SCHEMA = DB_NAME

MODEL_ID = "meta.llama-3.1-405b-instruct"
DEBUG = False

# --- Database Connection ---
def get_db_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        allow_local_infile=True,
        use_pure=True,
        autocommit=True
    )

# Initialize connection and cursor
conn = get_db_connection()
cursor = conn.cursor()

# Helper to execute SQL and return DataFrame
def execute_sql(sql: str) -> pd.DataFrame:
    if DEBUG:
        st.write(f"Executing SQL: {sql}")
    cursor.execute(sql)
    rows = cursor.fetchall()
    cols = cursor.column_names
    return pd.DataFrame(rows, columns=cols)

# --- Core Pipeline Functions ---

def extract_clean_sql(raw_response):
    # Remove quotes wrapper
    if raw_response.startswith("'") and raw_response.endswith("'"):
        raw_response = raw_response[1:-1]
    # Parse JSON if present
    try:
        parsed = json.loads(raw_response)
        text = parsed.get("text", "")
    except json.JSONDecodeError:
        text = raw_response
    # Unescape
    cleaned = text.replace('\\n', '\n').replace('\\', '').replace('\\"', '"').strip()
    # Strip markdown fences
    if cleaned.startswith('```sql'):
        cleaned = cleaned[6:]
    if cleaned.startswith('```'):
        cleaned = cleaned[3:]
    if cleaned.endswith('```'):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def translate_to_english(user_input, user_language, model_id=MODEL_ID):
    # Build translation prompt
    preamble = (
        f"You are a professional translator. Translate the following text into English,"
        f" keeping the meaning intact. The original language is '{user_language}'."
        " Return only the English translation without any additional explanations or markdown."
    )
    combined = f"{preamble.strip()}\n\n{user_input.strip()}"
    # Escape single quotes
    escaped = combined.replace("'", "\\'")
    # Call ML_GENERATE
    sql = f"""
    SELECT sys.ML_GENERATE(
        '{escaped}',
        JSON_OBJECT(
            'task','generation',
            'model_id','{model_id}',
            'language','en',
            'max_tokens',4000
        )
    ) AS response;
    """
    if DEBUG:
        print("Translating to English via ML_GENERATE...")
    cursor.execute(sql)
    res = cursor.fetchall()
    return extract_clean_sql(res[0][0])


def call_ml_generate(full_question, user_language='en', model_id=MODEL_ID):
    # Optional translation
    if user_language.lower() != 'en':
        question = translate_to_english(full_question, user_language=user_language, model_id=model_id)
    else:
        question = full_question
    # Build preamble with schema context
    preamble = (
        f"You are an expert in MySQL. Convert the following question into a SQL query that retrieves data "
        f"from the '{DBSYSTEM_SCHEMA}' database. The schema of '{DBSYSTEM_SCHEMA}' is provided as context. "
        "Avoid using information_schema or metadata queries. Return only the SQL query without explanations or markdown."
    )
    combined = f"{preamble.strip()}\n\n{question.strip()}"
    # Prepare escaped values
    escaped_question = combined.replace("'", "\\'")
    # Assemble schema context lines
    context_lines = [
        f"Table: {r['TABLE_NAME']}, Column: {r['COLUMN_NAME']}, Type: {r['COLUMN_TYPE']}, "
        f"Nullable: {r['IS_NULLABLE']}, Key: {r['COLUMN_KEY']}, Comment: {r['COLUMN_COMMENT']}"
        for _, r in db_schema_info.iterrows()
    ]
    context = "\n".join(context_lines)
    escaped_context = context.replace("'", "\\'")
    # Build ML_GENERATE SQL
    sql = f"""
    SELECT sys.ML_GENERATE(
        '{escaped_question}',
        JSON_OBJECT(
            'task','generation',
            'model_id','{model_id}',
            'language','en',
            'context','{escaped_context}',
            'max_tokens',4000
        )
    ) AS response;
    """
    if DEBUG:
        print("Generating SQL via ML_GENERATE with context...")
    cursor.execute(sql)
    result = cursor.fetchall()
    return result[0][0]


def run_generated_sql_with_repair(raw_response, translated_prompt, max_attempts=10):
    attempt = 0
    current = raw_response
    restricted = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE)\b", re.IGNORECASE)
    while attempt < max_attempts:
        attempt += 1
        sql_query = extract_clean_sql(current)
        if restricted.search(sql_query):
            return f"❌ Restricted operation detected: {sql_query}"
        try:
            parts = [q.strip() for q in sql_query.split(';') if q.strip()]
            results = []
            cols_set = set()
            for q in parts:
                cursor.execute(q)
                try:
                    rows = cursor.fetchall()
                    cols = tuple(cursor.column_names)
                    df = pd.DataFrame(rows, columns=cols)
                    results.append((cols, df))
                    cols_set.add(cols)
                except mysql.connector.errors.InterfaceError:
                    results.append((None, f"✅ Executed (no result): {q}"))
                while cursor.nextset():
                    pass
            dfs = [df for c, df in results if isinstance(df, pd.DataFrame)]
            if len(cols_set) == 1 and len(dfs) == len(parts):
                return pd.concat(dfs, ignore_index=True)
            return {f"Query {i+1}": df for i, (_, df) in enumerate(results)}
        except mysql.connector.Error as err:
            repair_prompt = (
                f"The original user intent was:\n{translated_prompt}\n"
                f"The generated SQL was:\n{sql_query}\n"
                f"Error:\n{err}\n"
                f"Regenerate a corrected SELECT-only query for '{DBSYSTEM_SCHEMA}' without metadata queries."
            )
            current = call_ml_generate(repair_prompt)
    return "❌ Failed to generate valid SQL after retries."


def generate_natural_language_answer(user_prompt, final_result, user_language, model_id=MODEL_ID):
    if isinstance(final_result, pd.DataFrame):
        context_text = final_result.to_string(index=False)
    elif isinstance(final_result, dict):
        parts = [f"{label}:\n{df.to_string(index=False)}" for label, df in final_result.items()]
        context_text = "\n\n".join(parts)
    else:
        context_text = str(final_result)
    # Escape for SQL
    user_esc = user_prompt.replace("'", "\\'")
    context_esc = context_text.replace("'", "\\'")
    sql = f"""
    SELECT sys.ML_GENERATE(
        'Respond to the following question: {user_esc} making use of the context provided',
        JSON_OBJECT(
            'task','generation',
            'model_id','{model_id}',
            'language','{user_language}',
            'context','{context_esc}',
            'max_tokens',4000
        )
    ) AS response;
    """
    if DEBUG:
        print("Generating natural language answer via ML_GENERATE...")
    cursor.execute(sql)
    resp = cursor.fetchall()[0][0]
    return extract_clean_sql(resp)


def full_pipeline(user_question, user_language, model_id=MODEL_ID, schema_info=None):
    # 1. Translate if needed
    if user_language.lower() != 'en':
        tq = translate_to_english(user_question, user_language=user_language, model_id=model_id)
    else:
        tq = user_question
    # 2. Generate SQL
    sql_resp = call_ml_generate(tq, user_language, model_id)
    # 3. Execute with repair
    final = run_generated_sql_with_repair(sql_resp, translated_prompt=tq)
    # 4. Count rows
    if isinstance(final, pd.DataFrame):
        n = len(final)
    elif isinstance(final, dict):
        n = sum(len(df) for df in final.values() if isinstance(df, pd.DataFrame))
    else:
        n = 0
    if DEBUG:
        print(f"Result rows: {n}")
    # 5. Return
    if n > 24:
        return final
    return generate_natural_language_answer(tq, final, user_language, model_id)

# --- Schema Extraction for Context ---
schema_query = f"""
SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_COMMENT
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = '{DBSYSTEM_SCHEMA}'
ORDER BY TABLE_NAME, ORDINAL_POSITION;
"""
db_schema_info = execute_sql(schema_query)

# --- Streamlit App UI ---
def main():
    st.title("Natural Language → SQL Explorer")
    st.write("Ask questions in natural language and retrieve SQL results.")
    question = st.text_input("Your question:")
    language = st.selectbox("Language:", ["en", "es", "pt", "fr"], index=1)
    if st.button("Run Query"):
        if not question:
            st.warning("Enter a question before running.")
        else:
            with st.spinner("Running..."):
                output = full_pipeline(question, language, model_id=MODEL_ID)
                if isinstance(output, pd.DataFrame):
                    st.dataframe(output)
                elif isinstance(output, dict):
                    for lbl, df in output.items():
                        st.subheader(lbl)
                        st.dataframe(df)
                else:
                    st.write(output)

if __name__ == "__main__":
    main()
