import streamlit as st
import re
import mysql.connector
import pandas as pd
import json

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

DB_HOST = "10.0.1.54"   # Database Host
DB_PORT = 3306          # Database port
DB_USER = "admin"       # Database user
DB_PASSWORD = "@Mysqlse2025"  # Database password
DB_NAME = "airportdb"   # Default target schema
DBSYSTEM_SCHEMA = DB_NAME
HISTORY_SCHEMA = "history"
# -----------------------------------------------------------------------------
# Model Configuration
# -----------------------------------------------------------------------------

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

# -----------------------------------------------------------------------------
# History Functions
# -----------------------------------------------------------------------------

def insert_into_history(question, query):
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=HISTORY_SCHEMA
        )
        cursor = conn.cursor()
        cursor.execute("INSERT INTO history (question, query) VALUES (%s, %s)", (question, query))
        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        st.error(f"[History] Insert error: {err}")

def fetch_history():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=HISTORY_SCHEMA
        )
        df = pd.read_sql("SELECT question FROM history ORDER BY id DESC LIMIT 20", conn)
        conn.close()
        return df
    except mysql.connector.Error as err:
        st.error(f"[History] Fetch error: {err}")
        return pd.DataFrame()

def clear_history():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=HISTORY_SCHEMA
        )
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE history")
        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        st.error(f"[History] Clear error: {err}")


# -----------------------------------------------------------------------------
# DB helpers – each call opens/closes its own connection for concurrency
# -----------------------------------------------------------------------------

def get_db_connection():
    """Open a brand-new connection on each call (drop cached connection to allow concurrency)."""
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        ssl_disabled=False,
        use_pure=True
    )

def get_safe_cursor():
    """Return a fresh cursor and its connection for each query."""
    conn = get_db_connection()
    return conn.cursor(), conn

def execute_sql(sql: str) -> pd.DataFrame:
    """
    Execute a SQL query using a new cursor/connection per call,
    ensuring resources are closed promptly.
    """
    cursor, conn = get_safe_cursor()
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        cols = cursor.column_names
        return pd.DataFrame(rows, columns=cols)
    finally:
        cursor.close()
        conn.close()

# -----------------------------------------------------------------------------
# LLM / text helpers
# -----------------------------------------------------------------------------

def extract_clean_sql(raw_response: str) -> str:
    """Clean up the raw LLM response to extract pure SQL."""
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

def translate_to_english(user_input: str, user_language: str, model_id: str) -> str:
    """Use the ML model to translate text into English."""
    cursor, conn = get_safe_cursor()
    try:
        prompt = (
            f"You are a professional translator. Translate the following text into English, "
            f"keeping meaning intact. Original language: {user_language}. "
            "Return only the translation without explanations or markdown."
        )
        text = f"{prompt}\n\n{user_input.strip()}".replace("'", "\\'")
        sql = (
            f"SELECT sys.ML_GENERATE('{text}', "
            f"JSON_OBJECT('task','generation','model_id','{model_id}','language','en','max_tokens',4000)) "
            "AS response;"
        )
        cursor.execute(sql)
        return extract_clean_sql(cursor.fetchall()[0][0])
    finally:
        cursor.close()
        conn.close()

def call_ml_generate(question_text: str, user_language: str, model_id: str) -> str:
    """Ask the ML model to generate a SQL query based on natural language."""
    if user_language.lower() != 'en':
        question_text = translate_to_english(question_text, user_language, model_id)

    # Build prompt
    prompt = (
        f"You are an expert in MySQL. Convert this into a SQL query for '{DBSYSTEM_SCHEMA}'. "
	"Use ONLY unqualified table names (no schema prefixes). "
        "Return only the SQL without markdown."
    )
    escaped = f"{prompt}\n\n{question_text}".replace("'", "\\'")

    # Gather schema context
    schema_q = (
        f"SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_COMMENT "
        f"FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='{DBSYSTEM_SCHEMA}' "
        "ORDER BY TABLE_NAME, ORDINAL_POSITION;"
    )
    df_schema = execute_sql(schema_q)
    context = '\n'.join(
        f"Table: {row.TABLE_NAME}, Column: {row.COLUMN_NAME}, Type: {row.COLUMN_TYPE}, "
        f"Nullable: {row.IS_NULLABLE}, Key: {row.COLUMN_KEY}, Context: {row.COLUMN_COMMENT}"
        for _, row in df_schema.iterrows()
    ).replace("'", "\\'")

    # Call the model
    cursor, conn = get_safe_cursor()
    try:
        sql = (
            f"SELECT sys.ML_GENERATE('{escaped}', "
            f"JSON_OBJECT('task','generation','model_id','{model_id}','language','en',"
            f"'context','{context}','max_tokens',4000)) AS response;"
        )
        cursor.execute(sql)
        return cursor.fetchall()[0][0]
    finally:
        cursor.close()
        conn.close()

def run_generated_sql_with_repair(
    raw_sql_resp: str,
    original_intent: str,
    model_id: str,
    max_attempts: int = 3
):
    """
    Execute the generated SQL, retrying and repairing on errors,
    disallowing destructive commands.
    """
    restricted = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE)\b", re.IGNORECASE)
    current = raw_sql_resp

    for _ in range(max_attempts):
        sql_query = extract_clean_sql(current)
        if restricted.search(sql_query):
            return f"❌ Restricted operation: {sql_query}", sql_query

        cursor, conn = get_safe_cursor()
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
            # Repair on error
            repair_prompt = (
                f"Original intent:\n{original_intent}\n"
                f"SQL query error:\n{sql_query}\nError: {err}\n"
                "Please regenerate a corrected SELECT-only query."
            )
            current = call_ml_generate(repair_prompt, 'en', model_id)
        finally:
            cursor.close()
            conn.close()

    return "❌ Failed to produce valid SQL after retries.", ""

def generate_natural_language_answer(
    user_question: str,
    final_df,
    user_language: str,
    model_id: str
) -> str:
    """Turn a small result set into a natural-language answer."""
    cursor, conn = get_safe_cursor()
    try:
        text_context = final_df.to_string(index=False) if isinstance(final_df, pd.DataFrame) else str(final_df)
        prompt = (
            f"Respond to: {user_question}\nUsing context:\n{text_context}"
        ).replace("'", "\\'")
        sql = (
            f"SELECT sys.ML_GENERATE('{prompt}', "
            f"JSON_OBJECT('task','generation','model_id','{model_id}','language','{user_language}','max_tokens',4000)) "
            "AS response;"
        )
        cursor.execute(sql)
        return extract_clean_sql(cursor.fetchall()[0][0])
    finally:
        cursor.close()
        conn.close()

def full_pipeline(user_question, user_language, model_id,
                  use_nl, max_nl_lines, override_nl=False):              
    raw_resp = call_ml_generate(user_question, user_language, model_id)
    final_result, generated_sql = run_generated_sql_with_repair(
        raw_resp, user_question, model_id
    )

    if (model_id in restricted_models) and (not override_nl):
        use_nl = False

    n = len(final_result) if isinstance(final_result, pd.DataFrame) else 0

    if use_nl and n <= max_nl_lines:
        answer = generate_natural_language_answer(
            user_question, final_result, user_language, model_id
        )
        return answer, generated_sql

    return final_result, generated_sql

def add_footer():
    st.markdown(
        """
        <style>
        /* Default (desktop) */
          [data-testid='stChatInput'] { bottom: 50px !important; }

          /* Mobile: width less than 768px */
          @media (max-width: 767px) {
            [data-testid='stChatInput'] { bottom: 90px !important; }
          }

        #fixed-footer { position: fixed; bottom: 0; left: 0; right: 0; width: 100%; padding: 10px; font-size: 16px; color: gray; text-align: center; z-index: 10000; }
        </style>
        <div id="fixed-footer">
            This interface is for demonstrative purposes only. This is not a tool supported by Oracle.
        </div>
        """,
        unsafe_allow_html=True
    )

# -----------------------------------------------------------------------------
# Streamlit App UI
# -----------------------------------------------------------------------------

def main():
    #st.image("rnum.png", width=400)
    #st.title("RNUM Network Analyzer powered by HeatWave GenAI Bot")
    global DB_NAME, DBSYSTEM_SCHEMA

    st.title("Natural Language → SQL Chatbot")

    if 'messages' not in st.session_state:
        st.session_state.messages = []

    # 1) init history_list from DB on first run
    if 'history_list' not in st.session_state:
        st.session_state.history_list = fetch_history()['question'].tolist()

    with st.sidebar:
        # Schema selection menu (above model list)
        try:
            schemas_df = execute_sql("SHOW SCHEMAS;")
            schema_list = schemas_df[schemas_df.columns[0]].tolist()
        except Exception:
            schema_list = []
        selected_schema = st.selectbox(
            "Select database schema:", schema_list,
            index=schema_list.index(DB_NAME) if DB_NAME in schema_list else 0
        )
        DB_NAME = selected_schema
        DBSYSTEM_SCHEMA = selected_schema

        # Model controls
        model_id = st.selectbox("Model List:", MODEL_OPTIONS, index=MODEL_OPTIONS.index(default_model))

        # 1) detect the restricted models as before
        nl_disabled = model_id in restricted_models

        # 2) offer an override checkbox that’s only visible when the model is restricted
        override_nl = False
        if nl_disabled:
            override_nl = st.checkbox(
                "Force-enable NL even on restricted model", 
                value=False,
                help="Only use if you know what you’re doing"
            )

        # 3) compute whether the NL toggle should actually be disabled
        effective_disabled = nl_disabled and not override_nl

        # 4) the main NL checkbox uses that
        use_nl = st.checkbox(
            "Natural Language Response",
            value=not nl_disabled or override_nl,
            disabled=effective_disabled
        )

        # 5) threshold only enabled when use_nl is true
        max_nl = st.number_input(
            "NL Response Threshold:", 
            min_value=1, 
            value=24, 
            disabled=not use_nl
        )
        language = st.selectbox("Language:", ["en", "es", "pt", "fr"], index=0)
        show_sql = st.radio("Show generated SQL?", ["No", "Yes"], index=0)

        # 6) HISTORY
        st.markdown("---")
        st.subheader("History")

        history_df = fetch_history()   # now re-runs on every button click

        if not history_df.empty:
            for _, row in history_df.iterrows():
                st.markdown(f"- {row['question']}")
        else:
            st.info("No history yet.")

        # refresh button
        if st.button("🔄 Refresh History"):
            pass  # no-op; clicking it causes a rerun

        if st.button("🗑️ Clear History"):
            clear_history()
            st.rerun()

    # Display past chat messages
    for msg in st.session_state.messages:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'])

    # Handle new user prompt
    if prompt := st.chat_input("Ask your question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Running query..."):
                output, generated_sql = full_pipeline(prompt, language, model_id, use_nl, max_nl, override_nl)
                if isinstance(output, pd.DataFrame):
                    st.dataframe(output)
                    display_output = "✅ Returned a data table."
                else:
                    st.markdown(output)
                    display_output = output
                if show_sql == "Yes" and generated_sql:
                    st.sidebar.markdown("### Generated SQL")
                    st.sidebar.code(generated_sql, language='sql')
                # save to history
                insert_into_history(prompt, generated_sql or "")

                # 3) immediately reflect it in the sidebar
                st.session_state.history_list.insert(0, prompt)
        st.session_state.messages.append({"role": "assistant", "content": display_output})

    add_footer()

if __name__ == "__main__":
    main()
