# Database Design Documentation — Authentication Service

---

## Table of Contents

1. [Database & Driver Info](#1-database--driver-info)
2. [Schema Overview](#2-schema-overview)
3. [Entity Relationship Diagram](#3-entity-relationship-diagram)
4. [Tables](#4-tables)
   - [auth.user_details](#41-authuser_details)
   - [auth.pending_user_registration](#42-authpending_user_registration)
   - [auth.security_details](#43-authsecurity_details)
   - [services.otp_transaction_log](#44-servicesotp_transaction_log)
   - [services.token_transaction_log](#45-servicestoken_transaction_log)
5. [Views](#5-views)
   - [auth_views.pending_user_registration_vw](#51-auth_viewspending_user_registration_vw)
   - [auth_views.user_profile](#52-auth_viewsuser_profile)
   - [services_views.otp_transaction_log_vw](#53-services_viewsotp_transaction_log_vw)
   - [services_views.token_transaction_log_vw](#54-services_viewstoken_transaction_log_vw)
6. [Constraints & Indexes Summary](#6-constraints--indexes-summary)
7. [Design Notes](#7-design-notes)

---

## 1. Database & Driver Info

| Property              | Value                                                        |
|-----------------------|--------------------------------------------------------------|
| **Database**          | PostgreSQL (hosted on **NeonDB** — Serverless PostgreSQL)    |
| **DB Owner**          | `neondb_owner`                                               |
| **Python Driver**     | `psycopg2-binary >= 2.9.10`                                  |
| **Tablespace**        | `pg_default`                                                 |
| **Connection**        | Configured via environment variables (`PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, `PGCONNURL`) |
| **SSL Mode**          | Configured via `PGSSLMODE` env var                           |
| **Connect Timeout**   | 10 seconds                                                   |
| **Collation**         | `pg_catalog."default"` on all `character varying` columns    |

> **NeonDB** is a serverless PostgreSQL platform. The database behaves as standard PostgreSQL — all standard SQL, constraints, indexes, and views apply.

---

## 2. Schema Overview

The database is split into **4 schemas** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│  auth                  (Core user data)                  │
│  ├── user_details                                        │
│  ├── pending_user_registration                           │
│  └── security_details                                    │
├─────────────────────────────────────────────────────────┤
│  auth_views            (Read-optimised views over auth)  │
│  ├── user_profile                                        │
│  └── pending_user_registration_vw                        │
├─────────────────────────────────────────────────────────┤
│  services              (Transactional logs)              │
│  ├── otp_transaction_log                                 │
│  └── token_transaction_log                               │
├─────────────────────────────────────────────────────────┤
│  services_views        (Read-optimised views over logs)  │
│  ├── otp_transaction_log_vw                              │
│  └── token_transaction_log_vw                            │
└─────────────────────────────────────────────────────────┘
```

| Schema           | Type   | Purpose                                                         |
|------------------|--------|-----------------------------------------------------------------|
| `auth`           | Tables | Stores permanent user identity and credential data              |
| `auth_views`     | Views  | Pre-joined, filtered views for safe reading — used by all SELECT queries |
| `services`       | Tables | Append-heavy transaction logs for OTPs and JWT tokens           |
| `services_views` | Views  | Filter logs down to only active (unexpired, unused) rows        |

---

## 3. Entity Relationship Diagram

```
auth.pending_user_registration
┌──────────────────────────────┐
│ uuid (PK)                    │
│ user_id                      │
│ email                        │          auth.user_details
│ first_name                   │          ┌──────────────────────────────┐
│ last_name                    │          │ uuid (PK)                    │
│ role_type                    │          │ user_id (UNIQUE)  ◄──────────┼──┐
│ country_cd                   │          │ email (UNIQUE)               │  │
│ phone                        │          │ first_name                   │  │
│ token_id                     │          │ last_name                    │  │
│ expires_at                   │          │ role_type                    │  │
│ created_at                   │          │ country_cd                   │  │
│ last_updated_at              │          │ phone (UNIQUE)               │  │
│ is_token_used                │          │ create_ts                    │  │
└──────────────────────────────┘          │ last_updated_ts              │  │
         (no FK — linked                  │ is_active                    │  │
          via token_id to                 │ is_deleted                   │  │
          token_transaction_log)          └──────────────────────────────┘  │
                                                        │ uuid + user_id    │
                                                        │                   │
                                          auth.security_details             │
                                          ┌──────────────────────────────┐  │
                                          │ uuid                         │  │
                                          │ user_id (FK) ────────────────┼──┘
                                          │ hashed_password              │
                                          │ is_2fa_enabled               │
                                          │ is_email_verified            │
                                          │ is_phone_verified            │
                                          │ create_at                    │
                                          │ last_updated                 │
                                          └──────────────────────────────┘

services.otp_transaction_log              services.token_transaction_log
┌──────────────────────────────┐          ┌──────────────────────────────┐
│ id (PK)                      │          │ token_id (PK)                │
│ email                        │          │ user_id                      │
│ user_id                      │          │ email                        │
│ hashed_otp                   │          │ token                        │
│ action                       │          │ action                       │
│ created_at                   │          │ is_token_used                │
│ is_used                      │          │ expires_at                   │
│ last_used_at                 │          │ created_at                   │
│ expires_at                   │          │ last_updated_at              │
└──────────────────────────────┘          └──────────────────────────────┘
  (no FK — user_id is a soft                (no FK — user_id is a soft
   reference, log is independent)            reference, log is independent)
```

> `services` tables do **not** have foreign keys to `auth` tables. They are independent transaction logs linked only by `user_id` and `email` as soft references. This keeps them append-safe even if a user record changes.

---

## 4. Tables

---

### 4.1 `auth.user_details`

**Purpose:** The primary user record. Created when a user completes the set-password step. This is the source of truth for user identity.

| Column            | Data Type                      | Nullable | Default        | Notes                                 |
|-------------------|--------------------------------|----------|----------------|---------------------------------------|
| `uuid`            | `uuid`                         | NOT NULL | —              | **Primary Key**                       |
| `user_id`         | `varchar(50)`                  | NOT NULL | —              | Unique, application-generated ID (e.g. `AY12345678`) |
| `first_name`      | `varchar(255)`                 | NOT NULL | —              |                                       |
| `last_name`       | `varchar(255)`                 | NULL     | —              |                                       |
| `role_type`       | `varchar(255)`                 | NOT NULL | `'user'`       | One of: `user`, `admin`, `guest`, `other` |
| `email`           | `varchar(255)`                 | NOT NULL | —              | Unique                                |
| `country_cd`      | `varchar(4)`                   | NOT NULL | —              | E.g. `+91`, `+44`                     |
| `phone`           | `varchar(255)`                 | NOT NULL | —              | Unique                                |
| `create_ts`       | `timestamp with time zone`     | NOT NULL | `now()`        | Record creation timestamp             |
| `last_updated_ts` | `timestamp with time zone`     | NOT NULL | `now()`        | Last modification timestamp           |
| `is_active`       | `boolean`                      | NOT NULL | `true`         | Soft-active flag; `false` = deactivated user |
| `is_deleted`      | `boolean`                      | NOT NULL | `false`        | Soft-delete flag; never hard-deleted  |

**Constraints:**

| Constraint Name               | Type        | Column(s)  |
|-------------------------------|-------------|------------|
| `user_details_pkey`           | PRIMARY KEY | `uuid`     |
| `user_details_email_key`      | UNIQUE      | `email`    |
| `user_details_phone_key`      | UNIQUE      | `phone`    |
| `user_details_user_id_key`    | UNIQUE      | `user_id`  |

**Indexes:**

| Index Name       | Type   | Column  | Order              |
|------------------|--------|---------|--------------------|
| `idx_user_email` | BTree  | `email` | ASC NULLS LAST     |
| `idx_user_phone` | BTree  | `phone` | ASC NULLS LAST     |

**DDL:**
```sql
CREATE TABLE IF NOT EXISTS auth.user_details
(
    uuid              uuid                        NOT NULL,
    user_id           character varying(50)       NOT NULL,
    first_name        character varying(255)      NOT NULL,
    last_name         character varying(255),
    role_type         character varying(255)      NOT NULL  DEFAULT 'user'::character varying,
    email             character varying(255)      NOT NULL,
    country_cd        character varying(4)        NOT NULL,
    phone             character varying(255)      NOT NULL,
    create_ts         timestamp with time zone    NOT NULL  DEFAULT now(),
    last_updated_ts   timestamp with time zone    NOT NULL  DEFAULT now(),
    is_active         boolean                     NOT NULL  DEFAULT true,
    is_deleted        boolean                     NOT NULL  DEFAULT false,
    CONSTRAINT user_details_pkey        PRIMARY KEY (uuid),
    CONSTRAINT user_details_email_key   UNIQUE (email),
    CONSTRAINT user_details_phone_key   UNIQUE (phone),
    CONSTRAINT user_details_user_id_key UNIQUE (user_id)
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_user_email
    ON auth.user_details USING btree (email ASC NULLS LAST) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_user_phone
    ON auth.user_details USING btree (phone ASC NULLS LAST) TABLESPACE pg_default;
```

---

### 4.2 `auth.pending_user_registration`

**Purpose:** Staging table for new signups. A row is inserted when `/v1/auth/signup` is called. The row is consumed (via the view filter) during `/v1/auth/signup/set-password`. Records expire after **15 minutes** if the user doesn't complete the flow. No FK to `user_details` — the user does not exist there yet.

| Column            | Data Type                      | Nullable | Default                          | Notes                                              |
|-------------------|--------------------------------|----------|----------------------------------|----------------------------------------------------|
| `uuid`            | `uuid`                         | NOT NULL | —                                | **Primary Key**                                    |
| `user_id`         | `varchar(30)`                  | NOT NULL | —                                | Pre-assigned user ID (same as in signup request)   |
| `email`           | `varchar(255)`                 | NOT NULL | —                                |                                                    |
| `first_name`      | `varchar(100)`                 | NOT NULL | —                                |                                                    |
| `last_name`       | `varchar(100)`                 | NOT NULL | —                                |                                                    |
| `role_type`       | `varchar(30)`                  | NOT NULL | —                                |                                                    |
| `country_cd`      | `varchar(10)`                  | NULL     | —                                |                                                    |
| `phone`           | `varchar(20)`                  | NULL     | —                                |                                                    |
| `token_id`        | `text`                         | NOT NULL | —                                | Links to the SIGN_UP JWT sent via email            |
| `expires_at`      | `timestamp with time zone`     | NULL     | `now() + interval '15 minutes'`  | Row becomes invisible to the view after this time  |
| `created_at`      | `timestamp with time zone`     | NULL     | `now()`                          |                                                    |
| `last_updated_at` | `timestamp with time zone`     | NOT NULL | `now()`                          |                                                    |
| `is_token_used`   | `boolean`                      | NULL     | `false`                          | Set to `true` after set-password completes         |

**Constraints:**

| Constraint Name                       | Type        | Column(s) |
|---------------------------------------|-------------|-----------|
| `pending_user_registration_pkey`      | PRIMARY KEY | `uuid`    |

**DDL:**
```sql
CREATE TABLE IF NOT EXISTS auth.pending_user_registration
(
    uuid              uuid                        NOT NULL,
    user_id           character varying(30)       NOT NULL,
    email             character varying(255)      NOT NULL,
    first_name        character varying(100)      NOT NULL,
    last_name         character varying(100)      NOT NULL,
    role_type         character varying(30)       NOT NULL,
    country_cd        character varying(10),
    phone             character varying(20),
    token_id          text                        NOT NULL,
    expires_at        timestamp with time zone              DEFAULT (now() + '00:15:00'::interval),
    created_at        timestamp with time zone              DEFAULT now(),
    last_updated_at   timestamp with time zone    NOT NULL  DEFAULT now(),
    is_token_used     boolean                               DEFAULT false,
    CONSTRAINT pending_user_registration_pkey PRIMARY KEY (uuid)
) TABLESPACE pg_default;
```

---

### 4.3 `auth.security_details`

**Purpose:** Stores credentials and security flags for every active user. Has a **cascading FK** to `auth.user_details` via `user_id` — deleting a user cascades to this table. Joined with `user_details` in the `user_profile` view.

| Column              | Data Type                      | Nullable | Default  | Notes                                              |
|---------------------|--------------------------------|----------|----------|----------------------------------------------------|
| `uuid`              | `uuid`                         | NOT NULL | —        | Matches `uuid` in `user_details`                   |
| `user_id`           | `varchar(50)`                  | NULL     | —        | **FK → `auth.user_details(user_id)`** (CASCADE UPDATE/DELETE) |
| `hashed_password`   | `varchar(255)`                 | NULL     | —        | Bcrypt / Argon2 hash of the user's password        |
| `is_2fa_enabled`    | `boolean`                      | NOT NULL | `false`  | Hardcoded `true` at onboarding (app-level override)|
| `is_email_verified` | `boolean`                      | NOT NULL | `false`  | Set `true` during set-password onboarding          |
| `is_phone_verified` | `boolean`                      | NOT NULL | `false`  | Not yet implemented in application layer           |
| `create_at`         | `timestamp with time zone`     | NOT NULL | `now()`  |                                                    |
| `last_updated`      | `timestamp with time zone`     | NOT NULL | `now()`  | Updated by the `reset_password` query              |

**Constraints:**

| Constraint Name                   | Type        | Column(s)  | References                      | On Update | On Delete |
|-----------------------------------|-------------|------------|---------------------------------|-----------|-----------|
| *(none — no explicit PK)*         | —           | —          | —                               | —         | —         |
| `security_details_user_id_fkey`   | FOREIGN KEY | `user_id`  | `auth.user_details(user_id)`    | CASCADE   | CASCADE   |

> **Note:** `security_details` has no primary key defined in the DDL. The row is identified by `uuid` + `user_id` in application queries.

**DDL:**
```sql
CREATE TABLE IF NOT EXISTS auth.security_details
(
    uuid               uuid                        NOT NULL,
    user_id            character varying(50),
    hashed_password    character varying(255),
    is_2fa_enabled     boolean                     NOT NULL  DEFAULT false,
    is_email_verified  boolean                     NOT NULL  DEFAULT false,
    is_phone_verified  boolean                     NOT NULL  DEFAULT false,
    create_at          timestamp with time zone    NOT NULL  DEFAULT now(),
    last_updated       timestamp with time zone    NOT NULL  DEFAULT now(),
    CONSTRAINT security_details_user_id_fkey FOREIGN KEY (user_id)
        REFERENCES auth.user_details (user_id) MATCH SIMPLE
        ON UPDATE CASCADE
        ON DELETE CASCADE
) TABLESPACE pg_default;
```

---

### 4.4 `services.otp_transaction_log`

**Purpose:** Append-only log of every OTP generated. Each row represents one OTP transaction. The OTP itself is **never stored in plain text** — only its hash. Rows expire after **15 minutes** by default. No FK to user tables — designed to remain intact even if user data changes.

| Column        | Data Type                      | Nullable | Default                           | Notes                                              |
|---------------|--------------------------------|----------|-----------------------------------|----------------------------------------------------|
| `id`          | `uuid`                         | NOT NULL | `gen_random_uuid()`               | **Primary Key** — also used as `otp_id` in app    |
| `email`       | `varchar(255)`                 | NOT NULL | —                                 |                                                    |
| `user_id`     | `varchar(255)`                 | NOT NULL | —                                 | Soft reference — no FK                             |
| `hashed_otp`  | `varchar(255)`                 | NOT NULL | —                                 | Bcrypt / Argon2 hash of the raw 4-digit OTP        |
| `action`      | `varchar(255)`                 | NOT NULL | —                                 | OTP purpose, e.g. `LOGIN_2FA_OTP`                  |
| `created_at`  | `timestamp with time zone`     | NOT NULL | `now()`                           |                                                    |
| `is_used`     | `boolean`                      | NOT NULL | `false`                           | Set `true` after successful OTP verification       |
| `last_used_at`| `timestamp with time zone`     | NOT NULL | `now()`                           | Updated when `mark_as_used` is called              |
| `expires_at`  | `timestamp with time zone`     | NOT NULL | `now() + interval '15 minutes'`   | View excludes rows past this time                  |

**Constraints:**

| Constraint Name                | Type        | Column(s) |
|--------------------------------|-------------|-----------|
| `otp_transaction_log_pkey`     | PRIMARY KEY | `id`      |

**DDL:**
```sql
CREATE TABLE IF NOT EXISTS services.otp_transaction_log
(
    id            uuid                        NOT NULL  DEFAULT gen_random_uuid(),
    email         character varying(255)      NOT NULL,
    user_id       character varying(255)      NOT NULL,
    hashed_otp    character varying(255)      NOT NULL,
    action        character varying(255)      NOT NULL,
    created_at    timestamp with time zone    NOT NULL  DEFAULT now(),
    is_used       boolean                     NOT NULL  DEFAULT false,
    last_used_at  timestamp with time zone    NOT NULL  DEFAULT now(),
    expires_at    timestamp with time zone    NOT NULL  DEFAULT (now() + '00:15:00'::interval),
    CONSTRAINT otp_transaction_log_pkey PRIMARY KEY (id)
) TABLESPACE pg_default;
```

---

### 4.5 `services.token_transaction_log`

**Purpose:** Append-only log of every JWT issued. Each row tracks one token's lifecycle — whether it has been used and when it expires. Tokens are **single-use**: once `is_token_used` is `true`, the row is hidden from the view and any further use is rejected. No FK to user tables.

| Column          | Data Type                         | Nullable | Default                           | Notes                                                |
|-----------------|-----------------------------------|----------|-----------------------------------|------------------------------------------------------|
| `token_id`      | `uuid`                            | NOT NULL | —                                 | **Primary Key** — embedded in JWT payload            |
| `user_id`       | `varchar(30)`                     | NOT NULL | —                                 | Soft reference — no FK                               |
| `email`         | `varchar(255)`                    | NOT NULL | —                                 |                                                      |
| `token`         | `text`                            | NOT NULL | —                                 | Full signed JWT string                               |
| `action`        | `varchar(50)`                     | NOT NULL | —                                 | Token purpose — one of `AllowedTokenPurpose` values  |
| `is_token_used` | `boolean`                         | NOT NULL | `false`                           | Set `true` after token is consumed                   |
| `expires_at`    | `timestamp without time zone`     | NOT NULL | `now() + interval '14 minutes'`   | View excludes rows past this time                    |
| `created_at`    | `timestamp without time zone`     | NULL     | `now()`                           |                                                      |
| `last_updated_at`| `timestamp without time zone`    | NULL     | `now()`                           | Updated when `mark_as_used` is called                |

**Allowed `action` values (`AllowedTokenPurpose`):**

| Value                   | Used for                                              |
|-------------------------|-------------------------------------------------------|
| `SIGN_UP`               | Set-password link sent after signup                   |
| `LOGIN_SESSION`         | Active login session after successful authentication  |
| `LOGIN_2FA_OTP`         | Challenge token issued during OTP-based 2FA login     |
| `LOGIN_2FA_MAGIC_URL`   | Challenge token for magic-link 2FA (not yet active)   |
| `PASSWORD_RESET`        | Reset-password link sent after forgot-password        |
| `EMAIL_VERIFICATION`    | Reserved — not yet implemented                        |

**Constraints:**

| Constraint Name                    | Type        | Column(s)   |
|------------------------------------|-------------|-------------|
| `token_transaction_log_pkey`       | PRIMARY KEY | `token_id`  |

> **Note:** `expires_at` defaults to `now() + 14 minutes` at the DB level. The JWT expiry (`JWTTOKENEXPIRATIONMINUTES`, default 15 min) is enforced independently by the application. Both layers must be satisfied for a token to be valid.

**DDL:**
```sql
CREATE TABLE IF NOT EXISTS services.token_transaction_log
(
    token_id          uuid                           NOT NULL,
    user_id           character varying(30)          NOT NULL,
    email             character varying(255)         NOT NULL,
    token             text                           NOT NULL,
    action            character varying(50)          NOT NULL,
    is_token_used     boolean                        NOT NULL  DEFAULT false,
    expires_at        timestamp without time zone    NOT NULL  DEFAULT (now() + '00:14:00'::interval),
    created_at        timestamp without time zone              DEFAULT now(),
    last_updated_at   timestamp without time zone              DEFAULT now(),
    CONSTRAINT token_transaction_log_pkey PRIMARY KEY (token_id)
) TABLESPACE pg_default;
```

---

## 5. Views

Views are the **only way the application reads data**. Direct table SELECTs are never used. Views enforce expiry and usage filters so the application does not need to add those conditions to every query.

---

### 5.1 `auth_views.pending_user_registration_vw`

**Source table:** `auth.pending_user_registration`

**Filter conditions:**
- `expires_at > now()` — excludes expired signup attempts
- `is_token_used = false` — excludes already-completed signups

**Purpose:** Returns only pending registrations that are still actionable. If a user's row is not visible here, their signup token has expired or they have already set a password.

**Columns exposed:** All columns from the source table.

```sql
CREATE OR REPLACE VIEW auth_views.pending_user_registration_vw AS
SELECT
    uuid, email, first_name, last_name, role_type,
    country_cd, phone, token_id, expires_at,
    created_at, last_updated_at, is_token_used, user_id
FROM auth.pending_user_registration
WHERE expires_at > now()
  AND is_token_used = false;
```

---

### 5.2 `auth_views.user_profile`

**Source tables:** `auth.user_details` (alias `ud`) JOIN `auth.security_details` (alias `sd`)

**Join conditions:**
- `ud.user_id = sd.user_id`
- `ud.uuid = sd.uuid`
- `ud.is_deleted = false` — hard-excludes deleted users

**Purpose:** The primary read surface for all user profile lookups. Merges identity data (`user_details`) and security data (`security_details`) into a single flat row. Also computes `full_name` as a derived column.

**Columns exposed:**

| Column              | Source                       | Notes                                                        |
|---------------------|------------------------------|--------------------------------------------------------------|
| `uuid`              | `ud.uuid`                    |                                                              |
| `user_id`           | `ud.user_id`                 |                                                              |
| `first_name`        | `ud.first_name`              |                                                              |
| `last_name`         | `ud.last_name`               |                                                              |
| `role_type`         | `ud.role_type`               |                                                              |
| `email`             | `ud.email`                   |                                                              |
| `phone`             | `ud.phone`                   |                                                              |
| `country_cd`        | `ud.country_cd`              |                                                              |
| `is_2fa_enabled`    | `sd.is_2fa_enabled`          |                                                              |
| `is_email_verified` | `sd.is_email_verified`       |                                                              |
| `is_phone_verified` | `sd.is_phone_verified`       |                                                              |
| `hashed_password`   | `sd.hashed_password`         |                                                              |
| `is_active`         | `ud.is_active`               |                                                              |
| `is_deleted`        | `ud.is_deleted`              |                                                              |
| `create_ts`         | `ud.create_ts`               |                                                              |
| `last_updated_ts`   | `ud.last_updated_ts`         |                                                              |
| `full_name`         | Computed                     | `Title(first_name) + ' ' + Title(last_name)` — e.g. `"Ayan Pradhan"` |

**`full_name` computation:**
```sql
(upper(substring(first_name, 1, 1)) || lower(substring(first_name, 2)))
|| ' ' ||
(upper(substring(last_name, 1, 1))  || lower(substring(last_name, 2)))
```

```sql
CREATE OR REPLACE VIEW auth_views.user_profile AS
SELECT
    ud.uuid, ud.user_id, ud.first_name, ud.last_name, ud.role_type,
    ud.email, ud.phone, ud.country_cd,
    sd.is_2fa_enabled, sd.is_email_verified, sd.is_phone_verified,
    sd.hashed_password,
    ud.is_active, ud.is_deleted,
    ud.create_ts, ud.last_updated_ts,
    (upper(substring(ud.first_name, 1, 1)) || lower(substring(ud.first_name, 2))
     || ' ' ||
     upper(substring(ud.last_name, 1, 1))  || lower(substring(ud.last_name, 2))) AS full_name
FROM auth.user_details ud
JOIN auth.security_details sd
    ON  ud.user_id::text   = sd.user_id::text
    AND ud.uuid::text      = sd.uuid::text
    AND ud.is_deleted      = false;
```

> **Note:** `is_active = false` users **are** visible in this view. The application checks `is_active` after fetching the row and raises `UserNotFoundException` if it is `false`.

---

### 5.3 `services_views.otp_transaction_log_vw`

**Source table:** `services.otp_transaction_log`

**Filter conditions:**
- `expires_at > now()` — excludes expired OTPs
- `is_used = false` — excludes already-consumed OTPs
- `action <> ''` — excludes rows with empty action (data sanity guard)

**Purpose:** Returns only active, valid OTP records. Any OTP that has expired or been used is automatically invisible here — `check_valid_otp` returning `None` means the OTP is invalid regardless of the reason.

**Columns exposed:** All columns from the source table.

```sql
CREATE OR REPLACE VIEW services_views.otp_transaction_log_vw AS
SELECT
    id, email, user_id, hashed_otp, action,
    created_at, is_used, last_used_at, expires_at
FROM services.otp_transaction_log
WHERE expires_at > now()
  AND is_used    = false
  AND action::text <> ''::text;
```

---

### 5.4 `services_views.token_transaction_log_vw`

**Source table:** `services.token_transaction_log`

**Filter conditions:**
- `expires_at > now()` — excludes expired tokens
- `is_token_used = false` — excludes already-consumed tokens

**Purpose:** Returns only active, unused JWT records. Used by both `check_valid_token` (SIGN_UP flow) and as the base for `check_valid_token_for_registered_user` (all other flows, which additionally JOIN to `user_profile`).

**Columns exposed:** All columns from the source table except `last_updated_at`.

```sql
CREATE OR REPLACE VIEW services_views.token_transaction_log_vw AS
SELECT
    token_id, user_id, email, token,
    action, is_token_used, expires_at, created_at
FROM services.token_transaction_log
WHERE expires_at   > now()
  AND is_token_used = false;
```

---

## 6. Constraints & Indexes Summary

### Primary Keys

| Table                              | PK Column    | Type   |
|------------------------------------|--------------|--------|
| `auth.user_details`                | `uuid`       | `uuid` |
| `auth.pending_user_registration`   | `uuid`       | `uuid` |
| `auth.security_details`            | *(none)*     | —      |
| `services.otp_transaction_log`     | `id`         | `uuid` |
| `services.token_transaction_log`   | `token_id`   | `uuid` |

### Unique Constraints

| Table                 | Column    |
|-----------------------|-----------|
| `auth.user_details`   | `uuid`    |
| `auth.user_details`   | `user_id` |
| `auth.user_details`   | `email`   |
| `auth.user_details`   | `phone`   |

### Foreign Keys

| Table                   | Column    | References                        | On Update | On Delete |
|-------------------------|-----------|-----------------------------------|-----------|-----------|
| `auth.security_details` | `user_id` | `auth.user_details(user_id)`      | CASCADE   | CASCADE   |

### Indexes

| Index Name       | Table                   | Column  | Type  |
|------------------|-------------------------|---------|-------|
| `idx_user_email` | `auth.user_details`     | `email` | BTree |
| `idx_user_phone` | `auth.user_details`     | `phone` | BTree |

---

## 7. Design Notes

### Two-step onboarding with a staging table
`pending_user_registration` acts as a buffer between signup and account activation. The user does not exist in `user_details` until they click the email link and set a password. If they never complete the flow, the row expires and disappears from the view — no cleanup job needed.

### View-based access only
All application SELECTs go through `auth_views` and `services_views`. The views embed expiry and usage filters centrally, so no individual query needs to repeat `WHERE expires_at > now() AND is_used = false`. Adding a new query automatically inherits these protections.

### Soft delete and soft deactivation
`user_details` uses `is_deleted = false` and `is_active = true` instead of hard deletes. The `user_profile` view filters out deleted users at the JOIN level. Inactive users (`is_active = false`) are returned by the view but rejected at the application layer.

### No FK from services to auth
`otp_transaction_log` and `token_transaction_log` hold `user_id` and `email` as plain strings without FK constraints. This keeps transaction logs independent — they are never affected by cascades, and remain intact as audit history even if the user record is modified.

### Single-use tokens and OTPs enforced at two layers
Both `token_transaction_log` and `otp_transaction_log` use `is_token_used` / `is_used` flags. The views filter these out. Additionally, `check_valid_token_for_registered_user` re-checks `is_token_used = FALSE` and `expires_at > current_timestamp` explicitly in the JOIN, providing a second enforcement layer independent of the view.

### Token expiry mismatch to note
`token_transaction_log.expires_at` defaults to `now() + 14 minutes` at the DB level, while the application JWT expiry (`JWTTOKENEXPIRATIONMINUTES`) defaults to 15 minutes. Both must pass for a token to be valid. The 1-minute gap provides a DB-side buffer before the JWT itself expires.

### `security_details` has no primary key
The table relies on the `uuid + user_id` pair for identification. This is safe because `user_id` has a cascading FK to `user_details`, but adding an explicit PK on `uuid` would be a recommended improvement.

### `is_2fa_enabled` default contradiction
The DDL defaults `is_2fa_enabled` to `false`, but the application (`setup_new_password`) explicitly passes `'True'` at insert time — so all newly registered users have 2FA enabled regardless of the column default.
