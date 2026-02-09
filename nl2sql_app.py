import streamlit as st
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

# -----------------------------------------------------------------------------
# Model Configuration
# -----------------------------------------------------------------------------

MODEL_CATALOG_QUERY = (
    "SELECT * FROM sys.ML_SUPPORTED_LLMS "
    "ORDER BY availability_date DESC;"
)
GENERATION_MODELS_QUERY = (
    "SELECT * "
    "FROM sys.ML_SUPPORTED_LLMS "
    "WHERE JSON_CONTAINS(capabilities, '\"GENERATION\"') "
    "ORDER BY availability_date DESC;"
)

default_model = None
MODEL_OPTIONS = []
restricted_models = []

def refresh_model_catalog():
    """Refresh model options and restricted models from the system catalog."""
    global MODEL_OPTIONS, restricted_models, default_model
    try:
        catalog_df = execute_sql(MODEL_CATALOG_QUERY)
        generation_df = execute_sql(GENERATION_MODELS_QUERY)
    except Exception:
        MODEL_OPTIONS = []
        restricted_models = []
        default_model = None
        return

    MODEL_OPTIONS = (
        generation_df["model_id"].dropna().astype(str).tolist()
        if "model_id" in generation_df.columns
        else []
    )

    if "default_model" in generation_df.columns and "model_id" in generation_df.columns:
        defaults = generation_df[generation_df["default_model"] == 1]["model_id"].dropna().astype(str).tolist()
        default_model = defaults[0] if defaults else (MODEL_OPTIONS[0] if MODEL_OPTIONS else None)
    else:
        default_model = MODEL_OPTIONS[0] if MODEL_OPTIONS else None

    if "provider" in catalog_df.columns and "model_id" in catalog_df.columns:
        restricted_models = (
            catalog_df[catalog_df["provider"] == "HeatWave"]["model_id"]
            .dropna()
            .astype(str)
            .tolist()
        )
    else:
        restricted_models = []

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

def run_nl_sql(natural_language_statement: str, model_id: str):
    """
    Execute NL_SQL and return:
    1) the final query result as DataFrame (or message string on failure/no rows)
    2) the generated SQL extracted from the verbose NL_SQL info stream.
    """
    cursor, conn = get_safe_cursor()
    generated_sql = ""
    result_frames = []

    try:
        cursor.execute(
            (
                "CALL sys.NL_SQL("
                "%s, "
                "@output, "
                "JSON_OBJECT("
                "'schemas', JSON_ARRAY(%s), "
                "'verbose', 1, "
                "'model_id', %s"
                ")"
                ");"
            ),
            (natural_language_statement, DBSYSTEM_SCHEMA, model_id)
        )

        while True:
            if cursor.with_rows:
                rows = cursor.fetchall()
                cols = list(cursor.column_names)

                if rows and cols == ["nl_sql_info"]:
                    for row in rows:
                        try:
                            info = json.loads(row[0])
                        except (TypeError, json.JSONDecodeError):
                            continue
                        if info.get("stage") == "validated_sql":
                            message = str(info.get("message", ""))
                            marker = "Generated SQL statement:"
                            if marker in message:
                                generated_sql = message.split(marker, 1)[1].strip()
                elif rows:
                    result_frames.append(pd.DataFrame(rows, columns=cols))

            if not cursor.nextset():
                break

        if not generated_sql:
            cursor.execute("SELECT @output AS nl_sql_output;")
            output_rows = cursor.fetchall()
            if output_rows:
                output_value = output_rows[0][0]
                if isinstance(output_value, str):
                    try:
                        output_json = json.loads(output_value)
                        generated_sql = str(
                            output_json.get("generated_sql")
                            or output_json.get("validated_sql")
                            or output_json.get("sql")
                            or ""
                        ).strip()
                    except json.JSONDecodeError:
                        generated_sql = output_value.strip()

        if not result_frames:
            return "✅ Query executed with no tabular result.", generated_sql

        if len(result_frames) == 1:
            return result_frames[0], generated_sql

        return pd.concat(result_frames, ignore_index=True), generated_sql

    except mysql.connector.Error as err:
        return f"❌ NL_SQL failed: {err}", generated_sql
    finally:
        cursor.close()
        conn.close()

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
        raw_response = cursor.fetchall()[0][0]
        if not isinstance(raw_response, str):
            return str(raw_response)
        try:
            parsed = json.loads(raw_response)
            if isinstance(parsed, dict) and "text" in parsed:
                return str(parsed["text"]).strip()
        except json.JSONDecodeError:
            pass
        return raw_response.strip()
    finally:
        cursor.close()
        conn.close()

def full_pipeline(user_question, user_language, model_id,
                  use_nl, max_nl_lines, override_nl=False):
    final_result, generated_sql = run_nl_sql(user_question, model_id)

    if (model_id in restricted_models) and (not override_nl):
        use_nl = False

    n = len(final_result) if isinstance(final_result, pd.DataFrame) else 0

    if use_nl and isinstance(final_result, pd.DataFrame) and n <= max_nl_lines:
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
    global DB_NAME, DBSYSTEM_SCHEMA

    st.title("Natural Language → SQL Chatbot")

    if 'messages' not in st.session_state:
        st.session_state.messages = []

    with st.sidebar:
        refresh_model_catalog()
        if not MODEL_OPTIONS:
            st.error("No generation-capable models found in sys.ML_SUPPORTED_LLMS.")
            st.stop()

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
        default_index = MODEL_OPTIONS.index(default_model) if default_model in MODEL_OPTIONS else 0
        model_id = st.selectbox("Model List:", MODEL_OPTIONS, index=default_index)
        
        # 1) detect the restricted models as before
        nl_disabled = model_id in restricted_models

        # 2) offer an override checkbox that’s only visible when the model is restricted
        override_nl = False
        if nl_disabled:
            override_nl = st.checkbox(
                "⚠️ Force‐enable NL even on restricted model", 
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
        st.session_state.messages.append({"role": "assistant", "content": display_output})

    add_footer()

if __name__ == "__main__":
    main()
