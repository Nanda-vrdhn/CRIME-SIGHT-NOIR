# `authentication/` — login and signup

A Flask **blueprint** (`auth_bp`, prefix `/api/auth`) so the account logic lives
on its own instead of being mixed into the main route file.

| Route                | Method | Returns                          |
| -------------------- | ------ | -------------------------------- |
| `/api/auth/login`    | POST   | session object (200) / 401       |
| `/api/auth/signup`   | POST   | session object (201) / 400 / 409 |

Both endpoints are registered by `backend/app.py`:

```python
from authentication.auth import auth_bp
app.register_blueprint(auth_bp)
```

## Session object

This is what the browser stores in `localStorage` under the key `csn`:

```jsonc
{
  "username":    "cop1",
  "role":        "police",         // public | police | admin
  "display":     "Cop",
  "stationCode": "PS-430",         // may be null
  "token":       "csn-police-9f3c…",
  // profile fields below are only present when the account has them
  "badge":        "42",
  "rank":         "Inspector",
  "stationName":  "Hyderabad Central PS",
  "district":     "Hyderabad",
  "state":        "Telangana",
  "squad":        "Squad Bh-11",
  "officialId":   "GOV-1",         // admin accounts
  "designation":  "SP",
  "department":   "Home",
  "zone":         "Zone-1"
}
```

**Keys are camelCase.** The database columns are snake_case
(`station_name`, `official_id`); `_PROFILE_COLUMNS` in `auth.py` performs the
translation. The frontend reads `CU.stationName` and `CU.officialId`, so
returning the raw column names silently broke those two fields — they used to
render as `undefined`/`—`.

## Password storage

- New and existing passwords are stored as **Werkzeug `pbkdf2:sha256` hashes**.
- Rows written by older versions of this project held plain text. `_check_password`
  still accepts them, and `login()` re-hashes the row on the first successful
  login, so old databases upgrade themselves.

```python
from werkzeug.security import generate_password_hash, check_password_hash
```

## Validation

| Check                       | HTTP |
| --------------------------- | ---- |
| username matches `[A-Za-z0-9_.-]{3,32}` | 400 |
| password ≥ 6 characters     | 400 |
| username already taken      | 409 |
| `police` without badge/rank/station | 400 |
| `admin` without officialId/designation/department | 400 |
| unknown role                | 400 |

## Limits

There is **no rate limiting**, no account lockout, no email verification and no
password reset. See [`../docs/SECURITY.md`](../docs/SECURITY.md).
