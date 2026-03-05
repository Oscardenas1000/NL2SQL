import json
from typing import Any, Dict, Optional

import mysql.connector


class HeatWaveLLM:
    """Minimal HeatWave-backed text generation client."""

    def __init__(self, model_id: str, connection_params: Dict[str, Any]):
        self.model_id = model_id
        self.connection_params = dict(connection_params)
        self._conn: Optional[mysql.connector.MySQLConnection] = None
        self._connect()

    def _connect(self) -> None:
        required_keys = ("host", "port", "user", "password")
        missing = [key for key in required_keys if not self.connection_params.get(key)]
        if missing:
            raise ValueError(f"Missing connection params for HeatWaveLLM: {', '.join(missing)}")

        connect_kwargs: Dict[str, Any] = {
            "host": self.connection_params["host"],
            "port": int(self.connection_params["port"]),
            "user": self.connection_params["user"],
            "password": self.connection_params["password"],
            "ssl_disabled": bool(self.connection_params.get("ssl_disabled", False)),
            "use_pure": True,
            "consume_results": True,
        }

        database = self.connection_params.get("database")
        if database:
            connect_kwargs["database"] = database

        self._conn = mysql.connector.connect(**connect_kwargs)

    def _ensure_connection(self) -> mysql.connector.MySQLConnection:
        if self._conn is None or not self._conn.is_connected():
            self._connect()
        if self._conn is None:
            raise RuntimeError("Failed to initialize HeatWaveLLM connection")
        return self._conn

    @staticmethod
    def _parse_ml_generate_response(raw_response: Any) -> str:
        if raw_response is None:
            return ""

        if not isinstance(raw_response, str):
            return str(raw_response)

        try:
            parsed = json.loads(raw_response)
            if isinstance(parsed, dict):
                if "text" in parsed:
                    return str(parsed["text"]).strip()
                if "response" in parsed:
                    return str(parsed["response"]).strip()
        except json.JSONDecodeError:
            pass

        return raw_response.strip()

    def invoke(self, prompt: str) -> str:
        conn = self._ensure_connection()
        cursor = conn.cursor(buffered=True)
        try:
            cursor.execute(
                (
                    "SELECT sys.ML_GENERATE(%s, "
                    "JSON_OBJECT('task','generation','model_id',%s,'max_tokens',4000)) "
                    "AS response;"
                ),
                (prompt, self.model_id),
            )
            row = cursor.fetchone()
            raw_response = row[0] if row else ""
            return self._parse_ml_generate_response(raw_response)
        finally:
            try:
                conn.consume_results()
            except Exception:
                pass
            try:
                cursor.close()
            except Exception:
                pass

    def close(self) -> None:
        if self._conn is None:
            return
        try:
            try:
                self._conn.consume_results()
            except Exception:
                pass
            self._conn.close()
        finally:
            self._conn = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
