-- Recreate routines/triggers idempotently.

DROP TRIGGER IF EXISTS demo.trg_ai_router_feedback_after_insert;
DROP PROCEDURE IF EXISTS demo.submit_router_feedback;
DROP PROCEDURE IF EXISTS demo.smart_ask;
DROP PROCEDURE IF EXISTS demo.refresh_router_schema_hints;
