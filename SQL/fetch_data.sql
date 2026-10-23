-- sign up 
-- 1. Check user email, userID, phone number, if exist return error
select user_email as user_email,
token_id,
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
   null as token_id,
          'active' as user_status
     from auth.user_profile
    where email = 'demo@user.com'
   union all
   select email as user_email,
   verification_token as token_id,
          'pending' as user_status
     from auth_vw.pending_user_registration_vw pending_user
    where email = 'demo@user.com'
      and not exists (
      select 1
        from auth.user_profile up
       where up.email = pending_user.email
   )
   union all
   select 'demo@user.com' as user_email,
   null as token_id,
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

-- 2. Insert into pending_user_registration_vw, and send email for verification
insert into auth.pending_user_registration(
    id,
    user_id,
    email,
    first_name,
    last_name,
    role_type,
    country_cd,
    phone,
    verification_token,
    expires_at
)
values (
   %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    NOW() + INTERVAL(15) MINUTE
);

ALTER TABLE "pending_user_registration" ALTER COLUMN "expires_at" SET DEFAULT NOW() + INTERVAL '15 minutes';
ALTER TABLE services.token_transaction_log ALTER COLUMN "expires_at" SET DEFAULT now()+interval '14 minutes';
    SELECT NOW() + INTERVAL '15 minutes';





select *
  from auth.user_details;



select active_user.email as active_email,
       active_user.user_id as active_user_id,
       pending_user.email as pending_email,
       pending_user.user_id as pending_user_id
  from auth_vw.pending_user_registration_vw pending_user
  left join auth.user_profile active_user
on active_user.email = pending_user.email
   and active_user.user_id = pending_user.user_id;

INSERT INTO services.token_transaction_log (
    id,
    user_id,
    email,
    token,
    action
)
VALUES (
    %s,
    %s,
    %s,
    %s,
    %s
);


SELECT auth.pending_user_registration 
WHERE email = ''