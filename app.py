import os
import json
import re

import pandas as pd
import mysql.connector
import sshtunnel
import streamlit as st

# Read connection settings from environment variables
BASTION_IP = os.getenv("BASTION_IP")
BASTION_USER = os.getenv("BASTION_USER")
BASTION_KEY = os.getenv("BASTION_KEY")
DBSYSTEM_IP = os.getenv("DBSYSTEM_IP")
DBSYSTEM_USER = os.getenv("DBSYSTEM_USER")
DBSYSTEM_PASSWORD = os.getenv("DBSYSTEM_PASSWORD")
DBSYSTEM_SCHEMA = os.getenv("DBSYSTEM_SCHEMA")
MODEL_ID = os.getenv("MODEL_ID", "meta.llama-3.1-405b-instruct")
DEBUG = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")


@st.cache_resource(show_spinner=False)
def get_connection():
    """Create the SSH tunnel and database connection."""
    if not all([BASTION_IP, BASTION_USER, BASTION_KEY, DBSYSTEM_IP, DBSYSTEM_USER, DBSYSTEM_PASSWORD, DBSYSTEM_SCHEMA]):
        raise RuntimeError("Missing database connection environment variables")

    tunnel = sshtunnel.SSHTunnelForwarder(
        (BASTION_IP, 22),
        ssh_username=BASTION_USER,
        ssh_pkey=BASTION_KEY,
        remote_bind_address=(DBSYSTEM_IP, 3306),
    )
    tunnel.start()

    conn = mysql.connector.connect(
        host="127.0.0.1",
        port=tunnel.local_bind_port,
        user=DBSYSTEM_USER,
        password=DBSYSTEM_PASSWORD,
        database=DBSYSTEM_SCHEMA,
        allow_local_infile=True,
        use_pure=True,
        autocommit=True,
    )
    cursor = conn.cursor()
    return tunnel, conn, cursor


def execute_sql(cursor, sql):
    """Run a SQL query and return the result as a pandas DataFrame."""
    if DEBUG:
        st.write(f"Running SQL:\n{sql}")
    cursor.execute(sql)
    return pd.DataFrame(cursor.fetchall(), columns=cursor.column_names)


@st.cache_data(show_spinner=False)
def load_schema_info(cursor):
    query = f"""
    SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_COMMENT
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = '{DBSYSTEM_SCHEMA}'
    ORDER BY TABLE_NAME, ORDINAL_POSITION;
    """
    return execute_sql(cursor, query)


def extract_clean_sql(raw_response: str) -> str:
    """Clean the raw SQL string returned by sys.ML_GENERATE."""
    if raw_response.startswith("'") and raw_response.endswith("'"):
        raw_response = raw_response[1:-1]
    try:
        parsed = json.loads(raw_response)
        text = parsed.get("text", "")
    except json.JSONDecodeError:
        text = raw_response
    cleaned = (
        text.replace("\\n", "\n")
        .replace("\\", "")
        .replace('\"', '"')
        .strip()
    )
    if cleaned.startswith("```sql"):
        cleaned = cleaned[6:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def translate_to_english(cursor, user_input: str, user_language: str, model_id: str = MODEL_ID) -> str:
    preamble = (
        f"You are a professional translator. Translate the following text into English, "
        f"keeping the meaning intact. The original language is '{user_language}'. "
        "Return only the English translation without any additional explanations or markdown."
    )
    combined_question = f"{preamble.strip()}\n\n{user_input.strip()}"
    combined_question_escaped = combined_question.replace("'", "\\'")
    sql = f"""
    SELECT sys.ML_GENERATE(
        '{combined_question_escaped}',
        JSON_OBJECT(
            'task', 'generation',
            'model_id', '{model_id}',
            'language', 'en',
            'max_tokens', 4000
        )
    ) AS response;
    """
    cursor.execute(sql)
    result = cursor.fetchall()
    translated_text = result[0][0]
    return extract_clean_sql(translated_text)


def call_ml_generate(cursor, db_schema_info, full_question: str, user_language: str = "en", model_id: str = MODEL_ID) -> str:
    if user_language.lower() != "en":
        translated_question = translate_to_english(cursor, full_question, user_language=user_language)
    else:
        translated_question = full_question

    schema_name = DBSYSTEM_SCHEMA
    preamble = (
        f"You are an expert in MySQL. Convert the following question into a SQL query that retrieves data "
        f"from the '{schema_name}' database. The schema of '{schema_name}' is provided as context. "
        "Avoid using information_schema or metadata queries. Return only the SQL query without explanations or markdown."
    )
    combined_question = f"{preamble.strip()}\n\n{translated_question.strip()}"

    context_lines = [
        f"Table: {row['TABLE_NAME']}, Column: {row['COLUMN_NAME']}, Type: {row['COLUMN_TYPE']}, "
        f"Nullable: {row['IS_NULLABLE']}, Key: {row['COLUMN_KEY']}, Comment: {row['COLUMN_COMMENT']}"
        for _, row in db_schema_info.iterrows()
    ]
    context_text = "\n".join(context_lines)

    combined_question_escaped = combined_question.replace("'", "\\'")
    context_text_escaped = context_text.replace("'", "\\'")

    sql = f"""
    SELECT sys.ML_GENERATE(
        '{combined_question_escaped}',
        JSON_OBJECT(
            'task', 'generation',
            'model_id', '{model_id}',
            'language', 'en',
            'context', '{context_text_escaped}',
            'max_tokens', 4000
        )
    ) AS response;
    """
    cursor.execute(sql)
    result = cursor.fetchall()
    return result[0][0]


def run_generated_sql_with_repair(cursor, raw_response: str, translated_prompt: str, max_attempts: int = 10):
    attempt = 0
    current_response = raw_response
    restricted_patterns = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE)\b", re.IGNORECASE)

    while attempt < max_attempts:
        attempt += 1
        sql_query = extract_clean_sql(current_response).strip()

        if DEBUG:
            st.write(f"Attempt {attempt}: running SQL:\n{sql_query}")

        if restricted_patterns.search(sql_query):
            return f"❌ Restricted operation detected in SQL:\n{sql_query}"

        try:
            queries = [q.strip() for q in sql_query.split(';') if q.strip()]
            results = []
            columns_set = set()

            for q in queries:
                cursor.execute(q)
                try:
                    result = cursor.fetchall()
                    columns = tuple(cursor.column_names)
                    df = pd.DataFrame(result, columns=columns)
                    results.append((columns, df))
                    columns_set.add(columns)
                except mysql.connector.errors.InterfaceError:
                    results.append(("no_result", f"✅ Query executed successfully (no result set): {q}"))

                while cursor.nextset():
                    pass

            dataframes = [df for col, df in results if isinstance(df, pd.DataFrame)]
            if len(columns_set) == 1 and len(dataframes) == len(queries):
                return pd.concat(dataframes, ignore_index=True)
            else:
                return {f"Query {i+1}": df for i, (_, df) in enumerate(results)}

        except mysql.connector.Error as err:
            if DEBUG:
                st.write(f"❌ MySQL Error: {err}")
            repair_prompt = (
                f"The original user intent was:\n\n{translated_prompt}\n\n"
                f"The following SQL query was generated but caused an error:\n\n{sql_query}\n\n"
                f"The error message was:\n\n{str(err)}\n\n"
                f"Please regenerate a corrected SQL query that fulfills the user's original intent, "
                f"works against the '{DBSYSTEM_SCHEMA}' database, and only uses SELECT statements. "
                f"Do not include INSERT, UPDATE, DELETE, DROP, ALTER, or any other DDL/DML statements. "
                f"Return only the corrected SQL query without explanations or markdown formatting."
            )
            while cursor.nextset():
                pass
            current_response = call_ml_generate(cursor, db_schema_info, repair_prompt)

    return "❌ Failed to generate a valid, executable SQL query after multiple attempts."


def generate_natural_language_answer(cursor, user_prompt: str, final_result, user_language: str, model_id: str = MODEL_ID) -> str:
    if isinstance(final_result, pd.DataFrame):
        context_text = final_result.to_string(index=False)
    elif isinstance(final_result, dict):
        context_parts = []
        for label, df in final_result.items():
            context_parts.append(f"{label}:\n{df.to_string(index=False)}")
        context_text = "\n\n".join(context_parts)
    else:
        context_text = str(final_result)

    user_prompt_escaped = user_prompt.replace("'", "\\'")
    context_text_escaped = context_text.replace("'", "\\'")

    sql = f"""
    SELECT sys.ML_GENERATE(
        'Respond to the following question {user_prompt_escaped} making use of the context provided',
        JSON_OBJECT(
            'task', 'generation',
            'model_id', '{model_id}',
            'language', '{user_language}',
            'context', '{context_text_escaped}',
            'max_tokens', 4000
        )
    ) AS response;
    """
    cursor.execute(sql)
    result = cursor.fetchall()
    natural_language_response = result[0][0]
    return extract_clean_sql(natural_language_response)


def full_pipeline(cursor, db_schema_info, user_question: str, user_language: str, model_id: str = MODEL_ID):
    if user_language.lower() != 'en':
        translated_question = translate_to_english(cursor, user_question, user_language=user_language, model_id=model_id)
    else:
        translated_question = user_question

    response = call_ml_generate(cursor, db_schema_info, translated_question, model_id=model_id)
    final_result = run_generated_sql_with_repair(cursor, response, translated_prompt=translated_question)

    if isinstance(final_result, pd.DataFrame):
        num_rows = len(final_result)
    elif isinstance(final_result, dict):
        num_rows = sum(len(df) for df in final_result.values() if isinstance(df, pd.DataFrame))
    else:
        num_rows = 0

    if num_rows > 24:
        return final_result
    else:
        return generate_natural_language_answer(cursor, translated_question, final_result, user_language=user_language, model_id=model_id)


# --- Streamlit UI ---

st.title("GenAI Chatbot - HeatWave")

try:
    tunnel, conn, cursor = get_connection()
    schema_info = load_schema_info(cursor)
    version_df = execute_sql(cursor, "SELECT version()")
    st.sidebar.success(f"Connected to DB, version: {version_df.iloc[0,0]}")
except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.stop()

question = st.text_area("Enter your question")
user_language = st.text_input("Language code", value="en")

if st.button("Run"):
    if not question:
        st.warning("Please enter a question")
    else:
        with st.spinner("Processing..."):
            result = full_pipeline(cursor, schema_info, question, user_language)
        if isinstance(result, pd.DataFrame):
            st.dataframe(result)
        elif isinstance(result, dict):
            for label, df in result.items():
                st.subheader(label)
                if isinstance(df, pd.DataFrame):
                    st.dataframe(df)
                else:
                    st.write(df)
        else:
            st.write(result)
