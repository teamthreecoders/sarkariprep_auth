# SQL Documentation — Authentication Service

> All queries are parameterised using `%s` placeholders (psycopg2 style).
> Parameters are positional — the order listed in each section is the exact order they are passed to the driver.
> All queries run against **PostgreSQL**.

---

## Table of Contents

1. [Database Object Overview](#1-database-object-overview)
   - [Schemas](#schemas)
   - [Tables](#tables)
   - [Views](#views)
2. [Query Execution Methods](#2-query-execution-methods)
3. [Auth Queries — `CRUD/auth.py`](#3-auth-queries--crudauthpy)
   - [check_user_status](#31-check_user_status)
   - [add_to_pending_user_details](#32-add_to_pending_user_details)
   - [fetch_pending_user_details](#33-fetch_pending_user_details)
   - [final_onboarding](#34-final_onboarding)
   - [setup_new_password](#35-setup_new_password)
   - [get_user_profile_by_email](#36-get_user_profile_by_email)
   - [get_user_profile_by_user_id](#37-get_user_profile_by_user_id)
   - [get_user_profile_by_phone](#38-get_user_profile_by_phone)
   - [reset_password](#39-reset_password)
4. [OTP Queries — `CRUD/otp.py`](#4-otp-queries--crudotppy)
   - [add_to_otp_log](#41-add_to_otp_log)
   - [check_valid_otp](#42-check_valid_otp)
   - [mark_as_used (OTP)](#43-mark_as_used-otp)
5. [Token Queries — `CRUD/token.py`](#5-token-queries--crudtokenpy)
   - [add_to_token_log](#51-add_to_token_log)
   - [check_valid_token](#52-check_valid_token)
   - [check_valid_token_for_registered_user](#53-check_valid_token_for_registered_user)
   - [mark_as_used (Token)](#54-mark_as_used-token)
6. [Query-to-API-Endpoint Map](#6-query-to-api-endpoint-map)

---

## 1. Database Object Overview

### Schemas

| Schema           | Purpose                                              |
|------------------|------------------------------------------------------|
| `auth`           | Core authentication tables (users, security)         |
| `auth_views`     | Read-optimised views over auth tables                |
| `services`       | Transactional log tables (OTP, tokens)               |
| `services_views` | Read-optimised views over services tables (filter out expired/used rows) |

---

### Tables

| Table                              | Schema     | Purpose                                                |
|------------------------------------|------------|--------------------------------------------------------|
| `pending_user_registration`        | `auth`     | Holds new signup data before the user sets a password  |
| `user_details`                     | `auth`     | Core user record after account activation              |
| `security_details`                 | `auth`     | Stores hashed password and security flags per user     |
| `otp_transaction_log`              | `services` | Logs every OTP generated, tracks usage and expiry      |
| `token_transaction_log`            | `services` | Logs every JWT issued, tracks usage and expiry         |

---

### Views

| View                               | Schema           | Underlying Table(s)                             | What it filters                                  |
|------------------------------------|------------------|-------------------------------------------------|--------------------------------------------------|
| `pending_user_registration_vw`     | `auth_views`     | `auth.pending_user_registration`                | Unexpired, unused signup records                 |
| `user_profile`                     | `auth_views`     | `auth.user_details` + `auth.security_details`   | Joined profile with is_active, hashed_password   |
| `otp_transaction_log_vw`           | `services_views` | `services.otp_transaction_log`                  | Non-expired, unused OTP rows                     |
| `token_transaction_log_vw`         | `services_views` | `services.token_transaction_log`                | Non-expired, unused token rows                   |

---

## 2. Query Execution Methods

The `DBConn` class exposes two execution methods:

| Method            | Used for                  | Returns                              |
|-------------------|---------------------------|--------------------------------------|
| `execute_query`   | `SELECT` statements       | `tuple` (fetchone=True) or `list[tuple]` (fetchone=False, max 200 rows) |
| `execute_command` | `INSERT / UPDATE / DELETE` | `int` — number of rows affected     |

> **Exception:** `reset_password` uses `execute_query` despite being an `UPDATE` because it has a `RETURNING` clause that returns a value.

---

## 3. Auth Queries — `CRUD/auth.py`

---

### 3.1 `check_user_status`

| Property        | Value                                            |
|-----------------|--------------------------------------------------|
| **Type**        | `SELECT`                                         |
| **Table/View**  | `auth_views.user_profile`, `auth_views.pending_user_registration_vw` |
| **Executed by** | `UserRepository.check_user_status`               |
| **Called from** | `AuthServices.signup`                            |
| **Returns**     | Single row `(user_email, user_status)`           |
| **Fetch mode**  | `fetchone=True`                                  |

**Purpose:** Determines whether a user trying to sign up already exists. Returns one of three statuses:
- `ACTIVE` — already a registered, active user (block signup → 409)
- `PENDING` — already submitted signup but hasn't set a password yet (allow re-entry)
- `NEW_USER` — never seen before (allow signup)

The query uses `UNION ALL` across three branches and prioritises `ACTIVE > PENDING > NEW_USER` via `ORDER BY` + `FETCH FIRST 1 ROWS ONLY`.

**Parameters (positional):**

| Position | Variable    | Type     | Maps to in SQL                              |
|----------|-------------|----------|---------------------------------------------|
| `%s` #1  | `phone`     | `string` | `WHERE phone = %s` in the ACTIVE branch     |
| `%s` #2  | `email`     | `string` | `OR email = %s` in the ACTIVE branch        |
| `%s` #3  | `email`     | `string` | `WHERE email = %s` in the PENDING branch    |
| `%s` #4  | `email`     | `string` | `SELECT %s AS user_email` in NEW_USER branch|

**SQL:**
```sql
SELECT user_email,
   CASE
      WHEN user_status = 'active'  THEN 'ACTIVE'
      WHEN user_status = 'pending' THEN 'PENDING'
      ELSE                              'NEW_USER'
   END AS user_status
FROM (
    -- Branch 1: Check active users
    SELECT email      AS user_email, 'active'   AS user_status
    FROM auth_views.user_profile
    WHERE phone = %s OR email = %s

    UNION ALL

    -- Branch 2: Check pending (not yet active) signups
    SELECT email      AS user_email, 'pending'  AS user_status
    FROM auth_views.pending_user_registration_vw AS pending_user
    WHERE email = %s
      AND NOT EXISTS (
          SELECT 1
          FROM auth_views.user_profile up
          WHERE up.email = pending_user.email
             OR up.phone = pending_user.phone
      )

    UNION ALL

    -- Branch 3: Fallback — treat as new user
    SELECT %s         AS user_email, 'NEW_USER' AS user_status
)
ORDER BY (
    CASE
        WHEN user_status = 'active'  THEN 1
        WHEN user_status = 'pending' THEN 2
        ELSE                              3
    END
)
FETCH FIRST 1 ROWS ONLY;
```

**Return columns:**

| Column        | Type     | Notes                                      |
|---------------|----------|--------------------------------------------|
| `user_email`  | `string` | The email or phone used in the lookup      |
| `user_status` | `string` | One of: `ACTIVE`, `PENDING`, `NEW_USER`    |

---

### 3.2 `add_to_pending_user_details`

| Property        | Value                                               |
|-----------------|-----------------------------------------------------|
| **Type**        | `INSERT`                                            |
| **Table**       | `auth.pending_user_registration`                    |
| **Executed by** | `UserRepository.add_to_pending_user_details`        |
| **Called from** | `AuthServices.signup`                               |
| **Returns**     | `int` — rows affected (expected: `1`)               |
| **Fetch mode**  | `execute_command`                                   |

**Purpose:** Saves the user's initial signup data into a staging table while they are waiting to set their password. The `token_id` links this row to the JWT sent via email so the record can be retrieved later.

**Parameters (positional):**

| Position | Variable      | Type     | Column inserted into          |
|----------|---------------|----------|-------------------------------|
| `%s` #1  | `uuid`        | `string` | `uuid`                        |
| `%s` #2  | `user_id`     | `string` | `user_id`                     |
| `%s` #3  | `first_name`  | `string` | `first_name`                  |
| `%s` #4  | `last_name`   | `string` | `last_name`                   |
| `%s` #5  | `role_type`   | `string` | `role_type`                   |
| `%s` #6  | `email`       | `string` | `email`                       |
| `%s` #7  | `country_cd`  | `string` | `country_cd`                  |
| `%s` #8  | `phone`       | `string` | `phone`                       |
| `%s` #9  | `token_id`    | `string` | `token_id`                    |

**SQL:**
```sql
INSERT INTO auth.pending_user_registration (
    uuid, user_id, first_name, last_name,
    role_type, email, country_cd, phone, token_id
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
```

---

### 3.3 `fetch_pending_user_details`

| Property        | Value                                              |
|-----------------|----------------------------------------------------|
| **Type**        | `SELECT`                                           |
| **Table/View**  | `auth_views.pending_user_registration_vw`          |
| **Executed by** | `UserRepository.fetch_pending_user_details`        |
| **Called from** | `AuthServices.set_password`                        |
| **Returns**     | Single row of user fields                          |
| **Fetch mode**  | `fetchone=True`                                    |

**Purpose:** Retrieves the staged signup data using the `token_id` from the JWT in the Authorization header. Used at the start of the set-password flow to confirm the pending record exists.

**Parameters (positional):**

| Position | Variable    | Type     | Maps to in SQL               |
|----------|-------------|----------|------------------------------|
| `%s` #1  | `token_id`  | `string` | `WHERE token_id = %s`        |

**SQL:**
```sql
SELECT
    user_id,
    email,
    first_name,
    last_name,
    role_type,
    country_cd,
    phone
FROM auth_views.pending_user_registration_vw AS pending_user
WHERE pending_user.token_id = %s;
```

**Return columns (in order):**

| Position | Column       | Type     |
|----------|--------------|----------|
| 0        | `user_id`    | `string` |
| 1        | `email`      | `string` |
| 2        | `first_name` | `string` |
| 3        | `last_name`  | `string` |
| 4        | `role_type`  | `string` |
| 5        | `country_cd` | `string` |
| 6        | `phone`      | `string` |

---

### 3.4 `final_onboarding`

| Property        | Value                                          |
|-----------------|------------------------------------------------|
| **Type**        | `INSERT`                                       |
| **Table**       | `auth.user_details`                            |
| **Executed by** | `UserRepository.final_onboarding` (Step 1 of 2)|
| **Called from** | `AuthServices.set_password`                    |
| **Returns**     | `int` — rows affected (expected: `1`)          |
| **Fetch mode**  | `execute_command`                              |

**Purpose:** Inserts the user into the main `user_details` table. This is Step 1 of 2 in the final onboarding process — it creates the user record. Step 2 ([`setup_new_password`](#35-setup_new_password)) is only executed if this INSERT succeeds (rows_affected > 0).

**Parameters (positional):**

| Position | Variable     | Type     | Column inserted into |
|----------|--------------|----------|----------------------|
| `%s` #1  | `uuid`       | `string` | `uuid`               |
| `%s` #2  | `user_id`    | `string` | `user_id`            |
| `%s` #3  | `email`      | `string` | `email`              |
| `%s` #4  | `first_name` | `string` | `first_name`         |
| `%s` #5  | `last_name`  | `string` | `last_name`          |
| `%s` #6  | `role_type`  | `string` | `role_type`          |
| `%s` #7  | `country_cd` | `string` | `country_cd`         |
| `%s` #8  | `phone`      | `string` | `phone`              |

**SQL:**
```sql
INSERT INTO auth.user_details (
    uuid, user_id, email,
    first_name, last_name, role_type,
    country_cd, phone
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
```

> **Note:** `is_active`, `is_deleted`, and timestamp columns (`created_at`, `updated_at`) are expected to be handled by column defaults in the table DDL.

---

### 3.5 `setup_new_password`

| Property        | Value                                          |
|-----------------|------------------------------------------------|
| **Type**        | `INSERT`                                       |
| **Table**       | `auth.security_details`                        |
| **Executed by** | `UserRepository.final_onboarding` (Step 2 of 2)|
| **Called from** | `AuthServices.set_password`                    |
| **Returns**     | `int` — rows affected (expected: `1`)          |
| **Fetch mode**  | `execute_command`                              |

**Purpose:** Inserts the user's hashed password and security flags into `security_details`. Always runs immediately after `final_onboarding` succeeds within the same transaction. Both inserts are committed together — if either fails, the whole transaction is rolled back.

**Parameters (positional):**

| Position | Variable           | Type      | Column inserted into   | Notes                              |
|----------|--------------------|-----------|------------------------|------------------------------------|
| `%s` #1  | `uuid`             | `string`  | `uuid`                 | Same UUID used in `final_onboarding` |
| `%s` #2  | `user_id`          | `string`  | `user_id`              |                                    |
| `%s` #3  | `hash_password`    | `string`  | `hashed_password`      | Bcrypt hash of the user's password |
| `%s` #4  | `'True'`           | `string`  | `is_2fa_enabled`       | Hardcoded `'True'` — 2FA on by default |
| `%s` #5  | `'True'`           | `string`  | `is_email_verified`    | Hardcoded `'True'` — email verified at this point |

**SQL:**
```sql
INSERT INTO auth.security_details (
    uuid,
    user_id,
    hashed_password,
    is_2fa_enabled,
    is_email_verified
)
VALUES (%s, %s, %s, %s, %s);
```

> **Important:** `is_2fa_enabled` is hardcoded to `'True'` at onboarding, meaning all new users have 2FA enabled by default.

---

### 3.6 `get_user_profile_by_email`

| Property        | Value                                          |
|-----------------|------------------------------------------------|
| **Type**        | `SELECT`                                       |
| **Table/View**  | `auth_views.user_profile`                      |
| **Executed by** | `UserRepository.get_user_profile_by_email`     |
| **Called from** | `AuthServices.login`, `AuthServices.forgot_password` |
| **Returns**     | Single row with full user profile              |
| **Fetch mode**  | `fetchone=True`                                |

**Purpose:** Fetches a complete user profile using their email address. Used at login and forgot-password to validate the user exists and retrieve their credentials.

**Parameters (positional):**

| Position | Variable | Type     | Maps to in SQL       |
|----------|----------|----------|----------------------|
| `%s` #1  | `email`  | `string` | `WHERE email = %s`   |

**SQL:**
```sql
SELECT
    user_id, email, country_cd, phone,
    first_name, last_name, full_name, role_type,
    is_2fa_enabled, is_email_verified, is_phone_verified,
    hashed_password, is_active
FROM auth_views.user_profile
WHERE email = %s;
```

**Return columns (in order):**

| Position | Column              | Type      |
|----------|---------------------|-----------|
| 0        | `user_id`           | `string`  |
| 1        | `email`             | `string`  |
| 2        | `country_cd`        | `string`  |
| 3        | `phone`             | `string`  |
| 4        | `first_name`        | `string`  |
| 5        | `last_name`         | `string`  |
| 6        | `full_name`         | `string`  |
| 7        | `role_type`         | `string`  |
| 8        | `is_2fa_enabled`    | `boolean` |
| 9        | `is_email_verified` | `boolean` |
| 10       | `is_phone_verified` | `boolean` |
| 11       | `hashed_password`   | `string`  |
| 12       | `is_active`         | `boolean` |

---

### 3.7 `get_user_profile_by_user_id`

| Property        | Value                                             |
|-----------------|---------------------------------------------------|
| **Type**        | `SELECT`                                          |
| **Table/View**  | `auth_views.user_profile`                         |
| **Executed by** | `UserRepository.get_user_profile_by_user_id`      |
| **Called from** | `AuthServices.login`, `AuthServices.forgot_password`, `AuthServices.get_current_user` |
| **Returns**     | Single row with full user profile                 |
| **Fetch mode**  | `fetchone=True`                                   |

**Purpose:** Fetches a complete user profile using their system-assigned `user_id`. Same return shape as [3.6](#36-get_user_profile_by_email).

**Parameters (positional):**

| Position | Variable  | Type     | Maps to in SQL         |
|----------|-----------|----------|------------------------|
| `%s` #1  | `user_id` | `string` | `WHERE user_id = %s`   |

**SQL:**
```sql
SELECT
    user_id, email, country_cd, phone,
    first_name, last_name, full_name, role_type,
    is_2fa_enabled, is_email_verified, is_phone_verified,
    hashed_password, is_active
FROM auth_views.user_profile
WHERE user_id = %s;
```

Return columns are identical to [3.6](#36-get_user_profile_by_email).

---

### 3.8 `get_user_profile_by_phone`

| Property        | Value                                             |
|-----------------|---------------------------------------------------|
| **Type**        | `SELECT`                                          |
| **Table/View**  | `auth_views.user_profile`                         |
| **Executed by** | `UserRepository.get_user_profile_by_phone`        |
| **Called from** | `AuthServices.login`, `AuthServices.forgot_password` |
| **Returns**     | Single row with full user profile                 |
| **Fetch mode**  | `fetchone=True`                                   |

**Purpose:** Fetches a complete user profile by matching both country code and phone number. Both columns are required to avoid cross-country number collisions.

**Parameters (positional):**

| Position | Variable     | Type     | Maps to in SQL              |
|----------|--------------|----------|-----------------------------|
| `%s` #1  | `country_cd` | `string` | `WHERE country_cd = %s`     |
| `%s` #2  | `phone`      | `string` | `AND phone = %s`            |

**SQL:**
```sql
SELECT
    user_id, email, country_cd, phone,
    first_name, last_name, full_name, role_type,
    is_2fa_enabled, is_email_verified, is_phone_verified,
    hashed_password, is_active
FROM auth_views.user_profile
WHERE country_cd = %s AND phone = %s;
```

Return columns are identical to [3.6](#36-get_user_profile_by_email).

---

### 3.9 `reset_password`

| Property        | Value                                          |
|-----------------|------------------------------------------------|
| **Type**        | `UPDATE … RETURNING`                           |
| **Table**       | `auth.security_details` (joined with `auth.user_details`) |
| **Executed by** | `UserRepository.reset_password`                |
| **Called from** | `AuthServices.reset_password`                  |
| **Returns**     | Single row `(last_updated,)`                   |
| **Fetch mode**  | `execute_query` + `fetchone=True`              |

**Purpose:** Updates the stored hashed password for a user, verified by matching both `user_id` and `email`. Uses an implicit JOIN between `security_details` and `user_details` via `uuid` to ensure only active, non-deleted accounts are updated. Returns the `last_updated` timestamp on success, `None` if no row was matched.

**Parameters (positional):**

| Position | Variable          | Type     | Maps to in SQL                    |
|----------|-------------------|----------|-----------------------------------|
| `%s` #1  | `hashed_password` | `string` | `SET hashed_password = %s`        |
| `%s` #2  | `user_id`         | `string` | `AND u.user_id = sd.user_id AND u.user_id = %s` |
| `%s` #3  | `email`           | `string` | `AND u.email = %s`                |

**SQL:**
```sql
UPDATE auth.security_details sd
SET hashed_password = %s, last_updated = NOW()
FROM auth.user_details u
WHERE
    u.uuid::text      = sd.uuid::text
    AND u.is_active   = TRUE
    AND u.is_deleted  = FALSE
    AND u.user_id     = sd.user_id
    AND u.user_id     = %s
    AND u.email       = %s
RETURNING sd.last_updated;
```

**Return columns:**

| Position | Column         | Type        | Notes                              |
|----------|----------------|-------------|------------------------------------|
| 0        | `last_updated` | `timestamp` | Time the password was changed      |

> **Note:** Uses `execute_query` (not `execute_command`) because of the `RETURNING` clause. Returns `None` if no matching active user was found — the service treats this as a failure.

---

## 4. OTP Queries — `CRUD/otp.py`

---

### 4.1 `add_to_otp_log`

| Property        | Value                                         |
|-----------------|-----------------------------------------------|
| **Type**        | `INSERT`                                      |
| **Table**       | `services.otp_transaction_log`                |
| **Executed by** | `OTPRepository.add_to_otp_log`                |
| **Called from** | `OTPServices.create_for_twoFactorAuth`        |
| **Returns**     | `int` — rows affected (expected: `1`)         |
| **Fetch mode**  | `execute_command`                             |

**Purpose:** Records a newly generated OTP in the transaction log. The OTP is stored **hashed** (never plain-text). Expiry is set to `NOW() + 5 MINUTES` by the database at insert time.

**Parameters (positional):**

| Position | Variable     | Type     | Column inserted into | Notes                           |
|----------|--------------|----------|----------------------|---------------------------------|
| `%s` #1  | `otp_id`     | `string` | `id`                 | UUID for this OTP transaction   |
| `%s` #2  | `email`      | `string` | `email`              |                                 |
| `%s` #3  | `user_id`    | `string` | `user_id`            |                                 |
| `%s` #4  | `hashed_otp` | `string` | `hashed_otp`         | Bcrypt hash of the raw OTP      |
| `%s` #5  | `purpose`    | `string` | `action`             | e.g. `LOGIN_2FA_OTP`            |

**SQL:**
```sql
INSERT INTO services.otp_transaction_log (
    id,
    email,
    user_id,
    hashed_otp,
    action,
    expires_at
)
VALUES (
    %s,
    %s,
    %s,
    %s,
    %s,
    NOW() + INTERVAL '5 MINUTES'
);
```

> **Note:** `expires_at` is computed server-side as `NOW() + INTERVAL '5 MINUTES'`. The application layer communicates "15 minutes" to the user in the email, but the DB enforces 5 minutes. Verify and align these values.

---

### 4.2 `check_valid_otp`

| Property        | Value                                         |
|-----------------|-----------------------------------------------|
| **Type**        | `SELECT`                                      |
| **Table/View**  | `services_views.otp_transaction_log_vw`       |
| **Executed by** | `OTPRepository.check_valid_otp`               |
| **Called from** | `OTPServices.verify_otp`                      |
| **Returns**     | Single row `(hashed_otp, action)`             |
| **Fetch mode**  | `fetchone=True`                               |

**Purpose:** Checks whether a valid (unexpired, unused) OTP record exists for the given user and transaction. The view already filters out expired and used rows — if this returns `None`, the OTP is either wrong, expired, or already used. The application then does a hash comparison on `hashed_otp` to verify the entered OTP.

**Parameters (positional):**

| Position | Variable  | Type     | Maps to in SQL          |
|----------|-----------|----------|-------------------------|
| `%s` #1  | `email`   | `string` | `WHERE email = %s`      |
| `%s` #2  | `user_id` | `string` | `AND user_id = %s`      |
| `%s` #3  | `otp_id`  | `string` | `AND id = %s`           |
| `%s` #4  | `purpose` | `string` | `AND action = %s`       |

**SQL:**
```sql
SELECT
    hashed_otp,
    action
FROM services_views.otp_transaction_log_vw
WHERE email    = %s
  AND user_id  = %s
  AND id       = %s
  AND action   = %s;
```

**Return columns:**

| Position | Column       | Type     | Notes                                              |
|----------|--------------|----------|----------------------------------------------------|
| 0        | `hashed_otp` | `string` | Compared against the entered OTP via bcrypt verify |
| 1        | `action`     | `string` | OTP purpose, e.g. `LOGIN_2FA_OTP`                  |

---

### 4.3 `mark_as_used` (OTP)

| Property        | Value                                         |
|-----------------|-----------------------------------------------|
| **Type**        | `UPDATE`                                      |
| **Table**       | `services.otp_transaction_log`                |
| **Executed by** | `OTPRepository.mark_as_used`                  |
| **Called from** | `OTPServices.verify_otp`                      |
| **Returns**     | `int` — rows affected (expected: `1`)         |
| **Fetch mode**  | `execute_command`                             |

**Purpose:** Marks the OTP as consumed after successful verification. Sets `is_used = TRUE` and stamps `last_used_at`. Prevents OTP replay attacks — the view (`otp_transaction_log_vw`) excludes rows where `is_used = TRUE`.

**Parameters (positional):**

| Position | Variable  | Type     | Maps to in SQL         |
|----------|-----------|----------|------------------------|
| `%s` #1  | `otp_id`  | `string` | `WHERE id = %s`        |
| `%s` #2  | `user_id` | `string` | `AND user_id = %s`     |

**SQL:**
```sql
UPDATE services.otp_transaction_log
SET
    is_used      = TRUE,
    last_used_at = NOW()
WHERE id      = %s
  AND user_id = %s;
```

---

## 5. Token Queries — `CRUD/token.py`

---

### 5.1 `add_to_token_log`

| Property        | Value                                          |
|-----------------|------------------------------------------------|
| **Type**        | `INSERT`                                       |
| **Table**       | `services.token_transaction_log`               |
| **Executed by** | `TokenRepository.add_to_token_log`             |
| **Called from** | `AccessTokenService` (every token creation)    |
| **Returns**     | `int` — rows affected (expected: `1`)          |
| **Fetch mode**  | `execute_command`                              |

**Purpose:** Persists every issued JWT to the database so it can be validated and revoked. The `action` field stores the token's purpose (e.g. `LOGIN_SESSION`, `SIGN_UP`, `PASSWORD_RESET`), which is used during validation to ensure a token is only used for its intended endpoint.

**Parameters (positional):**

| Position | Variable   | Type     | Column inserted into | Notes                                    |
|----------|------------|----------|----------------------|------------------------------------------|
| `%s` #1  | `token_id` | `string` | `token_id`           | UUID embedded in the JWT payload         |
| `%s` #2  | `user_id`  | `string` | `user_id`            |                                          |
| `%s` #3  | `email`    | `string` | `email`              |                                          |
| `%s` #4  | `token`    | `string` | `token`              | The full signed JWT string               |
| `%s` #5  | `purpose`  | `string` | `action`             | One of the `AllowedTokenPurpose` values  |

**SQL:**
```sql
INSERT INTO services.token_transaction_log (
    token_id,
    user_id,
    email,
    token,
    action
)
VALUES (%s, %s, %s, %s, %s);
```

---

### 5.2 `check_valid_token`

| Property        | Value                                                  |
|-----------------|--------------------------------------------------------|
| **Type**        | `SELECT`                                               |
| **Table/View**  | `services_views.token_transaction_log_vw`              |
| **Executed by** | `TokenRepository.check_valid_token`                    |
| **Called from** | `AccessTokenService.validate_token` — **only for `SIGN_UP` purpose** |
| **Returns**     | Single row `(token_id, action)`                        |
| **Fetch mode**  | `fetchone=True`                                        |

**Purpose:** Validates a token for pending (not-yet-registered) users. Used specifically during the signup set-password step, where the user doesn't yet have an active account in `user_details`. The view filters out expired and used tokens. Unlike [5.3](#53-check_valid_token_for_registered_user), it does **not** join to `user_profile`.

**Parameters (positional):**

| Position | Variable   | Type     | Maps to in SQL          |
|----------|------------|----------|-------------------------|
| `%s` #1  | `token_id` | `string` | `WHERE token_id = %s`   |
| `%s` #2  | `purpose`  | `string` | `AND action = %s`       |

**SQL:**
```sql
SELECT token_id, action
FROM services_views.token_transaction_log_vw
WHERE token_id = %s
  AND action   = %s;
```

**Return columns:**

| Position | Column     | Type     | Notes                              |
|----------|------------|----------|------------------------------------|
| 0        | `token_id` | `string` | Confirmed valid token ID           |
| 1        | `action`   | `string` | Confirmed purpose of the token     |

---

### 5.3 `check_valid_token_for_registered_user`

| Property        | Value                                                         |
|-----------------|---------------------------------------------------------------|
| **Type**        | `SELECT` with `INNER JOIN`                                    |
| **Table/View**  | `services_views.token_transaction_log_vw` + `auth_views.user_profile` |
| **Executed by** | `TokenRepository.check_valid_token`                           |
| **Called from** | `AccessTokenService.validate_token` — **for all purposes except `SIGN_UP`** |
| **Returns**     | Single row `(token_id, action)`                               |
| **Fetch mode**  | `fetchone=True`                                               |

**Purpose:** Validates a token for already-registered, active users. In addition to the view-level expiry/used checks, this query explicitly re-checks in the JOIN conditions that the token is unexpired (`expires_at > current_timestamp`) and unused (`is_token_used = FALSE`), and that the linked user is active and not deleted. Used for `LOGIN_SESSION`, `PASSWORD_RESET`, `LOGIN_2FA_OTP`, and `LOGIN_2FA_MAGIC_URL`.

**Parameters (positional):**

| Position | Variable   | Type     | Maps to in SQL                          |
|----------|------------|----------|-----------------------------------------|
| `%s` #1  | `token_id` | `string` | `WHERE token_txn.token_id::text = %s`   |
| `%s` #2  | `purpose`  | `string` | `AND token_txn.action = %s`             |

**SQL:**
```sql
SELECT
    token_txn.token_id,
    token_txn.action
FROM services_views.token_transaction_log_vw AS token_txn
INNER JOIN auth_views.user_profile AS user_profile
    ON  token_txn.user_id             = user_profile.user_id
    AND user_profile.is_active        = TRUE
    AND user_profile.is_deleted       = FALSE
    AND token_txn.expires_at          > CURRENT_TIMESTAMP
    AND token_txn.is_token_used       = FALSE
WHERE token_txn.token_id::text = %s
  AND token_txn.action         = %s;
```

**Return columns:**

| Position | Column     | Type     | Notes                          |
|----------|------------|----------|--------------------------------|
| 0        | `token_id` | `string` | Confirmed valid token ID       |
| 1        | `action`   | `string` | Confirmed purpose of the token |

---

### 5.4 `mark_as_used` (Token)

| Property        | Value                                          |
|-----------------|------------------------------------------------|
| **Type**        | `UPDATE`                                       |
| **Table**       | `services.token_transaction_log`               |
| **Executed by** | `TokenRepository.update_token_log`             |
| **Called from** | `AccessTokenService.mark_token_as_used`        |
| **Returns**     | `int` — rows affected (expected: `1`)          |
| **Fetch mode**  | `execute_command`                              |

**Purpose:** Marks a JWT as consumed after it has been used. Sets `is_token_used = TRUE` and stamps `last_updated_at`. Prevents token replay — the view (`token_transaction_log_vw`) and the JOIN in [5.3](#53-check_valid_token_for_registered_user) both exclude rows where `is_token_used = TRUE`. Called after:
- Successful set-password (consumes the SIGN_UP token)
- Successful reset-password (consumes the PASSWORD_RESET token)

**Parameters (positional):**

| Position | Variable   | Type     | Maps to in SQL         |
|----------|------------|----------|------------------------|
| `%s` #1  | `token_id` | `string` | `WHERE token_id = %s`  |

**SQL:**
```sql
UPDATE services.token_transaction_log
SET
    is_token_used    = TRUE,
    last_updated_at  = NOW()
WHERE token_id = %s;
```

---

## 6. Query-to-API-Endpoint Map

| API Endpoint                        | Queries Executed (in order)                                                                                 |
|-------------------------------------|-------------------------------------------------------------------------------------------------------------|
| `POST /v1/auth/signup`              | `check_user_status` → `add_to_pending_user_details` → `add_to_token_log`                                    |
| `POST /v1/auth/signup/set-password` | `check_valid_token` → `fetch_pending_user_details` → `final_onboarding` → `setup_new_password` → `mark_as_used (token)` |
| `POST /v1/auth/otp/login`           | `get_user_profile_by_*` → `add_to_token_log` (session or challenge token) → `add_to_otp_log` (if 2FA)      |
| `POST /v1/auth/otp/login/2fa_verify`| `check_valid_otp` → `mark_as_used (OTP)` → `add_to_token_log` (session token)                              |
| `POST /v1/auth/forgot-password`     | `get_user_profile_by_*` → `add_to_token_log`                                                                |
| `POST /v1/auth/reset-password`      | `check_valid_token_for_registered_user` → `reset_password` → `mark_as_used (token)`                         |
| `POST /v1/auth/me`                  | `check_valid_token_for_registered_user` → `get_user_profile_by_user_id`                                     |
| `DELETE /v1/auth/logout`            | No DB query — only clears the cookie                                                                        |
