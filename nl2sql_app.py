import os
import streamlit as st
import mysql.connector

try:
    import openai
except ImportError:
    openai = None


def convert_nl_to_sql(prompt: str) -> str:
    """Convert a natural language prompt to SQL using OpenAI."""
    if openai is None:
        raise RuntimeError("openai package is not installed")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    openai.api_key = api_key
    model = os.getenv("OPENAI_MODEL", "gpt-4")

    messages = [
        {
            "role": "system",
            "content": "Convert the user's natural language request into a SQL query without commentary.",
        },
        {"role": "user", "content": prompt},
    ]

    response = openai.ChatCompletion.create(model=model, messages=messages)
    sql = response["choices"][0]["message"]["content"].strip()
    return sql


def run_query(sql: str):
    """Execute a SQL query against HeatWave."""
    conn = mysql.connector.connect(
        user=os.getenv("HW_DB_USER"),
        password=os.getenv("HW_DB_PASS"),
        host=os.getenv("HW_HOST"),
        database=os.getenv("HW_DB_NAME"),
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute(sql)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results


st.title("NL2SQL with HeatWave")

prompt = st.text_input("Enter a natural language query")

if st.button("Run"):
    if not prompt:
        st.warning("Please enter a query")
    else:
        try:
            sql = convert_nl_to_sql(prompt)
            st.code(sql, language="sql")
            data = run_query(sql)
            st.write(data)
        except Exception as e:
            st.error(str(e))
