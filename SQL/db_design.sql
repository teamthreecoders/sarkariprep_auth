-- Active: 1779639209493@@ep-rough-firefly-aqtt5d17-pooler.c-8.us-east-1.aws.neon.tech@5432@authentication
CREATE DATABASE authentication;

-- postgre use authentication database
SELECT current_database();

CREATE SCHEMA auth;
CREATE schema auth_views;

CREATE SCHEMA services;

CREATE SCHEMA services_views;

CREATE TABLE IF NOT EXISTS auth.user_details
(
    uuid uuid NOT NULL,
    user_id character varying(50) COLLATE pg_catalog."default" NOT NULL,
    first_name character varying(255) COLLATE pg_catalog."default" NOT NULL,
    last_name character varying(255) COLLATE pg_catalog."default",
    role_type character varying(255) COLLATE pg_catalog."default" NOT NULL DEFAULT 'user'::character varying,
    email character varying(255) COLLATE pg_catalog."default" NOT NULL,
    country_cd character varying(4) COLLATE pg_catalog."default" NOT NULL ,
    phone character varying(255) COLLATE pg_catalog."default" NOT NULL,
    create_ts timestamp with time zone NOT NULL DEFAULT now(),
    last_updated_ts timestamp with time zone NOT NULL DEFAULT now(),
    is_active boolean NOT NULL DEFAULT true,
    is_deleted boolean NOT NULL DEFAULT false,
    CONSTRAINT user_details_pkey PRIMARY KEY (uuid),
    CONSTRAINT user_details_email_key UNIQUE (email),
    CONSTRAINT user_details_phone_key UNIQUE (phone),
    CONSTRAINT user_details_user_id_key UNIQUE (user_id)
)

TABLESPACE pg_default;

ALTER TABLE auth.user_details
    OWNER to neondb_owner;

-- Index: auth.idx_user_email
CREATE INDEX IF NOT EXISTS idx_user_email
    ON auth.user_details USING btree
    (email COLLATE pg_catalog."default" ASC NULLS LAST)
    TABLESPACE pg_default;
-- Index: auth.idx_user_phone
CREATE INDEX IF NOT EXISTS idx_user_phone
    ON auth.user_details USING btree
    (phone COLLATE pg_catalog."default" ASC NULLS LAST)
    TABLESPACE pg_default;


CREATE TABLE IF NOT EXISTS auth.security_details
(   uuid uuid NOT NULL ,
    user_id character varying(50) COLLATE pg_catalog."default",
    hashed_password character varying(255) COLLATE pg_catalog."default",
    is_2fa_enabled boolean NOT NULL DEFAULT false,
    is_email_verified boolean NOT NULL DEFAULT false,
    is_phone_verified boolean NOT NULL DEFAULT false,
    create_at timestamp WITH time zone NOT NULL DEFAULT now(),
    last_updated timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT security_details_user_id_fkey FOREIGN KEY (user_id)
        REFERENCES auth.user_details (user_id) MATCH SIMPLE
        ON UPDATE CASCADE
        ON DELETE CASCADE
)
TABLESPACE pg_default;



CREATE TABLE IF NOT EXISTS auth.pending_user_registration
(
    uuid uuid NOT NULL,
    user_id character varying(30) COLLATE pg_catalog."default" NOT NULL ,
    email character varying(255) COLLATE pg_catalog."default" NOT NULL ,
    first_name character varying(100) COLLATE pg_catalog."default" NOT NULL,
    last_name character varying(100) COLLATE pg_catalog."default" NOT NULL,
    role_type character varying(30) COLLATE pg_catalog."default" NOT NULL,
    country_cd character varying(10) COLLATE pg_catalog."default",
    phone character varying(20) COLLATE pg_catalog."default",
    token_id text COLLATE pg_catalog."default" NOT NULL ,
    expires_at timestamp with time zone DEFAULT (now() + '00:15:00'::interval),
    created_at timestamp with time zone DEFAULT now(),
    last_updated_at timestamp with time zone NOT NULL DEFAULT now(),
    is_token_used boolean DEFAULT false,
    CONSTRAINT pending_user_registration_pkey PRIMARY KEY (uuid)
)
TABLESPACE pg_default;


CREATE TABLE IF NOT EXISTS services.token_transaction_log
(
    token_id uuid NOT NULL,
    user_id character varying(30) COLLATE pg_catalog."default" NOT NULL,
    email character varying(255) COLLATE pg_catalog."default" NOT NULL,
    token text COLLATE pg_catalog."default" NOT NULL,
    action character varying(50) COLLATE pg_catalog."default" NOT NULL,
    is_token_used boolean NOT NULL DEFAULT false,
    expires_at timestamp without time zone NOT NULL DEFAULT (now() + '00:14:00'::interval),
    created_at timestamp without time zone DEFAULT now(),
    last_updated_at timestamp without time zone DEFAULT now(),
    CONSTRAINT token_transaction_log_pkey PRIMARY KEY (token_id)
)
TABLESPACE pg_default;

CREATE OR REPLACE VIEW services_views.token_transaction_log_vw AS
 SELECT 
    token_id,
    user_id,
    email,
    token,
    action,
    is_token_used,
    expires_at,
    created_at
   FROM services.token_transaction_log
  WHERE expires_at > now() AND is_token_used = false;



CREATE OR REPLACE VIEW auth_views.pending_user_registration_vw AS
 SELECT uuid,
    email,
    first_name,
    last_name,
    role_type,
    country_cd,
    phone,
    token_id,
    expires_at,
    created_at,
    last_updated_at,
    is_token_used,
    user_id
   FROM auth.pending_user_registration
  WHERE expires_at > now() AND is_token_used = false;

CREATE OR REPLACE VIEW auth_views.user_profile AS
 SELECT 
    ud.uuid,
    ud.user_id,
    ud.first_name,
    ud.last_name,
    ud.role_type,
    ud.email,
    ud.phone,
    sd.is_2fa_enabled,
    sd.is_email_verified,
    sd.is_phone_verified,
    ud.create_ts,
    ud.last_updated_ts,
    sd.hashed_password,
    ud.is_active,
    ud.is_deleted
   FROM auth.user_details ud
     JOIN auth.security_details sd ON ud.user_id::text = sd.user_id::text
     AND ud.uuid::text = sd.uuid::text
     ;