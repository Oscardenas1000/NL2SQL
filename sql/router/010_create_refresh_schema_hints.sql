CREATE PROCEDURE demo.refresh_router_schema_hints()
SQL SECURITY INVOKER
BEGIN
    DECLARE prev_group_concat_len BIGINT DEFAULT @@SESSION.group_concat_max_len;

    SET SESSION group_concat_max_len = 16384;

    DELETE FROM demo.router_schema_hints;

    INSERT INTO demo.router_schema_hints (schema_name, table_name, column_summary, updated_at)
    SELECT
        c.table_schema,
        c.table_name,
        LEFT(GROUP_CONCAT(c.column_name ORDER BY c.ordinal_position SEPARATOR ', '), 8000) AS column_summary,
        NOW()
    FROM information_schema.columns AS c
    WHERE c.table_schema NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys', 'demo')
    GROUP BY c.table_schema, c.table_name;

    SET SESSION group_concat_max_len = prev_group_concat_len;
END
