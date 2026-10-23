# Authentication API — Frontend Integration Guide

> **Base URL:** `https://authentication-five-indol.vercel.app`
> **Demo UI / API Playground:** [https://fast-api-authentication-demo-ui.vercel.app/api-docs](https://fast-api-authentication-demo-ui.vercel.app/api-docs)
> **Content-Type:** `application/json` (all requests and responses unless noted)

---

## Table of Contents

1. [Universal Response Shape](#1-universal-response-shape)
2. [Universal Error Shape](#2-universal-error-shape)
3. [All Possible Error Codes (Master Reference)](#3-all-possible-error-codes-master-reference)
4. [Password Rules](#4-password-rules)
5. [Credential Object Reference](#5-credential-object-reference)
6. [Endpoints](#6-endpoints)
   - [POST /v1/auth/signup](#61-post-v1authsignup)
   - [POST /v1/auth/signup/set-password](#62-post-v1authsignupset-password)
   - [POST /v1/auth/otp/login](#63-post-v1authotplogin)
   - [POST /v1/auth/otp/login/2fa_verify](#64-post-v1authotplogin2fa_verify)
   - [POST /v1/auth/refresh](#610-post-v1authrefresh)
   - [POST /v1/auth/forgot-password](#65-post-v1authforgot-password)
   - [POST /v1/auth/reset-password](#66-post-v1authreset-password)
   - [POST /v1/auth/me](#67-post-v1authme)
   - [DELETE /v1/auth/logout](#68-delete-v1authlogout)
   - [GET / and GET /health](#69-get--and-get-health)
7. [Page Endpoints (Browser / HTML)](#7-page-endpoints-browser--html)
8. [Token Reference](#8-token-reference)
9. [Full Authentication Flow Diagrams](#9-full-authentication-flow-diagrams)

---

## 1. Universal Response Shape

**Every successful API response** follows this exact structure:

```json
{
  "msg": "Human-readable message",
  "success": true,
  "code": 200,
  "error": null,
  "data": { ... }
}
```

| Field     | Type           | Notes                                                   |
|-----------|----------------|---------------------------------------------------------|
| `msg`     | `string`       | Human-readable status message                           |
| `success` | `boolean`      | Always `true` for success responses                     |
| `code`    | `integer`      | Mirrors the HTTP status code                            |
| `error`   | `null`         | Always `null` on success                                |
| `data`    | `object\|null` | Payload; shape varies per endpoint. See each endpoint.  |

---

## 2. Universal Error Shape

**Every error** (validation or application-level) follows this exact structure:

```json
{
  "msg": "Human-readable error message",
  "success": false,
  "code": 422,
  "error": {
    "issue": "...",
    "details": null
  },
  "data": null
}
```

| Field            | Type             | Notes                                                         |
|------------------|------------------|---------------------------------------------------------------|
| `msg`            | `string`         | Human-readable error message                                  |
| `success`        | `boolean`        | Always `false` on error                                       |
| `code`           | `integer`        | Mirrors the HTTP status code                                  |
| `error`          | `object`         | Always an object — never a plain string or array              |
| `error.issue`    | `string`         | Short error category (e.g. `"Unauthorized"`, `"Validation Failed"`) |
| `error.details`  | `array \| null`  | Populated only for validation errors; `null` for app errors   |
| `data`           | `null`           | Always `null` on error                                        |

### 2a. Validation Error

Triggered when request body fields fail schema validation (missing fields, wrong types, pattern mismatch, password rule violations).

```json
{
  "msg": "Request payload error",
  "success": false,
  "code": 422,
  "error": {
    "issue": "Validation Failed",
    "details": [
      {
        "type": "missing",
        "loc": ["body", "email"],
        "msg": "Field required",
        "input": {}
      },
      {
        "type": "string_too_short",
        "loc": ["body", "first_name"],
        "msg": "String should have at least 3 characters",
        "input": "ab"
      }
    ]
  },
  "data": null
}
```

Each object inside `error.details` has:

| Field   | Type     | Notes                                              |
|---------|----------|----------------------------------------------------|
| `type`  | `string` | Machine-readable error type (e.g. `"missing"`)     |
| `loc`   | `array`  | Location path — e.g. `["body", "field_name"]`      |
| `msg`   | `string` | Human-readable field-level message                 |
| `input` | `any`    | The value that was received for that field         |

### 2b. Application Error

```json
{
  "msg": "Invalid login credential",
  "success": false,
  "code": 401,
  "error": {
    "issue": "Unauthorized",
    "details": null
  },
  "data": null
}
```

---

## 3. All Possible Error Codes (Master Reference)

| HTTP | `error.issue`                       | `msg`                                                                       | Root Cause                                               |
|------|-------------------------------------|-----------------------------------------------------------------------------|----------------------------------------------------------|
| 400  | `"Password reset failed"`           | `"Password reset failed!"`                                                  | DB update failed during password reset                   |
| 401  | `"Unauthorized"`                    | `"Invalid login credential"`                                                | Wrong password, or `user_id` not found                   |
| 401  | `"Unauthorized"`                    | `"Invalid token"`                                                           | Authorization header missing, malformed, or wrong purpose|
| 401  | `"Unauthorized"`                    | `"Token expired"`                                                           | JWT token has passed its expiry time                     |
| 401  | `"Unauthorized"`                    | `"Invalid OTP"`                                                             | Wrong OTP entered during 2FA verification                |
| 401  | `"Unauthorized"`                    | `"OTP expired"`                                                             | The challenge_token JWT has expired (15-min window)      |
| 404  | `"Not Found"`                       | `"User Not Found"`                                                          | Email/phone/user_id not found, or account is inactive    |
| 404  | `"Not Found"`                       | `"Pending user not found"`                                                  | Set-password token references a non-existent signup      |
| 409  | `"Conflict"`                        | `"User EmailId or PhoneNo already registered."`                             | Duplicate signup with same email or phone number         |
| 422  | `"Password Mismatch"`               | `"Password & Confirm Password Not Match"`                                   | `new_password` does not equal `confirm_new_password`     |
| 422  | `"Validation Failed"`               | `"Request payload error"` — `error.details` contains the field error array | Missing fields, wrong types, regex mismatch              |
| 500  | `"Server Not Found"`                | `"Internal Server Error"`                                                   | Unexpected server-side failure                           |

---

## 4. Password Rules

Applied to `password` (login) and `new_password` (set/reset password) fields.

| Rule                        | Requirement                                      |
|-----------------------------|--------------------------------------------------|
| Minimum length              | 8 characters                                     |
| Spaces                      | Not allowed                                      |
| Special character           | At least 1 required (e.g. `! @ # $ % ^ & *`)    |
| Digit                       | At least 1 required (`0–9`)                      |
| Uppercase letter            | At least 1 required (`A–Z`)                      |
| Lowercase letter            | At least 1 required (`a–z`)                      |

**Valid example:** `MyPass@1`

If multiple rules fail, all failures are listed together in a single `422` validation error message.

---

## 5. Credential Object Reference

Endpoints that accept a `credential` field support **one of three shapes**. Send exactly one shape — do not mix fields.

### Shape A — By Email
```json
{ "email": "user@example.com" }
```
| Field   | Type     | Required | Validation       |
|---------|----------|----------|------------------|
| `email` | `string` | **Yes**  | Must contain `@` |

### Shape B — By Phone
```json
{ "country_cd": "+91", "phone": "9876543210" }
```
| Field        | Type     | Required | Validation                                              |
|--------------|----------|----------|---------------------------------------------------------|
| `country_cd` | `string` | **Yes**  | Pattern: `^\+\d{2}$` — plus sign followed by 2 digits  |
| `phone`      | `string` | **Yes**  | Exactly 10 digits                                       |

### Shape C — By User ID
```json
{ "user_id": "AY12345678" }
```
| Field     | Type     | Required | Validation              |
|-----------|----------|----------|-------------------------|
| `user_id` | `string` | **Yes**  | System-assigned user ID |

---

## 6. Endpoints

---

### 6.1 POST `/v1/auth/signup`

Register a new user. Sends a verification email containing a set-password link.

#### Request Body

```json
{
  "first_name": "Ayan",
  "last_name": "Pradhan",
  "email": "ayan@example.com",
  "phone": "9876543210",
  "country_cd": "+91",
  "role_type": "user"
}
```

| Field        | Type     | Required | Default  | Validation                                            |
|--------------|----------|----------|----------|-------------------------------------------------------|
| `first_name` | `string` | **Yes**  | —        | Min 3 characters                                      |
| `last_name`  | `string` | **Yes**  | —        | Min 3 characters                                      |
| `email`      | `string` | **Yes**  | —        | Must contain `@`                                      |
| `phone`      | `string` | **Yes**  | —        | Exactly 10 digits, pattern `^\d{10}$`                 |
| `country_cd` | `string` | No       | `"+91"`  | Pattern `^\+\d{2}$` (e.g. `+91`, `+44`, `+1`)        |
| `role_type`  | `string` | No       | `"user"` | One of: `"user"`, `"admin"`, `"guest"`, `"other"`    |

#### Success Response — `201 Created`

```json
{
  "msg": "Verification email sent. Please verify your email and set your password.",
  "success": true,
  "code": 201,
  "error": null,
  "data": {
    "email": "ayan@example.com",
    "email_verification_required": true
  }
}
```

| `data` Field                  | Type      | Notes            |
|-------------------------------|-----------|------------------|
| `email`                       | `string`  | Registered email |
| `email_verification_required` | `boolean` | Always `true`    |

#### Error Responses

| HTTP | `error`                       | `msg`                                              |
|------|-------------------------------|----------------------------------------------------|
| 409  | `"Conflict"`                  | `"User EmailId or PhoneNo already registered."`    |
| 422  | `[array]`                     | `"Request payload error"`                          |
| 500  | `"Server Not Found"`          | `"Internal Server Error"`                          |

#### What happens next
User receives an email. Clicking the link opens a browser page at `/pages/auth/set-password?token=<jwt>`. That page submits to **[6.2 Set Password](#62-post-v1authsignupset-password)**.

---

### 6.2 POST `/v1/auth/signup/set-password`

Set the initial password after clicking the sign-up email link. Finalises the user account.

#### Request Headers

| Header          | Required | Format           | Notes                                                      |
|-----------------|----------|------------------|------------------------------------------------------------|
| `Authorization` | **Yes**  | `Bearer <token>` | SIGN_UP token from the email link (passed as HTTP header)  |

> **Important:** This is an HTTP `Authorization` request header, not a cookie.

#### Request Body

```json
{
  "new_password": "MyPass@1",
  "confirm_new_password": "MyPass@1"
}
```

| Field                  | Type     | Required | Validation                                 |
|------------------------|----------|----------|--------------------------------------------|
| `new_password`         | `string` | **Yes**  | See [Password Rules](#4-password-rules)    |
| `confirm_new_password` | `string` | **Yes**  | Must exactly match `new_password`          |

#### Success Response — `201 Created`

```json
{
  "msg": "Password setup successful",
  "success": true,
  "code": 201,
  "error": null,
  "data": {
    "user_id": "AY12345678",
    "email": "ayan@example.com"
  }
}
```

| `data` Field | Type     | Notes                        |
|--------------|----------|------------------------------|
| `user_id`    | `string` | System-assigned unique ID    |
| `email`      | `string` | Registered email             |

#### Error Responses

| HTTP | `error`               | `msg`                                        |
|------|-----------------------|----------------------------------------------|
| 401  | `"Unauthorized"`      | `"Invalid token"`                            |
| 401  | `"Unauthorized"`      | `"Token expired"`                            |
| 404  | `"Not Found"`         | `"Pending user not found"`                   |
| 422  | `"Password Mismatch"` | `"Password & Confirm Password Not Match"`    |
| 422  | `[array]`             | `"Request payload error"`                    |
| 500  | `"Server Not Found"`  | `"Internal Server Error"`                    |

#### What happens next
Account is active. Redirect user to the login page.

---

### 6.3 POST `/v1/auth/otp/login`

Login with email/phone/user_id + password via OTP-based 2FA.

- **2FA disabled:** Returns a session token directly. Login complete.
- **2FA enabled:** Sends a 4-digit OTP to the user's email and returns a `challenge_token`. Proceed to **[6.4](#64-post-v1authotplogin2fa_verify)**.

#### Request Body

```json
{
  "credential": { "email": "ayan@example.com" },
  "password": "MyPass@1"
}
```

| Field        | Type     | Required | Notes                                                                    |
|--------------|----------|----------|--------------------------------------------------------------------------|
| `credential` | `object` | **Yes**  | One of the three shapes — see [Section 5](#5-credential-object-reference) |
| `password`   | `string` | **Yes**  | See [Password Rules](#4-password-rules)                                  |

#### Success Response — `200 OK` (2FA **disabled** — direct login)

```json
{
  "msg": "Login Successful",
  "success": true,
  "code": 200,
  "error": null,
  "data": {
    "token": "<session_jwt_token>"
  }
}
```

| `data` Field | Type     | Notes                                                                              |
|--------------|----------|------------------------------------------------------------------------------------|
| `token`      | `string` | Session JWT. Send as `Authorization: Bearer <token>` header on all protected calls. |
| `refresh_token` | `string` | Long-lived, single-use token. Exchange it at [`POST /v1/auth/refresh`](#610-post-v1authrefresh) for a new session token. (Also returned by `otp/login` when 2FA is disabled.) |

#### Success Response — `200 OK` (2FA **enabled** — OTP sent)

```json
{
  "msg": "OTP send successful",
  "success": true,
  "code": 200,
  "error": null,
  "data": {
    "mode": "otp",
    "challenge_token": "<challenge_jwt_token>"
  }
}
```

| `data` Field      | Type     | Notes                                                              |
|-------------------|----------|--------------------------------------------------------------------|
| `mode`            | `string` | Always `"otp"` for this endpoint                                  |
| `challenge_token` | `string` | Short-lived token. Use in the next step alongside the OTP.        |

> OTP is 4 digits and expires in **15 minutes**.

#### Error Responses

| HTTP | `error`              | `msg`                        |
|------|----------------------|------------------------------|
| 401  | `"Unauthorized"`     | `"Invalid login credential"` |
| 404  | `"Not Found"`        | `"User Not Found"`           |
| 422  | `[array]`            | `"Request payload error"`    |
| 500  | `"Server Not Found"` | `"Internal Server Error"`    |

---

### 6.4 POST `/v1/auth/otp/login/2fa_verify`

Complete 2FA login by submitting the OTP received via email along with the `challenge_token` from the login response.

#### Request Body

```json
{
  "challenge_token": "<challenge_jwt_token from otp/login>",
  "otp": "4829"
}
```

| Field             | Type     | Required | Notes                                                          |
|-------------------|----------|----------|----------------------------------------------------------------|
| `challenge_token` | `string` | **Yes**  | Value of `data.challenge_token` from the `otp/login` response |
| `otp`             | `string` | **Yes**  | 4-digit OTP delivered to the user's email                     |

#### Success Response — `200 OK`

```json
{
  "msg": "Login Successful",
  "success": true,
  "code": 200,
  "error": null,
  "data": {
    "token": "<session_jwt_token>"
  }
}
```

| `data` Field | Type     | Notes                                                                              |
|--------------|----------|------------------------------------------------------------------------------------|
| `token`      | `string` | Session JWT. Send as `Authorization: Bearer <token>` header on all protected calls. |

> **Cookie side-effect:** The server also sets an `Authorization` cookie (`Bearer <token>`). This is in addition to the JSON body — use whichever is more appropriate for your client.

#### Error Responses

| HTTP | `error`              | `msg`                     |
|------|----------------------|---------------------------|
| 401  | `"Unauthorized"`     | `"Invalid OTP"`           |
| 401  | `"Unauthorized"`     | `"OTP expired"`           |
| 500  | `"Server Not Found"` | `"Internal Server Error"` |

---

### 6.5 POST `/v1/auth/forgot-password`

Initiate a password reset. Sends a reset link to the user's registered email.

#### Request Body

```json
{
  "credential": { "email": "ayan@example.com" }
}
```

| Field        | Type     | Required | Notes                                                                    |
|--------------|----------|----------|--------------------------------------------------------------------------|
| `credential` | `object` | **Yes**  | One of the three shapes — see [Section 5](#5-credential-object-reference) |

#### Success Response — `202 Accepted`

```json
{
  "msg": "If an account exists for this email, a password reset link has been sent.",
  "success": true,
  "code": 202,
  "error": null,
  "data": {
    "email": "ayan@example.com"
  }
}
```

| `data` Field | Type     | Notes                           |
|--------------|----------|---------------------------------|
| `email`      | `string` | The email that was looked up    |

> **Security note:** The response message is intentionally vague. The API always responds with `202` regardless of whether the account exists, to prevent email enumeration.

#### Error Responses

| HTTP | `error`              | `msg`                     |
|------|----------------------|---------------------------|
| 404  | `"Not Found"`        | `"User Not Found"`        |
| 422  | `[array]`            | `"Request payload error"` |
| 500  | `"Server Not Found"` | `"Internal Server Error"` |

#### What happens next
User receives an email. Clicking the link opens `/pages/auth/reset-password?token=<jwt>` in a browser, which submits to **[6.6 Reset Password](#66-post-v1authreset-password)**.

---

### 6.6 POST `/v1/auth/reset-password`

Set a new password using the PASSWORD_RESET token from the forgot-password email.

#### Request Headers

| Header          | Required | Format           | Notes                                                          |
|-----------------|----------|------------------|----------------------------------------------------------------|
| `Authorization` | **Yes**  | `Bearer <token>` | PASSWORD_RESET token from the email link (HTTP request header) |

> **Important:** This is an HTTP `Authorization` request header, not a cookie.

#### Request Body

```json
{
  "new_password": "NewPass@2",
  "confirm_new_password": "NewPass@2"
}
```

| Field                  | Type     | Required | Validation                                 |
|------------------------|----------|----------|--------------------------------------------|
| `new_password`         | `string` | **Yes**  | See [Password Rules](#4-password-rules)    |
| `confirm_new_password` | `string` | **Yes**  | Must exactly match `new_password`          |

#### Success Response — `200 OK`

```json
{
  "msg": "Password Updated",
  "success": true,
  "code": 200,
  "error": null,
  "data": {
    "user_id": "AY12345678",
    "email": "ayan@example.com"
  }
}
```

| `data` Field | Type     | Notes                     |
|--------------|----------|---------------------------|
| `user_id`    | `string` | Unique system user ID     |
| `email`      | `string` | The user's registered email |

#### Error Responses

| HTTP | `error`                   | `msg`                                    |
|------|---------------------------|------------------------------------------|
| 400  | `"Password reset failed"` | `"Password reset failed!"`               |
| 401  | `"Unauthorized"`          | `"Invalid token"`                        |
| 401  | `"Unauthorized"`          | `"Token expired"`                        |
| 422  | `[array]`                 | `"Request payload error"`                |
| 500  | `"Server Not Found"`      | `"Internal Server Error"`                |

---

### 6.7 POST `/v1/auth/me`

Fetch the currently authenticated user's profile. Requires a valid login session token.

#### Request Headers

| Header          | Required | Format           | Notes                                             |
|-----------------|----------|------------------|---------------------------------------------------|
| `Authorization` | **Yes**  | `Bearer <token>` | Session JWT obtained from login (`data.token`)    |

> No request body needed.

#### Success Response — `200 OK`

```json
{
  "msg": "Authenticated",
  "success": true,
  "code": 200,
  "error": null,
  "data": {
    "user_id": "AY12345678",
    "first_name": "Ayan",
    "last_name": "Pradhan",
    "full_name": "Ayan Pradhan",
    "email": "ayan@example.com",
    "phone": "9876543210",
    "country_cd": "+91",
    "role_type": "user",
    "is_active": true,
    "is_2fa_enabled": false
  }
}
```

| `data` Field     | Type      | Notes                                               |
|------------------|-----------|-----------------------------------------------------|
| `user_id`        | `string`  | Unique system user ID                               |
| `first_name`     | `string`  | First name                                          |
| `last_name`      | `string`  | Last name                                           |
| `full_name`      | `string`  | Concatenated full name                              |
| `email`          | `string`  | Registered email                                    |
| `phone`          | `string`  | 10-digit phone number (no country code)             |
| `country_cd`     | `string`  | Country code, e.g. `"+91"`                          |
| `role_type`      | `string`  | One of: `"user"`, `"admin"`, `"guest"`, `"other"`  |
| `is_active`      | `boolean` | Whether the account is active                       |
| `is_2fa_enabled` | `boolean` | Whether 2FA is enabled for this account             |

#### Error Responses

| HTTP | `error`              | `msg`                     |
|------|----------------------|---------------------------|
| 401  | `"Unauthorized"`     | `"Invalid token"`         |
| 401  | `"Unauthorized"`     | `"Token expired"`         |
| 404  | `"Not Found"`        | `"User Not Found"`        |
| 500  | `"Server Not Found"` | `"Internal Server Error"` |

---

### 6.8 DELETE `/v1/auth/logout`

Log out the current user. Clears the server-set `Authorization` cookie.

> No `Authorization` header required. Optional JSON body `{"refresh_token": "<token>"}` — if sent, the refresh token is invalidated too, so the session can't be renewed after logout.

#### Success Response — `200 OK`

```json
{
  "msg": "Log Out successful",
  "success": true,
  "code": 202,
  "error": null,
  "data": null
}
```

> **Cookie side-effect:** The server sends `Set-Cookie: Authorization=; Max-Age=0` to clear the cookie.

#### Error Responses
None. This endpoint always returns `200 OK`.

---

### 6.10 POST `/v1/auth/refresh`

Exchange a refresh token for a new session token, without redoing OTP login. **Refresh tokens rotate:** the one you send is marked used, and the response contains a new one — always store the new `refresh_token`.

#### Request Body

```json
{ "refresh_token": "<refresh_token from 2fa_verify / previous refresh>" }
```

#### Success Response — `200 OK`

```json
{
  "msg": "Token refreshed",
  "success": true,
  "code": 200,
  "error": null,
  "data": {
    "token": "<new_session_jwt_token>",
    "refresh_token": "<new_refresh_token>"
  }
}
```

> **Cookie side-effect:** like `2fa_verify`, sets the `Authorization` cookie to the new session token.

#### Error Responses

| HTTP | `error`          | `msg`             | When                                                                 |
|------|------------------|-------------------|----------------------------------------------------------------------|
| 401  | `"Unauthorized"` | `"Invalid token"` | Refresh token is expired, already used, malformed, or user inactive. The user must log in again. |
| 500  | `"Server Not Found"` | `"Internal Server Error"` |                                                       |

Refresh token lifetime: `JWTREFRESHTOKENEXPIRATIONMINUTES` (default **43200** = 30 days).

---

### 6.9 GET `/` and GET `/health`

Utility endpoints. Not part of the auth flow.

**GET `/`** — `200 OK`
```json
{ "msg": "Hello, I am good! How are you?🐼🐼" }
```

**GET `/health`** — `200 OK`
```json
{ "greet": "welcome to authentication" }
```

---

## 7. Page Endpoints (Browser / HTML)

These endpoints return **HTML pages**, not JSON. They are opened directly in the user's browser via links in emails. **The frontend does not call these programmatically.** The HTML forms on these pages call back into the JSON API.

| Method | Path                           | Query param | Token Purpose    | HTML Page served            |
|--------|--------------------------------|-------------|------------------|-----------------------------|
| GET    | `/pages/auth/set-password`      | `token`     | `SIGN_UP`        | Set-password form           |
| GET    | `/pages/auth/reset-password`   | `token`     | `PASSWORD_RESET` | Reset-password form         |

**Query Parameter:**

| Param   | Required | Notes                                      |
|---------|----------|--------------------------------------------|
| `token` | **Yes**  | JWT appended automatically by email link   |

- Valid token → `200` — HTML form page
- Invalid or expired token → `401` — HTML error page (`token-expire.html`)

---

## 8. Token Reference

| Token Purpose         | Delivered via          | Used by                                    | Header format             |
|-----------------------|------------------------|--------------------------------------------|---------------------------|
| `SIGN_UP`             | Email link (query param) | `POST /v1/auth/signup/set-password`         | `Authorization: Bearer …` |
| `PASSWORD_RESET`      | Email link (query param) | `POST /v1/auth/reset-password`             | `Authorization: Bearer …` |
| `LOGIN_2FA_OTP`       | JSON body `challenge_token` | `POST /v1/auth/otp/login/2fa_verify`    | Sent in request body      |
| `LOGIN_SESSION`       | JSON body `data.token` | `POST /v1/auth/me`, `POST /v1/auth/reset-password` | `Authorization: Bearer …` |
| `REFRESH_TOKEN`       | JSON body `data.refresh_token` | `POST /v1/auth/refresh`, `DELETE /v1/auth/logout` (optional) | Sent in request body |

**Notes:**
- All tokens are JWTs signed with `HS256`.
- Default session token expiry: **15 minutes** (configurable via `JWTTOKENEXPIRATIONMINUTES`).
- OTP + challenge token expiry: **15 minutes** (OTP email states this).
- Tokens are **single-use** — marked as used in the database after first consumption.
- Always send as `Authorization: Bearer <token>` in the **HTTP request header** (not as a cookie).

---

## 9. Full Authentication Flow Diagrams

### New User Signup

```
Frontend                                    Backend
   |                                            |
   |--- POST /v1/auth/signup ------------------>|
   |    { first_name, last_name, email,         |
   |      phone, country_cd?, role_type? }      |
   |<-- 201 { data: { email, email_           --|
   |          verification_required: true } }   |
   |                                            |--- sends email with link
   |                                            |    /pages/auth/set-password?token=<jwt>
   |                                            |
   |   [User clicks email link in browser]      |
   |--- GET /pages/auth/set-password?token= -->|
   |<-- 200 HTML form -----------------------  |
   |                                            |
   |--- POST /v1/auth/signup/set-password ------>|
   |    Header: Authorization: Bearer <token>   |
   |    { new_password, confirm_new_password }  |
   |<-- 201 { data: { user_id, email } } ----  |
   |                                            |
   |   [Redirect to login page]                 |
```

---

### Login — 2FA Disabled

```
Frontend                                    Backend
   |                                            |
   |--- POST /v1/auth/otp/login --------------->|
   |    { credential: { email }, password }     |
   |<-- 200 { data: { token } } -------------- |
   |                                            |
   |   Store token. Use on all future requests: |
   |   Authorization: Bearer <token>            |
   |                                            |
   |--- POST /v1/auth/me -------------------->  |
   |    Header: Authorization: Bearer <token>   |
   |<-- 200 { data: { user_id, email, ... } }  |
```

---

### Login — 2FA Enabled

```
Frontend                                    Backend
   |                                            |
   |--- POST /v1/auth/otp/login --------------->|
   |    { credential: { email }, password }     |--- sends OTP email to user
   |<-- 200 { data: { mode: "otp",           --|
   |          challenge_token } }               |
   |                                            |
   |   [User reads OTP from email]              |
   |                                            |
   |--- POST /v1/auth/otp/login/2fa_verify ---->|
   |    { challenge_token, otp: "4829" }        |
   |<-- 200 { data: { token } } -------------- |
   |    (+ sets Authorization cookie)           |
   |                                            |
   |   Store token. Login complete.             |
```

---

### Forgot Password

```
Frontend                                    Backend
   |                                            |
   |--- POST /v1/auth/forgot-password -------->|
   |    { credential: { email } }               |--- sends reset email
   |<-- 202 { msg: "If an account exists…" }  |    /pages/auth/reset-password?token=<jwt>
   |                                            |
   |   [User clicks email link in browser]      |
   |--- GET /pages/auth/reset-password?token ->|
   |<-- 200 HTML form -----------------------  |
   |                                            |
   |--- POST /v1/auth/reset-password ---------->|
   |    Header: Authorization: Bearer <token>   |
   |    { new_password, confirm_new_password }  |
   |<-- 200 { data: { user_id, email } } ----  |
   |                                            |
   |   [Redirect to login page]                 |
```

---

### Logout

```
Frontend                                    Backend
   |                                            |
   |--- DELETE /v1/auth/logout ---------------->|
   |<-- 200 { msg: "Log Out successful" } ----  |
   |    (+ clears Authorization cookie)         |
   |                                            |
   |   Clear stored token. Redirect to login.   |
```

---

> **Deprecated:** `POST /v1/auth/magic_link/login` — Same request body as `otp/login`. Intended to deliver the 2FA challenge via a magic link in email instead of OTP. Currently **non-functional**. Do not implement.
