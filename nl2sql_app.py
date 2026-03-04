import streamlit as st
import mysql.connector
import pandas as pd
import json
import uuid
from typing import Any, Dict, List

try:
    from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
    from langchain_core.messages import HumanMessage
    from langchain_core.runnables import RunnableLambda
    from langchain_core.runnables.history import RunnableWithMessageHistory
    from langchain_core.tools import tool
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

DB_HOST = "163.192.105.216"   # Database Host
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
        use_pure=True,
        consume_results=True
    )

def get_safe_cursor():
    """Return a fresh *buffered* cursor and its connection for each query."""
    conn = get_db_connection()
    # buffered=True ensures result sets are fully fetched client-side, avoiding
    # `InternalError: Unread result found` when closing cursors/connections.
    return conn.cursor(buffered=True), conn

def safe_close_cursor_conn(cursor, conn) -> None:
    """Best-effort cleanup that avoids mysql-connector 'Unread result found' on close."""
    # First try to consume any pending results.
    try:
        conn.consume_results()
    except Exception:
        pass

    # Closing the cursor can itself raise if unread results are still present.
    try:
        cursor.close()
    except mysql.connector.errors.InternalError:
        # Try one more consume + close cycle
        try:
            conn.consume_results()
        except Exception:
            pass
        try:
            cursor.close()
        except Exception:
            pass

    # Close connection last.
    try:
        conn.close()
    except Exception:
        pass

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
        safe_close_cursor_conn(cursor, conn)

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
        options = json.dumps(
            {
                "schemas": [DBSYSTEM_SCHEMA],
                "verbose": 1,
                "model_id": model_id,
            }
        )

        # Use callproc + stored_results instead of execute(CALL...) + nextset().
        # With mysql-connector pure-python cursors, nextset() is not implemented,
        # which can leave unread results and trigger InternalError on close.
        output_vars = cursor.callproc(
            "sys.NL_SQL",
            (natural_language_statement, None, options),
        )

        for stored_result in cursor.stored_results():
            rows = stored_result.fetchall()
            cols = list(stored_result.column_names)

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

            try:
                stored_result.close()
            except Exception:
                pass

        if not generated_sql and len(output_vars) >= 2:
            output_value = output_vars[1]
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
        safe_close_cursor_conn(cursor, conn)

def parse_ml_generate_response(raw_response: Any) -> str:
    """Parse ML_GENERATE output and return plain text."""
    if not isinstance(raw_response, str):
        return str(raw_response)
    try:
        parsed = json.loads(raw_response)
        if isinstance(parsed, dict) and "text" in parsed:
            return str(parsed["text"]).strip()
    except json.JSONDecodeError:
        pass
    return raw_response.strip()

def call_ml_generate_text(prompt_text: str, model_id: str, language: str) -> str:
    """Run ML_GENERATE with a text prompt and return normalized text."""
    cursor, conn = get_safe_cursor()
    try:
        cursor.execute(
            (
                "SELECT sys.ML_GENERATE(%s, "
                "JSON_OBJECT('task','generation','model_id',%s,'language',%s,'max_tokens',4000)) "
                "AS response;"
            ),
            (prompt_text, model_id, language)
        )
        return parse_ml_generate_response(cursor.fetchall()[0][0])
    finally:
        safe_close_cursor_conn(cursor, conn)

def contextualize_question_with_history(
    user_question: str,
    user_language: str,
    model_id: str,
    history_messages: List[Any]
) -> str:
    """Rewrite follow-up questions into standalone prompts using chat history."""
    if not history_messages:
        return user_question

    history_lines = []
    for msg in history_messages[-12:]:
        content = str(getattr(msg, "content", "")).strip()
        if not content:
            continue
        role = "assistant"
        if LANGCHAIN_AVAILABLE and isinstance(msg, HumanMessage):
            role = "user"
        history_lines.append(f"{role}: {content}")

    if not history_lines:
        return user_question

    rewrite_prompt = (
        "Rewrite the final user message as a standalone analytics question for SQL generation. "
        "Keep the original intent and constraints. Return only the rewritten question.\n\n"
        f"Conversation:\n{chr(10).join(history_lines)}\n"
        f"Final user message:\n{user_question}"
    )

    try:
        rewritten = call_ml_generate_text(rewrite_prompt, model_id, user_language)
        return rewritten if rewritten else user_question
    except Exception:
        return user_question

if LANGCHAIN_AVAILABLE:
    @tool("run_nl_sql_tool")
    def run_nl_sql_tool(question: str, model_id: str) -> str:
        """Execute NL_SQL and return generated SQL plus result payload."""
        result, generated_sql = run_nl_sql(question, model_id)
        if isinstance(result, pd.DataFrame):
            payload = {
                "kind": "table",
                "generated_sql": generated_sql,
                "columns": result.columns.tolist(),
                "rows": result.values.tolist()
            }
        else:
            payload = {
                "kind": "message",
                "generated_sql": generated_sql,
                "message": str(result)
            }
        return json.dumps(payload, default=str)

    @tool("generate_nl_answer_tool")
    def generate_nl_answer_tool(
        user_question: str,
        table_payload: str,
        user_language: str,
        model_id: str
    ) -> str:
        """Generate a natural-language answer from tabular payload."""
        try:
            parsed = json.loads(table_payload)
        except json.JSONDecodeError:
            return str(table_payload)

        if parsed.get("kind") != "table":
            return str(parsed.get("message", "No tabular output."))

        table_df = pd.DataFrame(parsed.get("rows", []), columns=parsed.get("columns", []))
        return generate_natural_language_answer(user_question, table_df, user_language, model_id)

    def get_langchain_history(session_id: str) -> BaseChatMessageHistory:
        """Get or create per-session chat history used by LangChain."""
        if "lc_history_store" not in st.session_state:
            st.session_state["lc_history_store"] = {}

        history_store = st.session_state["lc_history_store"]
        if session_id not in history_store:
            history_store[session_id] = InMemoryChatMessageHistory()
        return history_store[session_id]

    def stateful_tool_entrypoint(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """LangChain runnable entrypoint with history-aware orchestration."""
        question = str(inputs.get("question", "")).strip()
        model_id = str(inputs.get("model_id", "")).strip()
        user_language = str(inputs.get("user_language", "en")).strip()
        use_nl = bool(inputs.get("use_nl", False))
        max_nl_lines = int(inputs.get("max_nl_lines", 24))
        override_nl = bool(inputs.get("override_nl", False))
        history_messages = inputs.get("history", [])

        standalone_question = contextualize_question_with_history(
            question, user_language, model_id, history_messages
        )
        tool_raw = run_nl_sql_tool.invoke({"question": standalone_question, "model_id": model_id})
        try:
            tool_payload = json.loads(tool_raw)
        except json.JSONDecodeError:
            tool_payload = {"kind": "message", "message": str(tool_raw), "generated_sql": ""}

        generated_sql = str(tool_payload.get("generated_sql", ""))

        if (model_id in restricted_models) and (not override_nl):
            use_nl = False

        if tool_payload.get("kind") == "table":
            columns = tool_payload.get("columns", [])
            rows = tool_payload.get("rows", [])
            table_df = pd.DataFrame(rows, columns=columns)

            if use_nl and len(table_df) <= max_nl_lines:
                nl_answer = generate_nl_answer_tool.invoke(
                    {
                        "user_question": question,
                        "table_payload": json.dumps(tool_payload),
                        "user_language": user_language,
                        "model_id": model_id
                    }
                )
                return {
                    "answer": nl_answer,
                    "render_type": "text",
                    "render_payload": nl_answer,
                    "generated_sql": generated_sql
                }

            return {
                "answer": f"Returned {len(table_df)} row(s).",
                "render_type": "table",
                "render_payload": {
                    "columns": columns,
                    "rows": rows
                },
                "generated_sql": generated_sql
            }

        message = str(tool_payload.get("message", "No output returned."))
        return {
            "answer": message,
            "render_type": "text",
            "render_payload": message,
            "generated_sql": generated_sql
        }

    def get_stateful_runnable() -> RunnableWithMessageHistory:
        """Create one history-aware runnable per Streamlit session."""
        if "stateful_langchain_runnable" not in st.session_state:
            st.session_state["stateful_langchain_runnable"] = RunnableWithMessageHistory(
                RunnableLambda(stateful_tool_entrypoint),
                get_langchain_history,
                input_messages_key="question",
                history_messages_key="history",
                output_messages_key="answer"
            )
        return st.session_state["stateful_langchain_runnable"]

def full_pipeline_stateful(
    user_question: str,
    user_language: str,
    model_id: str,
    use_nl: bool,
    max_nl_lines: int,
    override_nl: bool = False
):
    """Run the history-aware LangChain pipeline; fallback to stateless path."""
    if not LANGCHAIN_AVAILABLE:
        return full_pipeline(user_question, user_language, model_id, use_nl, max_nl_lines, override_nl)

    if "lc_session_id" not in st.session_state:
        st.session_state["lc_session_id"] = str(uuid.uuid4())

    runnable = get_stateful_runnable()
    response = runnable.invoke(
        {
            "question": user_question,
            "user_language": user_language,
            "model_id": model_id,
            "use_nl": use_nl,
            "max_nl_lines": max_nl_lines,
            "override_nl": override_nl
        },
        config={"configurable": {"session_id": st.session_state["lc_session_id"]}}
    )

    render_type = response.get("render_type", "text")
    generated_sql = str(response.get("generated_sql", ""))
    if render_type == "table":
        payload = response.get("render_payload", {})
        if isinstance(payload, dict):
            return pd.DataFrame(payload.get("rows", []), columns=payload.get("columns", [])), generated_sql
    return response.get("render_payload", ""), generated_sql

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
        return parse_ml_generate_response(cursor.fetchall()[0][0])
    finally:
        safe_close_cursor_conn(cursor, conn)

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
# Chat rendering helpers
# -----------------------------------------------------------------------------

def render_chat_message(message: Dict[str, Any]) -> None:
    """Render a stored chat message, including persisted table payloads."""
    role = str(message.get("role", "assistant"))
    with st.chat_message(role):
        msg_type = str(message.get("type", "text"))
        if msg_type == "table":
            payload = message.get("payload", {})
            if isinstance(payload, dict):
                columns = payload.get("columns", [])
                rows = payload.get("rows", [])
                st.dataframe(pd.DataFrame(rows, columns=columns))
                return
        st.markdown(str(message.get("content", "")))

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
        if not LANGCHAIN_AVAILABLE:
            st.warning("LangChain not installed. Running stateless mode.")

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
        render_chat_message(msg)

    # Handle new user prompt
    if prompt := st.chat_input("Ask your question..."):
        st.session_state.messages.append({"role": "user", "type": "text", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Running query..."):
                output, generated_sql = full_pipeline_stateful(
                    prompt, language, model_id, use_nl, max_nl, override_nl
                )
                if isinstance(output, pd.DataFrame):
                    st.dataframe(output)
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "type": "table",
                            "content": "✅ Returned a data table.",
                            "payload": {
                                "columns": output.columns.tolist(),
                                "rows": output.values.tolist(),
                            },
                        }
                    )
                else:
                    st.markdown(output)
                    st.session_state.messages.append(
                        {"role": "assistant", "type": "text", "content": str(output)}
                    )
                if show_sql == "Yes" and generated_sql:
                    st.sidebar.markdown("### Generated SQL")
                    st.sidebar.code(generated_sql, language='sql')

    add_footer()

if __name__ == "__main__":
    main()
