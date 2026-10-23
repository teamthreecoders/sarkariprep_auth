
__schema = "services"

fetch_otp = """
SELECT 
user_id,
email,
otp_hash,
purpose,
expire_at
from services.otp_transaction_view
WHERE user_id = %s AND email = %s and purpose = %s and token_id = %s
;
"""

add_to_token_log = lambda exp_interval_min : f"""
INSERT INTO {__schema}.token_transaction_log (
token_id,
user_id,
email,
token,
action,
expires_on
)
VALUES (
    %s,
    %s,
    %s,
    %s,
    %s,
    NOW() + INTERVAL '{exp_interval_min - 1} MINUTES'
);
    """
check_valid_token_for_non_onboarded_user = f"""
SELECT token_id as token_id, action FROM services_views.token_transaction_log_vw token_txn
where token_id = %s and action = %s
and not exists(
SELECT 1 FROM auth_views.user_profile user_profile
where user_profile.email = token_txn.email
)
;
"""

check_valid_token_for_onboarded_user = f"""
SELECT token_id as token_id, action
FROM services_views.token_transaction_log_vw token_txn
INNER JOIN auth_views.user_profile user_profile
ON token_txn.user_id = user_profile.user_id
and user_profile.is_active = true
and user_profile.is_deleted = false
and token_txn.expires_at > current_timestamp
and token_txn.is_token_used = FALSE
where token_txn.token_id::text =  %s 
and token_txn.action = %s
;
"""

mark_as_used = f"""
  UPDATE services.token_transaction_log
   SET is_token_used = true, last_updated_at = now()
  WHERE token_id = %s  ;
"""