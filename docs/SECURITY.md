# Security notes

> **This is a student mini-project.** It is safe to run on `127.0.0.1` for a
> demo or coursework. It is **not** safe to expose to the internet. This page
> records what has been fixed and what deliberately remains open, so nobody
> mistakes a demo for a hardened service.

## What has been fixed

### 1. Passwords are hashed

Previously every account — including the demo ones — stored its password in
plain text in the `users` table.

```python
# authentication/auth.py
generate_password_hash(password, method="pbkdf2:sha256")   # at rest
check_password_hash(stored, given)                         # on login
```

Rows created by older versions of the project are still plain text, so
`_check_password()` falls back to a constant-time comparison and `login()`
re-hashes the row on the first successful login. Old databases upgrade
themselves.

### 2. Stored XSS in the UI

Criminal names, addresses and FIR remarks are free text that arrives from the
API and was interpolated straight into `innerHTML`. A single record containing
`<img src=x onerror=…>` would run script for anyone who opened the criminal
list.

Every such interpolation now goes through `esc()`, which HTML-escapes
`& < > " '`. Fields written with `textContent` are inherently safe.

### 3. Werkzeug debugger turned off by default

The server previously ran with `debug=True` on `0.0.0.0`. The Werkzeug debugger
exposes an interactive console, and its PIN is guessable enough that this is a
well-known **remote code execution** vector on anything reachable from a network.

Now: `debug` is off unless `FLASK_DEBUG=1`, and the bind address defaults to
`127.0.0.1`.

### 4. Input validation

`_body()` uses `get_json(silent=True) or {}`, so a missing or malformed body
becomes a `400` instead of a `500`. Numbers are coerced and clamped by `_int()`,
foreign keys are checked with `_exists()` before every `INSERT`, and usernames
are matched against `[A-Za-z0-9_.-]{3,32}`.

### 5. SQL injection

All queries are parameterised. The only interpolated identifiers are table and
column names taken from module-level allow-lists (`_USER_COLUMNS`, the tuple in
`table_counts()`), never from request data.

## What remains — by design

| Gap | Why it is still here |
| --- | -------------------- |
| **The session `token` is never verified** | It is an opaque, unique string returned to the browser; no route checks it. Adding enforcement would break the frontend, which does not send an `Authorization` header. |
| **No rate limiting / lockout** | A login endpoint that never throttles allows password guessing. |
| **No HTTPS** | Credentials and session objects travel in clear text. |
| **CORS allows all origins** | `CORS(app)` with no restrictions. |
| **All read endpoints are unauthenticated** | Anyone who can reach the port can read every case. |
| **Demo passwords are printed in the UI** | `public123`, `police123`, `govt2026` are shown on the login screen. |
| **No password reset, no email verification, no MFA** | Out of scope for the project. |
| **Flask's development server** | Not a production WSGI server; see `docs/SETUP.md`. |

## If you need to actually deploy this

At minimum: terminate TLS, put it behind a real WSGI server (gunicorn/uwsgi)
and a reverse proxy, replace the token with signed sessions (e.g.
`Flask-Login` + `itsdangerous`) enforced on every non-public route, add rate
limiting to `/api/auth/*`, lock CORS to known origins, remove the demo accounts
and their visible passwords, and set a secret key from the environment.

## Reporting

This repository is coursework, not a maintained product, so there is no
disclosure process. If you are a student forking it, treat the table above as
your to-do list.
