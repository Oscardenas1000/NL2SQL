import streamlit as st
import re
import mysql.connector
import pandas as pd
import json

# --- Configuration ---
DB_HOST = "10.0.1.54" # Database Host, Auto-populated variable
DB_PORT = 3306 # Database port, Auto-populated variable
DB_USER = "admin" # Database user, Auto-populated variable
DB_PASSWORD = "@Mysqlse2025" # Database user password, Auto-populated variable
DB_NAME = "airportdb" # Target schema, Auto-populated variable
DBSYSTEM_SCHEMA = DB_NAME 

default_model = "meta.llama-3.1-405b-instruct"
MODEL_OPTIONS = [
    "meta.llama-3.1-405b-instruct",
    "meta.llama-3.2-90b-vision-instruct",
    "meta.llama-3.3-70b-instruct",
    "cohere.command-r-plus-08-2024",
    "cohere.command-r-08-2024",
    "llama3.1-8b-instruct-v1",
    "llama3.2-1b-instruct-v1",
    "llama3.2-3b-instruct-v1",
    "mistral-7b-instruct-v3"
]
restricted_models = [
    "llama3.1-8b-instruct-v1",
    "llama3.2-1b-instruct-v1",
    "llama3.2-3b-instruct-v1",
    "mistral-7b-instruct-v3"
]

DEBUG = False

@st.cache_resource
def get_db_connection():
    conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        allow_local_infile=True,
        use_pure=True,
        autocommit=True
    )
    return conn

def get_safe_cursor():
    conn = get_db_connection()
    if not conn.is_connected():
        conn.reconnect(attempts=3, delay=2)
    return conn.cursor()

def execute_sql(sql: str) -> pd.DataFrame:
    cursor = get_safe_cursor()
    if DEBUG:
        st.write(f"Executing SQL: {sql}")
    cursor.execute(sql)
    rows = cursor.fetchall()
    cols = cursor.column_names
    return pd.DataFrame(rows, columns=cols)

def extract_clean_sql(raw_response):
    if raw_response.startswith("'") and raw_response.endswith("'"):
        raw_response = raw_response[1:-1]
    try:
        parsed = json.loads(raw_response)
        text = parsed.get("text", "")
    except json.JSONDecodeError:
        text = raw_response
    cleaned = text.replace('\\n', '\n').replace('\\', '').replace('\\"', '"').strip()
    for fence in ('```sql', '```'):
        if cleaned.startswith(fence):
            cleaned = cleaned[len(fence):]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
    return cleaned.strip()

def translate_to_english(user_input, user_language, model_id):
    cursor = get_safe_cursor()
    prompt = f"You are a professional translator. Translate the following text into English, keeping meaning intact. Original language: {user_language}. Return only the translation without explanations or markdown."
    text = f"{prompt}\n\n{user_input.strip()}".replace("'", "\\'")
    sql = f"SELECT sys.ML_GENERATE('{text}', JSON_OBJECT('task','generation','model_id','{model_id}','language','en','max_tokens',4000)) AS response;"
    cursor.execute(sql)
    return extract_clean_sql(cursor.fetchall()[0][0])

def call_ml_generate(question_text, user_language, model_id):
    cursor = get_safe_cursor()
    if user_language.lower() != 'en':
        question_text = translate_to_english(question_text, user_language, model_id)
    prompt = f"You are an expert in MySQL. Convert this into a SQL query for '{DBSYSTEM_SCHEMA}'. Return only the SQL without markdown."
    escaped = f"{prompt}\n\n{question_text}".replace("'", "\\'")
    schema_q = f"SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='{DBSYSTEM_SCHEMA}' ORDER BY TABLE_NAME, ORDINAL_POSITION;"
    df_schema = execute_sql(schema_q)
    context = '\\n'.join(f"Table: {row.TABLE_NAME}, Column: {row.COLUMN_NAME}, Type: {row.COLUMN_TYPE}, Nullable: {row.IS_NULLABLE}, Key: {row.COLUMN_KEY}" for _, row in df_schema.iterrows()).replace("'", "\\'")
    sql = f"SELECT sys.ML_GENERATE('{escaped}', JSON_OBJECT('task','generation','model_id','{model_id}','language','en','context','{context}','max_tokens',4000)) AS response;"
    cursor.execute(sql)
    return cursor.fetchall()[0][0]

def run_generated_sql_with_repair(raw_sql_resp, original_intent, model_id, max_attempts=3):
    cursor = get_db_connection().cursor()
    restricted = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE)\b", re.IGNORECASE)
    current = raw_sql_resp
    for _ in range(max_attempts):
        sql_query = extract_clean_sql(current)
        if restricted.search(sql_query):
            return f"❌ Restricted operation: {sql_query}", sql_query
        try:
            cursor.execute(sql_query)
            dfs = []
            while True:
                try:
                    rows = cursor.fetchall()
                    cols = cursor.column_names
                    dfs.append(pd.DataFrame(rows, columns=cols))
                except Exception:
                    pass
                if not cursor.nextset():
                    break
            if not dfs:
                return f"✅ Executed (no result): {sql_query}", sql_query
            if len(dfs) == 1:
                return dfs[0], sql_query
            return pd.concat(dfs, ignore_index=True), sql_query
        except mysql.connector.Error as err:
            repair_prompt = (
                f"Original intent:\n{original_intent}\n"
                f"SQL query error:\n{sql_query}\n"
                f"Error: {err}\n"
                "Please regenerate a corrected SELECT-only query."
            )
            current = call_ml_generate(repair_prompt, 'en', model_id)
    return "❌ Failed to produce valid SQL after retries.", ""

def generate_natural_language_answer(user_question, final_df, user_language, model_id):
    cursor = get_safe_cursor()
    text_context = final_df.to_string(index=False) if isinstance(final_df, pd.DataFrame) else str(final_df)
    prompt = f"Respond to: {user_question}\nUsing context:\n{text_context}".replace("'", "\\'")
    sql = f"SELECT sys.ML_GENERATE('{prompt}', JSON_OBJECT('task','generation','model_id','{model_id}','language','{user_language}','max_tokens',4000)) AS response;"
    cursor.execute(sql)
    return extract_clean_sql(cursor.fetchall()[0][0])

def full_pipeline(user_question, user_language, model_id, use_nl, max_nl_lines):
    raw_resp = call_ml_generate(user_question, user_language, model_id)
    final_result, generated_sql = run_generated_sql_with_repair(raw_resp, user_question, model_id)
    n = len(final_result) if isinstance(final_result, pd.DataFrame) else 0
    if model_id in restricted_models:
        use_nl = False
    if use_nl and n <= max_nl_lines:
        answer = generate_natural_language_answer(user_question, final_result, user_language, model_id)
        return answer, generated_sql
    return final_result, generated_sql

def add_footer():
    st.markdown(
        """
        <style>
        /* Push the chat-input bar up so we have space for the footer */
        [data-testid="stChatInput"] {
            bottom: 60px !important;
        }

        /* The actual footer */
        #fixed-footer {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            width: 100%;
            background: #f9f9f9;
            padding: 10px;
            font-size: 12px;
            color: gray;
            text-align: center;
            border-top: 1px solid #e0e0e0;
            z-index: 10000;
        }
        </style>

        <div id="fixed-footer">
            This chatbot can make mistakes; none of the models use this data for training.
        </div>
        """,
        unsafe_allow_html=True
    )

# --- Streamlit App UI ---
def main():
    st.title("Natural Language → SQL Chatbot") # title can be modified
    if 'messages' not in st.session_state:
        st.session_state.messages = []

    with st.sidebar:
        model_id = st.selectbox("Model List:", MODEL_OPTIONS, index=MODEL_OPTIONS.index(default_model))
        nl_disabled = model_id in restricted_models
        use_nl = st.checkbox("Natural Language Response", value=not nl_disabled, disabled=nl_disabled)
        max_nl = st.number_input("NL Response Threshold:", min_value=1, value=24, disabled=not use_nl)
        language = st.selectbox("Language:", ["en", "es", "pt", "fr"], index=0)
        show_sql = st.radio("Show generated SQL?", ["No", "Yes"], index=0)

    for msg in st.session_state.messages:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'])

    if prompt := st.chat_input("Ask your question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Running query..."):
                output, generated_sql = full_pipeline(prompt, language, model_id, use_nl, max_nl)
                if isinstance(output, pd.DataFrame):
                    st.dataframe(output)
                    display_output = "✅ Returned a data table."
                else:
                    st.markdown(output)
                    display_output = output
                if show_sql == "Yes" and generated_sql:
                    st.sidebar.markdown("### Generated SQL")
                    st.sidebar.code(generated_sql, language='sql')
        st.session_state.messages.append({"role": "assistant", "content": display_output})

    #fixed footer text
    add_footer()

if __name__ == "__main__":
    main()
