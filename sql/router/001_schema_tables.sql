-- Core schema and tables for demo.smart_ask and enhancements.

CREATE DATABASE IF NOT EXISTS demo;

CREATE TABLE IF NOT EXISTS demo.ai_router_log (
    id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    asked_at         DATETIME     NOT NULL DEFAULT NOW(),
    question         TEXT         NOT NULL,
    route            VARCHAR(20)  NOT NULL,
    route_confidence DECIMAL(5,2) NULL,
    ambiguity_flag   TINYINT(1)   NOT NULL DEFAULT 0,
    cache_hit        TINYINT(1)   NOT NULL DEFAULT 0,
    sql_generated    TEXT         NULL,
    notes            TEXT         NULL
);

CREATE TABLE IF NOT EXISTS demo.router_schema_hints (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    schema_name    VARCHAR(128) NOT NULL,
    table_name     VARCHAR(128) NOT NULL,
    column_summary TEXT         NULL,
    updated_at     DATETIME     NOT NULL DEFAULT NOW(),
    UNIQUE KEY uq_router_schema_table (schema_name, table_name)
);

CREATE TABLE IF NOT EXISTS demo.ai_router_cache (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    question_hash       CHAR(64)     NOT NULL,
    normalized_question TEXT         NOT NULL,
    route               VARCHAR(20)  NOT NULL,
    answer              LONGTEXT     NOT NULL,
    generated_sql       TEXT         NULL,
    cache_hits          INT UNSIGNED NOT NULL DEFAULT 0,
    last_hit_at         DATETIME     NOT NULL DEFAULT NOW(),
    created_at          DATETIME     NOT NULL DEFAULT NOW(),
    UNIQUE KEY uq_router_question_hash (question_hash)
);

CREATE TABLE IF NOT EXISTS demo.ai_router_feedback (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    router_log_id INT UNSIGNED NOT NULL,
    feedback_type ENUM('up', 'down') NOT NULL,
    feedback_note TEXT NULL,
    created_at    DATETIME NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_router_feedback_log
        FOREIGN KEY (router_log_id)
        REFERENCES demo.ai_router_log(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS demo.ai_router_route_metrics (
    route      VARCHAR(20) PRIMARY KEY,
    up_votes   INT UNSIGNED NOT NULL DEFAULT 0,
    down_votes INT UNSIGNED NOT NULL DEFAULT 0,
    updated_at DATETIME NOT NULL DEFAULT NOW()
);
