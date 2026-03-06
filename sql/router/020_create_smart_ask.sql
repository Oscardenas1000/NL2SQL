CREATE PROCEDURE demo.smart_ask(
    IN  p_question  VARCHAR(2000),
    IN  p_schema_scope_json LONGTEXT,
    OUT p_route     VARCHAR(20),
    OUT p_answer    LONGTEXT
)
SQL SECURITY INVOKER
main_block: BEGIN
    DECLARE v_classify JSON;
    DECLARE v_classify_text VARCHAR(1024) DEFAULT '';
    DECLARE v_route_candidate VARCHAR(20) DEFAULT NULL;
    DECLARE v_conf_text VARCHAR(16) DEFAULT '0';
    DECLARE v_confidence DECIMAL(5,2) DEFAULT 0;
    DECLARE v_ambiguous TINYINT(1) DEFAULT 0;

    DECLARE v_route VARCHAR(20) DEFAULT 'LLM';
    DECLARE v_sql_valid TINYINT DEFAULT 0;
    DECLARE v_sql_query TEXT DEFAULT NULL;
    DECLARE v_rag_text LONGTEXT DEFAULT '';
    DECLARE v_schema_context LONGTEXT DEFAULT '';
    DECLARE v_schema_scope_json JSON DEFAULT NULL;
    DECLARE v_scope_signature TEXT DEFAULT '*';
    DECLARE v_nl_sql_options JSON;

    DECLARE v_log_id INT UNSIGNED DEFAULT NULL;
    DECLARE v_normalized_question TEXT;
    DECLARE v_question_hash CHAR(64);

    DECLARE v_cached_id INT UNSIGNED DEFAULT NULL;
    DECLARE v_cached_route VARCHAR(20) DEFAULT NULL;
    DECLARE v_cached_answer LONGTEXT DEFAULT NULL;
    DECLARE v_cached_sql TEXT DEFAULT NULL;

    SET @smart_ask_log_id = NULL;

    SET v_normalized_question = LOWER(TRIM(REGEXP_REPLACE(p_question, '[[:space:]]+', ' ')));

    IF p_schema_scope_json IS NOT NULL AND JSON_VALID(p_schema_scope_json) THEN
        SET v_schema_scope_json = CAST(p_schema_scope_json AS JSON);
    END IF;

    IF v_schema_scope_json IS NULL OR JSON_LENGTH(v_schema_scope_json) = 0 THEN
        SET v_scope_signature = '*';
        SET v_nl_sql_options = JSON_OBJECT('verbose', 1);
    ELSE
        SET v_scope_signature = CAST(v_schema_scope_json AS CHAR(4096));
        SET v_nl_sql_options = JSON_OBJECT('schemas', v_schema_scope_json, 'verbose', 1);
    END IF;

    SET v_question_hash = SHA2(CONCAT(v_normalized_question, '||scope=', v_scope_signature), 256);

    SELECT c.id, c.route, c.answer, c.generated_sql
      INTO v_cached_id, v_cached_route, v_cached_answer, v_cached_sql
      FROM demo.ai_router_cache AS c
     WHERE c.question_hash = v_question_hash
     LIMIT 1;

    IF v_cached_id IS NOT NULL THEN
        SET p_route = v_cached_route;
        SET p_answer = v_cached_answer;

        INSERT INTO demo.ai_router_log (
            question,
            route,
            route_confidence,
            ambiguity_flag,
            cache_hit,
            sql_generated,
            notes,
            asked_at
        )
        VALUES (
            p_question,
            v_cached_route,
            NULL,
            0,
            1,
            v_cached_sql,
            CONCAT('Served from ai_router_cache (scope=', v_scope_signature, ')'),
            NOW()
        );
        SET v_log_id = LAST_INSERT_ID();
        SET @smart_ask_log_id = v_log_id;

        UPDATE demo.ai_router_cache
           SET cache_hits = cache_hits + 1,
               last_hit_at = NOW()
         WHERE id = v_cached_id;

        LEAVE main_block;
    END IF;

    IF (SELECT COUNT(*) FROM demo.router_schema_hints) = 0 THEN
        CALL demo.refresh_router_schema_hints();
    END IF;

    SELECT LEFT(
               GROUP_CONCAT(
                   CONCAT(
                       h.schema_name, '.', h.table_name,
                       '(', COALESCE(h.column_summary, ''), ')'
                   )
                   SEPARATOR '; '
               ),
               12000
           )
      INTO v_schema_context
      FROM demo.router_schema_hints AS h
     WHERE (
        v_schema_scope_json IS NULL
        OR JSON_LENGTH(v_schema_scope_json) = 0
        OR JSON_CONTAINS(v_schema_scope_json, JSON_QUOTE(h.schema_name), '$')
    );

    SET v_classify = sys.ML_GENERATE(
        CONCAT(
            'Classify this question into exactly one of SQL, RAG, or LLM. ',
            'Return format: ROUTE=<SQL|RAG|LLM>;CONFIDENCE=<0-100>. ',
            'Prefer SQL when answer likely exists in relational tables. ',
            'If the user asks about database contents, available records, or table data, choose SQL. ',
            'Choose LLM for greetings, introductions, opinions, or other conversational prompts that do not ask for stored data. ',
            'Schema context: ', COALESCE(v_schema_context, 'none'), '. ',
            'Question: ', p_question
        ),
        JSON_OBJECT('task', 'generation', 'max_tokens', 40)
    );

    SET v_classify_text = UPPER(COALESCE(JSON_UNQUOTE(JSON_EXTRACT(v_classify, '$.text')), ''));
    SET v_route_candidate = REGEXP_SUBSTR(v_classify_text, 'SQL|RAG|LLM');
    SET v_conf_text = COALESCE(REGEXP_SUBSTR(v_classify_text, '[0-9]{1,3}'), '0');
    SET v_confidence = CAST(v_conf_text AS DECIMAL(5,2));

    IF v_confidence > 100 THEN
        SET v_confidence = 100;
    END IF;

    IF v_route_candidate IS NOT NULL THEN
        SET v_route = v_route_candidate;
    ELSEIF v_classify_text LIKE '%SQL%' THEN
        SET v_route = 'SQL';
    ELSEIF v_classify_text LIKE '%RAG%' THEN
        SET v_route = 'RAG';
    ELSE
        SET v_route = 'LLM';
    END IF;

    SET v_ambiguous = IF(v_confidence < 70, 1, 0);

    INSERT INTO demo.ai_router_log (
        question,
        route,
        route_confidence,
        ambiguity_flag,
        cache_hit,
        asked_at
    )
    VALUES (
        p_question,
        v_route,
        v_confidence,
        v_ambiguous,
        0,
        NOW()
    );
    SET v_log_id = LAST_INSERT_ID();
    SET @smart_ask_log_id = v_log_id;

    IF v_ambiguous = 1 THEN
        CALL sys.NL_SQL(p_question, @smart_ask_nl_meta, v_nl_sql_options);
        SET v_sql_valid = CAST(COALESCE(JSON_UNQUOTE(JSON_EXTRACT(@smart_ask_nl_meta, '$.is_sql_valid')), '0') AS UNSIGNED);
        SET v_sql_query = JSON_UNQUOTE(JSON_EXTRACT(@smart_ask_nl_meta, '$.sql_query'));

        CALL sys.ML_RAG(p_question, @smart_ask_rag_resp, NULL);
        SET v_rag_text = COALESCE(JSON_UNQUOTE(JSON_EXTRACT(@smart_ask_rag_resp, '$.text')), '');

        SET v_route = 'FUSION';
        SET p_route = 'FUSION';
        SET p_answer = JSON_UNQUOTE(
            JSON_EXTRACT(
                sys.ML_GENERATE(
                    CONCAT(
                        'Synthesize a single helpful answer for the question using both SQL and RAG evidence. ',
                        'Question: ', p_question,
                        '\nSQL metadata: ', COALESCE(@smart_ask_nl_meta, '{}'),
                        '\nRAG answer: ', v_rag_text
                    ),
                    JSON_OBJECT('task', 'generation')
                ),
                '$.text'
            )
        );

        UPDATE demo.ai_router_log
           SET route = 'FUSION',
               sql_generated = v_sql_query,
               notes = 'Low-confidence classification; executed multi-route fusion'
         WHERE id = v_log_id;

    ELSEIF v_route = 'SQL' THEN
        CALL sys.NL_SQL(p_question, @smart_ask_nl_meta, v_nl_sql_options);

        SET v_sql_valid = CAST(COALESCE(JSON_UNQUOTE(JSON_EXTRACT(@smart_ask_nl_meta, '$.is_sql_valid')), '0') AS UNSIGNED);
        SET v_sql_query = JSON_UNQUOTE(JSON_EXTRACT(@smart_ask_nl_meta, '$.sql_query'));

        IF v_sql_valid = 1 THEN
            SET p_route = 'SQL';
            SET p_answer = JSON_PRETTY(
                JSON_OBJECT(
                    'route', 'SQL',
                    'generated_sql', v_sql_query,
                    'tables_used', JSON_EXTRACT(@smart_ask_nl_meta, '$.tables'),
                    'model_id', JSON_UNQUOTE(JSON_EXTRACT(@smart_ask_nl_meta, '$.model_id'))
                )
            );

            UPDATE demo.ai_router_log
               SET sql_generated = v_sql_query,
                   notes = 'SQL route executed'
             WHERE id = v_log_id;
        ELSE
            SET v_route = 'LLM_FALLBACK';
            SET p_route = 'LLM_FALLBACK';
            SET p_answer = JSON_UNQUOTE(
                JSON_EXTRACT(
                    sys.ML_GENERATE(p_question, JSON_OBJECT('task', 'generation')),
                    '$.text'
                )
            );

            UPDATE demo.ai_router_log
               SET route = 'LLM_FALLBACK',
                   notes = 'NL_SQL returned is_sql_valid=0; fell back to LLM'
             WHERE id = v_log_id;
        END IF;

    ELSEIF v_route = 'RAG' THEN
        SET p_route = 'RAG';
        CALL sys.ML_RAG(p_question, @smart_ask_rag_resp, NULL);
        SET p_answer = JSON_UNQUOTE(JSON_EXTRACT(@smart_ask_rag_resp, '$.text'));

        UPDATE demo.ai_router_log
           SET notes = 'RAG route executed'
         WHERE id = v_log_id;

    ELSE
        SET p_route = 'LLM';
        SET p_answer = JSON_UNQUOTE(
            JSON_EXTRACT(
                sys.ML_GENERATE(p_question, JSON_OBJECT('task', 'generation')),
                '$.text'
            )
        );

        UPDATE demo.ai_router_log
           SET notes = 'LLM route executed'
         WHERE id = v_log_id;
    END IF;

    INSERT INTO demo.ai_router_cache (
        question_hash,
        normalized_question,
        route,
        answer,
        generated_sql,
        cache_hits,
        last_hit_at,
        created_at
    )
    VALUES (
        v_question_hash,
        v_normalized_question,
        p_route,
        p_answer,
        v_sql_query,
        0,
        NOW(),
        NOW()
    )
    ON DUPLICATE KEY UPDATE
        route = VALUES(route),
        answer = VALUES(answer),
        generated_sql = VALUES(generated_sql),
        last_hit_at = NOW();
END
