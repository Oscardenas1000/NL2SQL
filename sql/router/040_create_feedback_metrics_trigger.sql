CREATE TRIGGER demo.trg_ai_router_feedback_after_insert
AFTER INSERT ON demo.ai_router_feedback
FOR EACH ROW
BEGIN
    DECLARE v_route VARCHAR(20);

    SELECT l.route INTO v_route
    FROM demo.ai_router_log AS l
    WHERE l.id = NEW.router_log_id
    LIMIT 1;

    IF v_route IS NOT NULL THEN
        INSERT INTO demo.ai_router_route_metrics (
            route,
            up_votes,
            down_votes,
            updated_at
        )
        VALUES (
            v_route,
            IF(NEW.feedback_type = 'up', 1, 0),
            IF(NEW.feedback_type = 'down', 1, 0),
            NOW()
        )
        ON DUPLICATE KEY UPDATE
            up_votes = up_votes + IF(NEW.feedback_type = 'up', 1, 0),
            down_votes = down_votes + IF(NEW.feedback_type = 'down', 1, 0),
            updated_at = NOW();
    END IF;
END
