
add_to_otp_log = """insert into services.otp_transaction_log(
                    id,
                    email,
                    user_id,
                    hashed_otp,
                    action,
                    expires_at
                    )
                    values
                    (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    NOW() + INTERVAL '5 MINUTES'
                    );
                    """

check_valid_otp = """
    SELECT 
    hashed_otp,
    action 
    from services_views.otp_transaction_log_vw
    where email = %s and user_id = %s and id = %s and action = %s;
"""

mark_as_used = """
UPDATE services.otp_transaction_log
SET is_used = TRUE, last_used_at = NOW()
WHERE id = %s and user_id = %s;
"""
