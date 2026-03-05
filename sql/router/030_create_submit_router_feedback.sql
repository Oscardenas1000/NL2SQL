CREATE PROCEDURE demo.submit_router_feedback(
    IN p_router_log_id INT UNSIGNED,
    IN p_feedback_type VARCHAR(10),
    IN p_feedback_note TEXT
)
SQL SECURITY INVOKER
BEGIN
    DECLARE v_feedback VARCHAR(10);

    SET v_feedback = LOWER(TRIM(p_feedback_type));

    IF v_feedback NOT IN ('up', 'down') THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'feedback_type must be up or down';
    END IF;

    INSERT INTO demo.ai_router_feedback (
        router_log_id,
        feedback_type,
        feedback_note,
        created_at
    )
    VALUES (
        p_router_log_id,
        v_feedback,
        p_feedback_note,
        NOW()
    );
END
