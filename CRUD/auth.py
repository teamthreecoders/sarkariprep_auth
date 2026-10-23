
__table_schema = "auth"
__view_schema = "auth_views"

check_user_status =  f"""
select user_email as user_email,
   case
      when user_status = 'active'  then
         'ACTIVE'
      when user_status = 'pending' then
         'PENDING'
      else
         'NEW_USER'
   end as user_status
from (
select email as user_email,
      'active' as user_status
 from auth_views.user_profile
where  phone = %s or email = %s
union all
select email as user_email,
      'pending' as user_status
 from auth_views.pending_user_registration_vw pending_user
where email = %s
  and not exists (
  select 1
    from auth_views.user_profile up
   where (up.email = pending_user.email) or (up.phone = pending_user.phone)
)
union all
select %s as user_email,
      'NEW_USER' as user_status
)
order by (
case
  when user_status = 'active'  then
     1
  when user_status = 'pending' then
     2
  else
     3
end
)
fetch first 1 rows only;
"""

add_to_pending_user_details:str = f"""
INSERT INTO {__table_schema}.pending_user_registration 
(
uuid,user_id,first_name,last_name,role_type,email,country_cd,phone,token_id
)
VALUES 
( 
%s,%s, %s, %s, %s, %s, %s, %s, %s
);
"""

fetch_pending_user_details = f"""
SELECT 
user_id,
email,
first_name,
last_name,
role_type,
country_cd,
phone
FROM auth_views.pending_user_registration_vw as pending_user
WHERE pending_user.token_id = %s
;
"""

final_onboarding:str = f"""
INSERT INTO {__table_schema}.user_details (
   uuid,
    user_id,
    email,
    first_name,
    last_name,
    role_type,
    country_cd,
    phone
)
values (
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s
);
"""
setup_new_password = f"""
INSERT INTO {__table_schema}.security_details (
    uuid,
    user_id,
    hashed_password,
    is_2fa_enabled,
    is_email_verified
)
values (
    %s,
    %s,
    %s,
    %s,
    %s
);
"""

__BASE_QUERY_get_user_profile = """
SELECT user_id,
email,
country_cd,
phone,
first_name,
last_name,
full_name,
role_type,
is_2fa_enabled,
is_email_verified,
is_phone_verified,
hashed_password,
is_active
FROM auth_views.user_profile
"""

get_user_profile_by_email = f"""
{__BASE_QUERY_get_user_profile}
WHERE email = %s
"""

get_user_profile_by_user_id = f"""
{__BASE_QUERY_get_user_profile}
WHERE user_id = %s
"""

get_user_profile_by_phone = f"""
{__BASE_QUERY_get_user_profile}
WHERE country_cd= %s and phone = %s
"""


reset_password = """
UPDATE auth.security_details sd
SET hashed_password = %s , last_updated = NOW()
FROM auth.user_details u
WHERE
    u.uuid::text = sd.uuid::text
    AND u.is_active = TRUE
    AND u.is_deleted = FALSE
    AND u.user_id = sd.user_id
    AND u.user_id = %s
    AND u.email = %s
RETURNING  sd.last_updated
;
    """

mark_pending_as_used = """
UPDATE auth.pending_user_registration
SET is_token_used = TRUE, last_updated_at = NOW()
WHERE token_id = %s;
"""
