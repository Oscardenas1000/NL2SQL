import atexit
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import mysql.connector
import pandas as pd
import streamlit as st

from heatwave_llm import HeatWaveLLM

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

DEFAULT_DB_HOST = "163.192.105.216"
DEFAULT_DB_PORT = 3306
DEFAULT_DB_USER = "admin"
DB_PASSWORD = "@Mysqlse2025"
DEFAULT_DB_NAME = "airportdb"

DB_NAME = DEFAULT_DB_NAME

# -----------------------------------------------------------------------------
# Model Configuration
# -----------------------------------------------------------------------------

MODEL_CATALOG_QUERY = (
    "SELECT * FROM sys.ML_SUPPORTED_LLMS "
    "ORDER BY availability_date DESC;"
)

default_model: Optional[str] = None
MODEL_OPTIONS: List[str] = []
restricted_models: List[str] = []
MODEL_CATALOG_ERROR: Optional[str] = None

DEFAULT_SMALL_MODEL_ID = "llama3.1-8b-instruct-v1"
DEFAULT_MEDIUM_MODEL_ID = "meta.llama-3.2-90b-vision-instruct"
DEFAULT_LARGE_MODEL_ID = "xai.grok-4-1-fast-reasoning"
MODEL_PICKER_OPTIONS = ["Small", "Medium", "Large", "Catalog"]

# -----------------------------------------------------------------------------
# Router SQL bundle (externalized schema/tables/procedures/triggers)
# -----------------------------------------------------------------------------

ROUTER_SETUP_VERSION = "v5"
ROUTER_SETUP_STATE_KEY = f"_smart_ask_ready_{ROUTER_SETUP_VERSION}"
ROUTER_SQL_DIR = os.path.join(os.path.dirname(__file__), "sql", "router")
ROUTER_SQL_PLAN: List[Tuple[str, str]] = [
    ("001_schema_tables.sql", "multi"),
    ("005_drop_routines.sql", "multi"),
    ("010_create_refresh_schema_hints.sql", "single"),
    ("020_create_smart_ask.sql", "single"),
    ("030_create_submit_router_feedback.sql", "single"),
    ("040_create_feedback_metrics_trigger.sql", "single"),
]

# -----------------------------------------------------------------------------
# Runtime LLM cache and cleanup
# -----------------------------------------------------------------------------

_ACTIVE_LLM_CLIENTS: List[HeatWaveLLM] = []


def _track_llm_client(client: HeatWaveLLM) -> None:
    if not any(existing is client for existing in _ACTIVE_LLM_CLIENTS):
        _ACTIVE_LLM_CLIENTS.append(client)


@atexit.register
def _cleanup_llm_clients() -> None:
    for client in list(_ACTIVE_LLM_CLIENTS):
        try:
            client.close()
        except Exception:
            pass
    _ACTIVE_LLM_CLIENTS.clear()


# -----------------------------------------------------------------------------
# Routing heuristics
# -----------------------------------------------------------------------------


_CONVERSATIONAL_MARKERS = [
    "my name is",
    "i am ",
    "call me ",
    "hello",
    "hi",
    "hey",
    "how are you",
    "who are you",
    "what is your name",
]

_DB_INTENT_MARKERS = [
    "database",
    "schema",
    "table",
    "sql",
    "query",
    "show",
    "list",
    "count",
    "sum",
    "average",
    "top",
    "rows",
    "data",
]


def is_conversational_prompt(user_question: str) -> bool:
    normalized = " ".join(str(user_question or "").strip().lower().split())
    if not normalized:
        return True

    has_conversation_marker = any(marker in normalized for marker in _CONVERSATIONAL_MARKERS)
    has_db_intent_marker = any(marker in normalized for marker in _DB_INTENT_MARKERS)
    return has_conversation_marker and not has_db_intent_marker


def detect_schema_mentions(user_question: str, available_schemas: List[str]) -> List[str]:
    question = str(user_question or "")
    if not question:
        return []

    normalized_question = question.lower()
    mentioned: List[str] = []
    for schema in available_schemas:
        schema_name = str(schema).strip()
        if not schema_name:
            continue

        # Match whole schema tokens so "fifa" doesn't match unrelated words.
        pattern = rf"(?<![a-z0-9_]){re.escape(schema_name.lower())}(?![a-z0-9_])"
        if re.search(pattern, normalized_question):
            mentioned.append(schema_name)

    return mentioned


def safe_rerun() -> None:
    rerun_fn = getattr(st, "rerun", None)
    if callable(rerun_fn):
        rerun_fn()
        return

    experimental_rerun_fn = getattr(st, "experimental_rerun", None)
    if callable(experimental_rerun_fn):
        experimental_rerun_fn()


# -----------------------------------------------------------------------------
# Config helpers
# -----------------------------------------------------------------------------


def _read_config_value(key: str, default: Optional[str] = None) -> Optional[str]:
    env_value = os.getenv(key)
    if env_value not in (None, ""):
        return env_value

    try:
        if key in st.secrets:
            secret_value = st.secrets[key]
            if secret_value not in (None, ""):
                return str(secret_value)

        db_section = st.secrets.get("database", {})
        if hasattr(db_section, "get"):
            for candidate in (key, key.lower(), key.upper()):
                section_value = db_section.get(candidate)
                if section_value not in (None, ""):
                    return str(section_value)
    except Exception:
        pass

    return default


def get_connection_params(selected_database: Optional[str] = None) -> Dict[str, Any]:
    host = _read_config_value("DB_HOST", DEFAULT_DB_HOST)
    port_raw = _read_config_value("DB_PORT", str(DEFAULT_DB_PORT))
    user = _read_config_value("DB_USER", DEFAULT_DB_USER)
    password = _read_config_value("DB_PASSWORD", DB_PASSWORD)
    database = selected_database or _read_config_value("DB_NAME", DEFAULT_DB_NAME)

    try:
        port = int(port_raw) if port_raw is not None else DEFAULT_DB_PORT
    except (TypeError, ValueError):
        port = DEFAULT_DB_PORT

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
        "ssl_disabled": False,
    }


# -----------------------------------------------------------------------------
# DB helpers – each call opens/closes its own connection for concurrency
# -----------------------------------------------------------------------------


def get_db_connection(
    connection_params: Dict[str, Any],
    database_override: Optional[str] = None,
) -> mysql.connector.MySQLConnection:
    connect_kwargs: Dict[str, Any] = {
        "host": connection_params["host"],
        "port": int(connection_params["port"]),
        "user": connection_params["user"],
        "password": connection_params["password"],
        "ssl_disabled": bool(connection_params.get("ssl_disabled", False)),
        "use_pure": True,
        "consume_results": True,
        "autocommit": True,
    }

    database = database_override if database_override is not None else connection_params.get("database")
    if database:
        connect_kwargs["database"] = database

    return mysql.connector.connect(**connect_kwargs)


def get_safe_cursor(
    connection_params: Dict[str, Any],
    database_override: Optional[str] = None,
) -> Tuple[mysql.connector.cursor.MySQLCursor, mysql.connector.MySQLConnection]:
    conn = get_db_connection(connection_params, database_override=database_override)
    return conn.cursor(buffered=True), conn


def safe_close_cursor_conn(
    cursor: mysql.connector.cursor.MySQLCursor,
    conn: mysql.connector.MySQLConnection,
) -> None:
    try:
        conn.consume_results()
    except Exception:
        pass

    try:
        cursor.close()
    except mysql.connector.errors.InternalError:
        try:
            conn.consume_results()
        except Exception:
            pass
        try:
            cursor.close()
        except Exception:
            pass
    except Exception:
        pass

    try:
        conn.close()
    except Exception:
        pass


def execute_sql(
    sql: str,
    connection_params: Dict[str, Any],
    params: Optional[Tuple[Any, ...]] = None,
    database_override: Optional[str] = None,
) -> pd.DataFrame:
    cursor, conn = get_safe_cursor(connection_params, database_override=database_override)
    try:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        cols = cursor.column_names
        return pd.DataFrame(rows, columns=cols)
    finally:
        safe_close_cursor_conn(cursor, conn)


# -----------------------------------------------------------------------------
# Router SQL file helpers
# -----------------------------------------------------------------------------


def _read_router_sql_file(filename: str) -> str:
    path = os.path.join(ROUTER_SQL_DIR, filename)
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _smart_ask_has_schema_scope_param(cursor: mysql.connector.cursor.MySQLCursor) -> bool:
    cursor.execute(
        (
            "SELECT COUNT(*) "
            "FROM information_schema.parameters "
            "WHERE specific_schema = 'demo' "
            "AND specific_name = 'smart_ask' "
            "AND parameter_mode = 'IN' "
            "AND parameter_name = 'p_schema_scope_json'"
        )
    )
    row = cursor.fetchone()
    return bool(row and int(row[0]) > 0)


def _column_exists(
    cursor: mysql.connector.cursor.MySQLCursor,
    schema_name: str,
    table_name: str,
    column_name: str,
) -> bool:
    cursor.execute(
        (
            "SELECT COUNT(*) "
            "FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s AND column_name = %s"
        ),
        (schema_name, table_name, column_name),
    )
    row = cursor.fetchone()
    return bool(row and int(row[0]) > 0)


def _ensure_router_log_columns(cursor: mysql.connector.cursor.MySQLCursor) -> None:
    """Backward-compatible migration for older demo.ai_router_log layouts."""
    if not _column_exists(cursor, "demo", "ai_router_log", "route_confidence"):
        cursor.execute(
            "ALTER TABLE demo.ai_router_log "
            "ADD COLUMN route_confidence DECIMAL(5,2) NULL AFTER route"
        )

    if not _column_exists(cursor, "demo", "ai_router_log", "ambiguity_flag"):
        cursor.execute(
            "ALTER TABLE demo.ai_router_log "
            "ADD COLUMN ambiguity_flag TINYINT(1) NOT NULL DEFAULT 0 "
            "AFTER route_confidence"
        )

    if not _column_exists(cursor, "demo", "ai_router_log", "cache_hit"):
        cursor.execute(
            "ALTER TABLE demo.ai_router_log "
            "ADD COLUMN cache_hit TINYINT(1) NOT NULL DEFAULT 0 "
            "AFTER ambiguity_flag"
        )


def _split_simple_sql_statements(script: str) -> List[str]:
    cleaned_lines = []
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        cleaned_lines.append(line)

    cleaned_script = "\n".join(cleaned_lines)

    statements: List[str] = []
    token: List[str] = []
    in_single_quote = False
    in_double_quote = False
    escape_next = False

    for char in cleaned_script:
        token.append(char)

        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            continue

        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            continue

        if char == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(token).strip()
            if statement:
                statements.append(statement)
            token = []

    tail = "".join(token).strip()
    if tail:
        statements.append(tail)

    return statements


def apply_router_sql_bundle(connection_params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    cursor, conn = get_safe_cursor(connection_params, database_override=None)
    try:
        if st.session_state.get(ROUTER_SETUP_STATE_KEY):
            _ensure_router_log_columns(cursor)
            if _smart_ask_has_schema_scope_param(cursor):
                return True, None
            # Force one-time routine refresh if an older smart_ask signature is still present.
            st.session_state[ROUTER_SETUP_STATE_KEY] = False

        for filename, mode in ROUTER_SQL_PLAN:
            sql_text = _read_router_sql_file(filename)
            if mode == "multi":
                for statement in _split_simple_sql_statements(sql_text):
                    cursor.execute(statement)
            else:
                cursor.execute(sql_text.strip())

        _ensure_router_log_columns(cursor)
        cursor.execute("CALL demo.refresh_router_schema_hints()")

        try:
            conn.commit()
        except Exception:
            pass

        st.session_state[ROUTER_SETUP_STATE_KEY] = True
        return True, None
    except FileNotFoundError as err:
        return False, f"Router SQL file missing: {err}"
    except mysql.connector.Error as err:
        return False, str(err)
    finally:
        safe_close_cursor_conn(cursor, conn)


# -----------------------------------------------------------------------------
# Model catalog and NL_SQL helpers
# -----------------------------------------------------------------------------


def _capabilities_include_generation(capabilities: Any) -> bool:
    if capabilities is None:
        return False

    parsed: Any = capabilities
    if isinstance(parsed, str):
        text_value = parsed.strip()
        if not text_value:
            return False
        try:
            parsed = json.loads(text_value)
        except json.JSONDecodeError:
            parsed = text_value

    if isinstance(parsed, dict):
        values = list(parsed.values())
    elif isinstance(parsed, (list, tuple, set)):
        values = list(parsed)
    else:
        values = [parsed]

    for value in values:
        token = str(value).strip().upper()
        if token == "GENERATION" or "GENERATION" in token:
            return True

    return False


def refresh_model_catalog(connection_params: Dict[str, Any]) -> None:
    """Refresh model options and restricted models from the system catalog."""
    global MODEL_OPTIONS, restricted_models, default_model, MODEL_CATALOG_ERROR
    try:
        catalog_df = execute_sql(MODEL_CATALOG_QUERY, connection_params)
        MODEL_CATALOG_ERROR = None
    except Exception as err:
        MODEL_OPTIONS = []
        restricted_models = []
        default_model = None
        MODEL_CATALOG_ERROR = str(err)
        return

    if "model_id" in catalog_df.columns:
        all_model_ids = catalog_df["model_id"].dropna().astype(str).tolist()
    else:
        all_model_ids = []

    generation_model_ids: List[str] = []
    if "model_id" in catalog_df.columns and "capabilities" in catalog_df.columns:
        generation_df = catalog_df[catalog_df["capabilities"].apply(_capabilities_include_generation)]
        generation_model_ids = generation_df["model_id"].dropna().astype(str).tolist()

    MODEL_OPTIONS = generation_model_ids if generation_model_ids else all_model_ids

    if "default_model" in catalog_df.columns and "model_id" in catalog_df.columns:
        defaults = catalog_df[catalog_df["default_model"] == 1]["model_id"].dropna().astype(str).tolist()
        if defaults:
            default_candidate = defaults[0]
            default_model = default_candidate if default_candidate in MODEL_OPTIONS else (MODEL_OPTIONS[0] if MODEL_OPTIONS else None)
        else:
            default_model = MODEL_OPTIONS[0] if MODEL_OPTIONS else None
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


def _resolve_model_option(candidate: Optional[str], model_options: List[str]) -> Optional[str]:
    requested = str(candidate or "").strip()
    if not requested:
        return None

    if requested in model_options:
        return requested

    requested_lower = requested.lower()
    for model_id in model_options:
        if str(model_id).lower() == requested_lower:
            return str(model_id)

    return None


def get_model_size_presets(model_options: List[str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    configured_presets = {
        "Small": str(_read_config_value("MODEL_PRESET_SMALL", DEFAULT_SMALL_MODEL_ID) or DEFAULT_SMALL_MODEL_ID),
        "Medium": str(_read_config_value("MODEL_PRESET_MEDIUM", DEFAULT_MEDIUM_MODEL_ID) or DEFAULT_MEDIUM_MODEL_ID),
        "Large": str(_read_config_value("MODEL_PRESET_LARGE", DEFAULT_LARGE_MODEL_ID) or DEFAULT_LARGE_MODEL_ID),
    }

    resolved_presets: Dict[str, str] = {}
    for size_label, configured_model_id in configured_presets.items():
        resolved_model_id = _resolve_model_option(configured_model_id, model_options)
        if resolved_model_id:
            resolved_presets[size_label] = resolved_model_id

    return configured_presets, resolved_presets


def _extract_generated_sql_from_nl_info_rows(rows: List[Tuple[Any, ...]], current_sql: str = "") -> str:
    generated_sql = current_sql
    for row in rows:
        try:
            info = json.loads(row[0])
        except (TypeError, json.JSONDecodeError, IndexError):
            continue

        if info.get("stage") == "validated_sql":
            message = str(info.get("message", ""))
            marker = "Generated SQL statement:"
            if marker in message:
                generated_sql = message.split(marker, 1)[1].strip()

    return generated_sql


def run_nl_sql(
    natural_language_statement: str,
    model_id: str,
    connection_params: Dict[str, Any],
    schema_scope: Optional[List[str]] = None,
) -> Tuple[Any, str]:
    """
    Execute NL_SQL and return:
    1) final query result as DataFrame (or message string)
    2) generated SQL extracted from the NL_SQL info stream.
    """
    cursor, conn = get_safe_cursor(connection_params)
    generated_sql = ""
    result_frames: List[pd.DataFrame] = []

    try:
        # NL_SQL expects options.schemas as a JSON array of schema names.
        cleaned_schema_scope: List[str] = []
        for schema in schema_scope or []:
            schema_name = str(schema).strip()
            if schema_name and schema_name not in cleaned_schema_scope:
                cleaned_schema_scope.append(schema_name)

        if not cleaned_schema_scope:
            fallback_schema = str(connection_params.get("database") or DB_NAME).strip()
            if fallback_schema:
                cleaned_schema_scope = [fallback_schema]

        options = json.dumps(
            {
                "schemas": cleaned_schema_scope,
                "verbose": 1,
                "model_id": model_id,
            }
        )

        output_vars = cursor.callproc(
            "sys.NL_SQL",
            (natural_language_statement, None, options),
        )

        for stored_result in cursor.stored_results():
            rows = stored_result.fetchall()
            cols = list(stored_result.column_names)

            if rows and cols == ["nl_sql_info"]:
                generated_sql = _extract_generated_sql_from_nl_info_rows(rows, generated_sql)
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


def ensure_smart_ask_objects(connection_params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Ensure demo schema/log tables/procedures/triggers exist using external SQL files."""
    return apply_router_sql_bundle(connection_params)


def _extract_generated_sql_from_smart_ask_answer(answer: str) -> str:
    if not answer:
        return ""

    try:
        parsed = json.loads(answer)
    except json.JSONDecodeError:
        return ""

    if not isinstance(parsed, dict):
        return ""

    return str(parsed.get("generated_sql", "")).strip()


def run_smart_ask(
    user_question: str,
    connection_params: Dict[str, Any],
    schema_scope: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Call demo.smart_ask and return route, answer, generated SQL, and optional SQL table output."""
    cursor, conn = get_safe_cursor(connection_params)
    route = "LLM"
    answer = ""
    generated_sql = ""
    log_id: Optional[int] = None
    result_frames: List[pd.DataFrame] = []

    try:
        cleaned_schema_scope: List[str] = []
        for schema in schema_scope or []:
            schema_name = str(schema).strip()
            if schema_name and schema_name not in cleaned_schema_scope:
                cleaned_schema_scope.append(schema_name)

        if not cleaned_schema_scope:
            fallback_schema = str(connection_params.get("database") or DB_NAME).strip()
            if fallback_schema:
                cleaned_schema_scope = [fallback_schema]

        schema_scope_json = json.dumps(cleaned_schema_scope)
        out_params = cursor.callproc("demo.smart_ask", (user_question, schema_scope_json, "", ""))
        if len(out_params) >= 4:
            route = str(out_params[2] or "LLM").strip().upper()
            answer = str(out_params[3] or "").strip()

        for stored_result in cursor.stored_results():
            rows = stored_result.fetchall()
            cols = list(stored_result.column_names)

            if rows and cols == ["nl_sql_info"]:
                generated_sql = _extract_generated_sql_from_nl_info_rows(rows, generated_sql)
            elif rows:
                result_frames.append(pd.DataFrame(rows, columns=cols))

            try:
                stored_result.close()
            except Exception:
                pass

        if not generated_sql:
            generated_sql = _extract_generated_sql_from_smart_ask_answer(answer)

        cursor.execute("SELECT @smart_ask_log_id")
        log_row = cursor.fetchone()
        if log_row and log_row[0] is not None:
            try:
                log_id = int(log_row[0])
            except (TypeError, ValueError):
                log_id = None

        try:
            conn.commit()
        except Exception:
            pass

        return {
            "route": route,
            "answer": answer,
            "generated_sql": generated_sql,
            "log_id": log_id,
            "table": result_frames[-1] if result_frames else None,
        }
    except mysql.connector.Error as err:
        return {
            "route": "LLM",
            "answer": f"❌ smart_ask failed: {err}",
            "generated_sql": "",
            "log_id": None,
            "table": None,
        }
    finally:
        safe_close_cursor_conn(cursor, conn)


def submit_router_feedback(
    router_log_id: int,
    feedback_type: str,
    connection_params: Dict[str, Any],
    feedback_note: Optional[str] = None,
) -> Tuple[bool, str]:
    cursor, conn = get_safe_cursor(connection_params)
    try:
        cursor.callproc(
            "demo.submit_router_feedback",
            (int(router_log_id), str(feedback_type), feedback_note or ""),
        )
        try:
            conn.commit()
        except Exception:
            pass
        return True, "Feedback saved."
    except mysql.connector.Error as err:
        return False, str(err)
    finally:
        safe_close_cursor_conn(cursor, conn)


def render_feedback_controls(router_log_id: Optional[int], connection_params: Dict[str, Any]) -> None:
    if not router_log_id:
        return

    state_key = f"_router_feedback_{router_log_id}"
    submitted_feedback = st.session_state.get(state_key)

    st.caption("Rate this router result:")
    col_up, col_down, _ = st.columns([1, 1, 6])

    with col_up:
        up_clicked = st.button(
            "👍🏻",
            key=f"feedback_up_{router_log_id}",
            disabled=bool(submitted_feedback),
        )
    with col_down:
        down_clicked = st.button(
            "👎🏻",
            key=f"feedback_down_{router_log_id}",
            disabled=bool(submitted_feedback),
        )

    if up_clicked or down_clicked:
        feedback_type = "up" if up_clicked else "down"
        ok, message = submit_router_feedback(router_log_id, feedback_type, connection_params)
        if ok:
            st.session_state[state_key] = feedback_type
            st.success("Feedback recorded.")
        else:
            st.error(f"Feedback failed: {message}")


# -----------------------------------------------------------------------------
# Chat and response helpers
# -----------------------------------------------------------------------------


def message_to_memory_text(message: Dict[str, Any]) -> str:
    msg_type = str(message.get("type", "text"))
    if msg_type != "table":
        return str(message.get("content", "")).strip()

    payload = message.get("payload", {})
    if not isinstance(payload, dict):
        return ""

    columns = payload.get("columns", [])
    rows = payload.get("rows", [])
    preview_df = pd.DataFrame(rows[:5], columns=columns)
    preview_text = preview_df.to_string(index=False) if not preview_df.empty else "(empty result)"
    return (
        f"Returned table with {len(rows)} row(s) and columns {', '.join(map(str, columns))}.\n"
        f"Preview:\n{preview_text}"
    )


def format_recent_turns(messages: List[Dict[str, Any]], max_turns: int = 12) -> str:
    """Format the last ~12 turns as Human/AI lines for LLM prompts."""
    relevant_messages = messages[-(max_turns * 2):]
    lines: List[str] = []

    for msg in relevant_messages:
        role = "Human" if msg.get("role") == "user" else "AI"
        content = message_to_memory_text(msg)
        if content:
            lines.append(f"{role}: {content}")

    return "\n".join(lines)


def get_session_heatwave_llm(model_id: str, connection_params: Dict[str, Any]) -> HeatWaveLLM:
    signature = (
        model_id,
        connection_params.get("host"),
        int(connection_params.get("port", DEFAULT_DB_PORT)),
        connection_params.get("user"),
        connection_params.get("password"),
        connection_params.get("database"),
    )

    cached_client = st.session_state.get("_heatwave_llm_client")
    cached_signature = st.session_state.get("_heatwave_llm_signature")

    if cached_client is not None and cached_signature == signature:
        return cached_client

    if cached_client is not None:
        try:
            cached_client.close()
        except Exception:
            pass

    client = HeatWaveLLM(model_id=model_id, connection_params=connection_params)
    st.session_state["_heatwave_llm_client"] = client
    st.session_state["_heatwave_llm_signature"] = signature
    _track_llm_client(client)
    return client


def chat_with_memory(
    user_language: str,
    model_id: str,
    connection_params: Dict[str, Any],
    messages: List[Dict[str, Any]],
    extra_context: Optional[str] = None,
) -> str:
    llm = get_session_heatwave_llm(model_id=model_id, connection_params=connection_params)
    history_text = format_recent_turns(messages, max_turns=12)

    context_block = ""
    if extra_context:
        context_block = (
            "\nAdditional router context (use as supporting signal, do not mention it verbatim to the user):\n"
            f"{extra_context}\n"
        )

    prompt = (
        "You are a helpful chat assistant with conversation memory. "
        "Use the conversation context and answer the latest Human message directly. "
        f"Respond in language code '{user_language}'.\n\n"
        "Conversation:\n"
        f"{history_text}"
        f"{context_block}\n"
        "AI:"
    )
    return llm.invoke(prompt)


def explain_sql_result_with_llm(
    user_question: str,
    result_df: pd.DataFrame,
    generated_sql: str,
    user_language: str,
    model_id: str,
    connection_params: Dict[str, Any],
) -> str:
    llm = get_session_heatwave_llm(model_id=model_id, connection_params=connection_params)

    table_text = result_df.to_string(index=False)
    prompt = (
        "You are a data assistant. Explain this SQL result in clear natural language. "
        f"Respond in language code '{user_language}'.\n\n"
        f"User question:\n{user_question}\n\n"
        f"Generated SQL:\n{generated_sql or '(not available)'}\n\n"
        f"Result table:\n{table_text}\n"
    )
    return llm.invoke(prompt)


def render_and_store_sql_response(
    output: Any,
    generated_sql: str,
    user_question: str,
    show_sql: str,
    explain_result: bool,
    explain_threshold: int,
    user_language: str,
    model_id: str,
    connection_params: Dict[str, Any],
    message_mode: str,
) -> None:
    if isinstance(output, pd.DataFrame):
        st.dataframe(output)
        st.session_state.messages.append(
            {
                "role": "assistant",
                "type": "table",
                "content": f"✅ Returned {len(output)} row(s).",
                "payload": {
                    "columns": output.columns.tolist(),
                    "rows": output.values.tolist(),
                },
                "generated_sql": generated_sql,
                "mode": message_mode,
            }
        )

        if show_sql == "Yes" and generated_sql:
            st.code(generated_sql, language="sql")

        if explain_result and len(output) <= explain_threshold:
            with st.spinner("Explaining result..."):
                try:
                    explanation = explain_sql_result_with_llm(
                        user_question=user_question,
                        result_df=output,
                        generated_sql=generated_sql,
                        user_language=user_language,
                        model_id=model_id,
                        connection_params=connection_params,
                    )
                except Exception as err:
                    explanation = f"❌ Explanation failed: {err}"

            st.markdown(explanation)
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "type": "text",
                    "content": str(explanation),
                    "mode": message_mode,
                }
            )
        return

    st.markdown(str(output))
    if show_sql == "Yes" and generated_sql:
        st.code(generated_sql, language="sql")

    st.session_state.messages.append(
        {
            "role": "assistant",
            "type": "text",
            "content": str(output),
            "generated_sql": generated_sql,
            "mode": message_mode,
        }
    )


# -----------------------------------------------------------------------------
# UI helpers
# -----------------------------------------------------------------------------


def add_footer() -> None:
    st.markdown(
        """
        <style>
          [data-testid='stChatInput'] { bottom: 50px !important; }
          @media (max-width: 767px) {
            [data-testid='stChatInput'] { bottom: 90px !important; }
          }

        #fixed-footer {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            width: 100%;
            padding: 10px;
            font-size: 16px;
            color: gray;
            text-align: center;
            z-index: 10000;
        }
        </style>
        <div id="fixed-footer">
            This interface is for demonstrative purposes only. This is not a tool supported by Oracle.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chat_message(message: Dict[str, Any], show_generated_sql: bool) -> None:
    role = str(message.get("role", "assistant"))
    with st.chat_message(role):
        msg_type = str(message.get("type", "text"))

        if msg_type == "table":
            payload = message.get("payload", {})
            if isinstance(payload, dict):
                columns = payload.get("columns", [])
                rows = payload.get("rows", [])
                st.dataframe(pd.DataFrame(rows, columns=columns))

                if show_generated_sql:
                    generated_sql = str(message.get("generated_sql", "")).strip()
                    if generated_sql:
                        st.code(generated_sql, language="sql")
                return

        st.markdown(str(message.get("content", "")))

        if show_generated_sql:
            generated_sql = str(message.get("generated_sql", "")).strip()
            if generated_sql:
                st.code(generated_sql, language="sql")


# -----------------------------------------------------------------------------
# Streamlit App
# -----------------------------------------------------------------------------


def main() -> None:
    global DB_NAME

    st.title("Chat Assistant with NL2SQL")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    base_connection_params = get_connection_params()
    if not base_connection_params.get("password"):
        st.error("Missing database password. Configure DB_PASSWORD in Streamlit secrets or environment variables.")
        st.info("Example env var: DB_PASSWORD=your_password")
        st.stop()

    router_ready = False
    router_error: Optional[str] = None

    with st.sidebar:
        refresh_model_catalog(base_connection_params)
        if not MODEL_OPTIONS:
            if MODEL_CATALOG_ERROR:
                st.error(f"Model catalog query failed: {MODEL_CATALOG_ERROR}")
            else:
                st.error("No models found in sys.ML_SUPPORTED_LLMS.")
            st.stop()

        try:
            schemas_df = execute_sql("SHOW SCHEMAS;", base_connection_params)
            schema_list = schemas_df[schemas_df.columns[0]].dropna().astype(str).tolist()
        except Exception:
            schema_list = []

        if not schema_list:
            fallback_schema = str(base_connection_params.get("database") or DEFAULT_DB_NAME)
            schema_list = [fallback_schema]

        configured_default_schema = str(base_connection_params.get("database") or "").strip()
        if configured_default_schema in schema_list:
            DB_NAME = configured_default_schema
        else:
            DB_NAME = schema_list[0]

        sql_scope_state_key = "sql_schema_scope"
        sql_scope_pending_additions_key = "sql_schema_scope_pending_additions"
        pending_scope_additions_raw = st.session_state.pop(sql_scope_pending_additions_key, [])
        pending_scope_additions: List[str] = []
        if isinstance(pending_scope_additions_raw, list):
            for schema in pending_scope_additions_raw:
                schema_name = str(schema).strip()
                if schema_name and schema_name in schema_list and schema_name not in pending_scope_additions:
                    pending_scope_additions.append(schema_name)

        existing_scope = st.session_state.get(sql_scope_state_key)
        if not isinstance(existing_scope, list):
            cleaned_scope = [DB_NAME]
        else:
            cleaned_scope = [
                str(schema).strip()
                for schema in existing_scope
                if str(schema).strip() in schema_list
            ]

        if not cleaned_scope:
            cleaned_scope = [DB_NAME]

        for schema_name in pending_scope_additions:
            if schema_name not in cleaned_scope:
                cleaned_scope.append(schema_name)

        st.session_state[sql_scope_state_key] = cleaned_scope

        selected_sql_schemas = st.multiselect(
            "Schemas for SQL inference (NL_SQL):",
            schema_list,
            key=sql_scope_state_key,
            help="Choose one or more schemas to pass natively to sys.NL_SQL options.schemas.",
        )
        if not selected_sql_schemas:
            selected_sql_schemas = [DB_NAME]
            st.session_state[sql_scope_state_key] = selected_sql_schemas
        st.caption(f"SQL schema scope: {len(selected_sql_schemas)} selected")

        connection_params = get_connection_params(selected_database=DB_NAME)

        router_ready, router_error = ensure_smart_ask_objects(connection_params)
        if not router_ready and router_error:
            st.warning(f"`demo.smart_ask` unavailable: {router_error}")

        configured_presets, resolved_presets = get_model_size_presets(MODEL_OPTIONS)
        picker_mode_default_index = MODEL_PICKER_OPTIONS.index("Catalog")
        model_picker_mode = st.selectbox(
            "Model Picker:",
            MODEL_PICKER_OPTIONS,
            index=picker_mode_default_index,
            help=(
                "Small/Medium/Large use preset model IDs. "
                "You can override presets with MODEL_PRESET_SMALL, MODEL_PRESET_MEDIUM, and MODEL_PRESET_LARGE."
            ),
        )

        if model_picker_mode == "Catalog":
            default_index = MODEL_OPTIONS.index(default_model) if default_model in MODEL_OPTIONS else 0
            selected_model_id = st.selectbox("Model List:", MODEL_OPTIONS, index=default_index)
        else:
            preset_model_id = resolved_presets.get(model_picker_mode)
            if preset_model_id:
                selected_model_id = preset_model_id
                st.caption(f"{model_picker_mode} model: `{selected_model_id}`")
            else:
                fallback_model_id = default_model if default_model in MODEL_OPTIONS else MODEL_OPTIONS[0]
                selected_model_id = fallback_model_id
                configured_model_id = configured_presets.get(model_picker_mode, "(not configured)")
                st.caption(
                    f"{model_picker_mode} preset `{configured_model_id}` not available; "
                    f"using `{selected_model_id}`."
                )

        mode = st.selectbox("Mode", ["Auto", "Chat", "SQL"], index=0)

        nl_disabled = selected_model_id in restricted_models
        override_nl = False
        if nl_disabled:
            override_nl = st.checkbox(
                "⚠️ Force-enable NL even on restricted model",
                value=False,
                help="Only use if you know what you are doing",
            )

        effective_disabled = nl_disabled and not override_nl

        explain_result = st.checkbox(
            "Explain result in natural language",
            value=not effective_disabled,
            disabled=effective_disabled,
        )

        explain_threshold = int(
            st.number_input(
                "Explain threshold (rows):",
                min_value=1,
                value=24,
                disabled=not explain_result,
            )
        )

        language = st.selectbox("Language:", ["en", "es", "pt", "fr"], index=0)
        show_sql = st.radio("Show generated SQL?", ["No", "Yes"], index=0)

    for msg in st.session_state.messages:
        render_chat_message(msg, show_generated_sql=(show_sql == "Yes"))

    pending_user_prompt_key = "pending_user_prompt"
    sql_scope_pending_additions_key = "sql_schema_scope_pending_additions"
    prompt = st.chat_input("Ask your question...")

    if prompt:
        mentioned_schemas = detect_schema_mentions(prompt, schema_list)
        missing_schemas = [schema for schema in mentioned_schemas if schema not in selected_sql_schemas]
        if missing_schemas:
            st.session_state[sql_scope_pending_additions_key] = missing_schemas
            st.session_state[pending_user_prompt_key] = prompt
            safe_rerun()
    else:
        pending_prompt = st.session_state.pop(pending_user_prompt_key, None)
        if isinstance(pending_prompt, str) and pending_prompt.strip():
            prompt = pending_prompt

    if prompt:
        st.session_state.messages.append(
            {
                "role": "user",
                "type": "text",
                "content": prompt,
                "mode": mode.lower(),
            }
        )

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            active_mode = mode.lower()

            if active_mode == "auto":
                if not router_ready:
                    st.caption("Auto router unavailable; falling back to CHAT mode.")
                    active_mode = "chat"
                elif is_conversational_prompt(prompt):
                    st.caption("Auto routed locally to `LLM` (conversational input).")
                    active_mode = "chat"
                else:
                    with st.spinner("Routing with demo.smart_ask..."):
                        router_output = run_smart_ask(
                            prompt,
                            connection_params,
                            schema_scope=selected_sql_schemas,
                        )

                    router_route = str(router_output.get("route", "LLM")).upper()
                    router_answer = str(router_output.get("answer", "")).strip()
                    generated_sql = str(router_output.get("generated_sql", "")).strip()
                    router_log_id = router_output.get("log_id")
                    router_table = router_output.get("table")

                    st.caption(f"Auto routed by `demo.smart_ask` to `{router_route}`.")

                    if router_route == "SQL":
                        sql_output: Any = router_table if isinstance(router_table, pd.DataFrame) else router_answer
                        render_and_store_sql_response(
                            output=sql_output,
                            generated_sql=generated_sql,
                            user_question=prompt,
                            show_sql=show_sql,
                            explain_result=explain_result,
                            explain_threshold=explain_threshold,
                            user_language=language,
                            model_id=selected_model_id,
                            connection_params=connection_params,
                            message_mode="auto_sql",
                        )
                    else:
                        context_for_llm = (
                            f"smart_ask route: {router_route}\n"
                            f"smart_ask answer/context:\n{router_answer or '(empty)'}"
                        )
                        with st.spinner("Thinking..."):
                            try:
                                answer = chat_with_memory(
                                    user_language=language,
                                    model_id=selected_model_id,
                                    connection_params=connection_params,
                                    messages=st.session_state.messages,
                                    extra_context=context_for_llm,
                                )
                            except Exception as err:
                                answer = f"❌ Chat failed: {err}"

                        st.markdown(answer)
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "type": "text",
                                "content": str(answer),
                                "mode": "auto_chat",
                            }
                        )

                        if show_sql == "Yes" and generated_sql:
                            st.code(generated_sql, language="sql")

                    render_feedback_controls(
                        router_log_id=router_log_id if isinstance(router_log_id, int) else None,
                        connection_params=connection_params,
                    )

                    active_mode = "handled"

            if active_mode == "chat":
                with st.spinner("Thinking..."):
                    try:
                        answer = chat_with_memory(
                            user_language=language,
                            model_id=selected_model_id,
                            connection_params=connection_params,
                            messages=st.session_state.messages,
                        )
                    except Exception as err:
                        answer = f"❌ Chat failed: {err}"

                st.markdown(answer)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "type": "text",
                        "content": str(answer),
                        "mode": "chat",
                    }
                )
            elif active_mode == "sql":
                with st.spinner("Running SQL..."):
                    output, generated_sql = run_nl_sql(
                        natural_language_statement=prompt,
                        model_id=selected_model_id,
                        connection_params=connection_params,
                        schema_scope=selected_sql_schemas,
                    )

                render_and_store_sql_response(
                    output=output,
                    generated_sql=generated_sql,
                    user_question=prompt,
                    show_sql=show_sql,
                    explain_result=explain_result,
                    explain_threshold=explain_threshold,
                    user_language=language,
                    model_id=selected_model_id,
                    connection_params=connection_params,
                    message_mode="sql",
                )

    add_footer()


if __name__ == "__main__":
    main()
