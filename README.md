# Authentication Service

A FastAPI-based authentication backend with OTP 2FA, JWT session management, email verification, and password reset flows.

**Live API:** `https://authentication-five-indol.vercel.app`
**Demo UI / API Playground:** [https://fast-api-authentication-demo-ui.vercel.app/api-docs](https://fast-api-authentication-demo-ui.vercel.app/api-docs)

---

## Features

- Email-verified signup with a two-step onboarding (signup → set password via email link)
- OTP-based two-factor authentication (2FA enabled by default for all users)
- JWT session tokens with configurable expiry
- Forgot password / reset password via email link
- Get current user profile (`/v1/auth/me`)
- Logout with cookie clearing

---

## Tech Stack

| Layer        | Technology                          |
|--------------|-------------------------------------|
| Framework    | FastAPI + Uvicorn                   |
| Database     | PostgreSQL on NeonDB (serverless)   |
| DB Driver    | psycopg2-binary                     |
| Auth         | PyJWT (HS256)                       |
| Passwords    | Argon2 (argon2-cffi)                |
| Email        | aiosmtplib + Jinja2 templates       |
| Validation   | Pydantic v2                         |

---

## Project Structure

```
AUTHENTICATION/
├── app.py                    # FastAPI app, middleware, exception handlers
├── handler.py                # Global exception handlers
├── core/
│   └── config.py             # DBConfig, SMTPConfig, JWTConfig (loaded from .env)
├── routes/
│   ├── v1/auth.py            # All /v1/auth/* endpoints
│   └── webpage/webpage.py    # HTML page endpoints (set-password, reset-password)
├── services/
│   ├── auth.py               # Signup, login, password reset business logic
│   ├── token.py              # JWT creation and validation
│   ├── otp.py                # OTP generation and verification
│   └── mail.py               # Email sending
├── repositories/
│   └── user_repository.py    # DB query execution layer
├── CRUD/
│   ├── auth.py               # Auth SQL queries
│   ├── token.py              # Token SQL queries
│   └── otp.py                # OTP SQL queries (referenced as otp.py)
├── schemas/                  # Pydantic request/response schemas
├── templates/                # Jinja2 HTML email/page templates
├── documentation/
│   ├── API_DOCS.md           # Full API reference
│   ├── DB_DESIGN.md          # Database schema and design notes
│   └── SQL_DOCS.md           # All SQL queries documented
├── .env.example              # Environment variable template
└── requirements.txt
```

---

## Quick Start

**1. Clone and install dependencies**

```bash
git clone <repo-url>
cd AUTHENTICATION
pip install -r requirements.txt
```

**2. Configure environment**

```bash
cp .env.example .env
# Fill in your values — see .env.example for all required variables
```

See [Environment Variables](#environment-variables) below for details.

**3. Run**

```bash
uvicorn app:app --reload
```

The API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

> **Want to try without setting up?** Use the hosted [Demo UI / API Playground](https://fast-api-authentication-demo-ui.vercel.app/api-docs).

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values.

| Variable                              | Description                            | Default        |
|---------------------------------------|----------------------------------------|----------------|
| `PGHOST`                              | PostgreSQL host                        | —              |
| `PGPORT`                              | PostgreSQL port                        | `5432`         |
| `PGUSER`                              | PostgreSQL user                        | —              |
| `PGPASSWORD`                          | PostgreSQL password                    | —              |
| `PGDATABASE`                          | PostgreSQL database name               | —              |
| `PGCONNURL`                           | Full connection URL                    | —              |
| `PGSSLMODE`                           | SSL mode                               | `ssl`          |
| `SMTPEMAIL`                           | Sender email address                   | —              |
| `SMTPPASSWORD`                        | Email app password                     | —              |
| `SMTPHOST`                            | SMTP server host                       | —              |
| `SMTPPORT`                            | SMTP server port                       | `587`          |
| `JWTSECRETKEY`                        | JWT signing secret                     | —              |
| `JWTALGORITHM`                        | JWT algorithm                          | `HS256`        |
| `JWTTOKENEXPIRATIONMINUTES`           | Session token expiry (minutes)         | `15`           |
| `JWTCHALLENGETOKENEXPIRATIONMINUTES`  | 2FA challenge token expiry (minutes)   | `30`           |
| `JWTOTPTOKENEXPIRATIONMINUTES`        | OTP expiry (minutes)                   | `30`           |
| `JWTREFRESHTOKENEXPIRATIONMINUTES`    | Refresh token expiry (minutes)         | `15`           |

---

## API Overview

| Method   | Endpoint                          | Description                          |
|----------|-----------------------------------|--------------------------------------|
| POST     | `/v1/auth/signup`                 | Register a new user                  |
| POST     | `/v1/auth/signup/set-password`    | Complete signup — set initial password |
| POST     | `/v1/auth/otp/login`              | Login (returns session or OTP challenge) |
| POST     | `/v1/auth/otp/login/2fa_verify`   | Complete 2FA — submit OTP            |
| POST     | `/v1/auth/forgot-password`        | Request a password reset email       |
| POST     | `/v1/auth/reset-password`         | Set a new password via reset link    |
| POST     | `/v1/auth/me`                     | Get current user profile             |
| DELETE   | `/v1/auth/logout`                 | Logout (clears session cookie)       |
| GET      | `/pages/auth/set-password`        | HTML set-password page (email link)  |
| GET      | `/pages/auth/reset-password`      | HTML reset-password page (email link)|

> For full request/response shapes, error codes, flow diagrams, and token reference, see the [API Documentation](documentation/API_DOCS.md).

---

## Documentation

| Document | Description |
|---|---|
| [API_DOCS.md](documentation/API_DOCS.md) | Complete API reference — endpoints, request/response shapes, error codes, auth flows |
| [DB_DESIGN.md](documentation/DB_DESIGN.md) | Database schema, ERD, table definitions, views, and design decisions |
| [SQL_DOCS.md](documentation/SQL_DOCS.md) | Every SQL query with parameters, return columns, and endpoint mapping |

---

## Authentication Flow Summary

```
Signup:   POST /signup → email link → POST /signup/set-password → account active

Login:    POST /otp/login
            ├── 2FA disabled → { token }  ← store and use as Bearer token
            └── 2FA enabled  → { challenge_token } → POST /otp/login/2fa_verify → { token }

Reset:    POST /forgot-password → email link → POST /reset-password
```

All protected endpoints require `Authorization: Bearer <token>` in the request header.
