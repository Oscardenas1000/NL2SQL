# Router SQL Bundle

This folder contains the database objects required by `demo.smart_ask` and enhancement features.

## Files and order

1. `001_schema_tables.sql`
2. `005_drop_routines.sql`
3. `010_create_refresh_schema_hints.sql`
4. `020_create_smart_ask.sql`
5. `030_create_submit_router_feedback.sql`
6. `040_create_feedback_metrics_trigger.sql`

Compatibility note:
- `nl2sql_app.py` performs a runtime migration check for legacy `demo.ai_router_log` layouts and adds missing columns (`route_confidence`, `ambiguity_flag`, `cache_hit`) when needed.

## Enhancement coverage

- Confidence scoring: `demo.smart_ask` stores `route_confidence` and `ambiguity_flag`.
- Schema-aware routing: `demo.router_schema_hints` + `demo.refresh_router_schema_hints`.
- Multi-route fusion: low-confidence branch in `demo.smart_ask` runs `NL_SQL` + `ML_RAG` and synthesizes via `ML_GENERATE`.
- Response caching: `demo.ai_router_cache` used by `demo.smart_ask`.
- User feedback loop: `demo.ai_router_feedback`, `demo.submit_router_feedback`, and route metrics trigger.

## Manual apply example

```sql
SOURCE sql/router/001_schema_tables.sql;
SOURCE sql/router/005_drop_routines.sql;
SOURCE sql/router/010_create_refresh_schema_hints.sql;
SOURCE sql/router/020_create_smart_ask.sql;
SOURCE sql/router/030_create_submit_router_feedback.sql;
SOURCE sql/router/040_create_feedback_metrics_trigger.sql;
CALL demo.refresh_router_schema_hints();
```
