# `backend/` — Flask API server

## Files

| File            | Responsibility                                                      |
| --------------- | ------------------------------------------------------------------- |
| `app.py`        | Route definitions, request validation, JSON error handlers          |
| `database.py`   | Connection factory, schema creation, first-run seeding, migrations  |
| `requirements.txt` | Runtime dependencies                                              |

Login and signup are **not** in `app.py` — they live in
[`../authentication/auth.py`](../authentication/auth.py).

## Run it

```bash
pip install -r backend/requirements.txt
python backend/app.py
```

Paths are resolved from `__file__`, so the working directory does not matter:

```bash
python /anywhere/CRIME-SIGHT-NOIR/backend/app.py   # works
```

## Environment variables

| Variable       | Default             | Meaning                                              |
| -------------- | ------------------- | ---------------------------------------------------- |
| `PORT`         | `4000`              | Listen port                                          |
| `HOST`         | `127.0.0.1`         | Bind address; set `0.0.0.0` to expose on the LAN     |
| `FLASK_DEBUG`  | *(off)*             | `1` enables the Werkzeug debugger — **never** on a public host |
| `CSN_DB_PATH`  | `backend/crimesight.db` | SQLite file location (used by the test suite)    |

## Request flow

```
browser ──► Flask route
              │  _body()          parse JSON, tolerate a missing/invalid body
              │  _int()           coerce + clamp client-supplied numbers
              │  _exists()        validate foreign keys before INSERT
              ▼
           get_db()  ──►  sqlite3 (rows as dicts)
              │
              └── try/finally: conn.close()   ← no leaks on the error path
```

## Helper functions in `app.py`

| Helper | Purpose |
| ------ | ------- |
| `get_severity(crime_type)` | `HOMICIDE|KIDNAP|SEXUAL|ARSON|HUMAN TRAF` → Critical, `ROBBERY|ASSAULT|FIREARM|EXTORT|DRUG|COUNTER|IDENTITY` → High, else Medium |
| `_body()` | `request.get_json(silent=True) or {}` — never `None`, never raises |
| `_int(value, default, min, max)` | Safe int coercion with clamping |
| `_next_fir_number(conn)` | Next `FIR-<year>-<n>` for the **current year**, parsed numerically |
| `_next_criminal_id(conn)` | Next free `CRIM-<n>`, parsed numerically |
| `_exists(conn, table, col, val)` | Foreign-key check before insert |

### Why the ID generators parse numerically

The originals sorted text:

```python
conn.execute("SELECT id FROM criminals ORDER BY id DESC LIMIT 1").fetchone()
```

With ids `CRIM-100 … CRIM-110`, lexicographic `DESC` returns `CRIM-110` — but if
`CRIM-99` ever existed it would win, and `int("CRIM-99".replace("CRIM-",""))`
then compares against `CRIM-111` incorrectly. Worse, `int(last['fir_number']
.replace('FIR-2026-', ''))` raises `ValueError` the moment the year rolls over
or a row doesn't match the expected prefix. Both helpers now extract digits with
`re` and take the maximum.

## Error handling

Every error returns JSON, never an HTML error page:

```json
{ "error": { "status": 404, "message": "Not found" } }
```

`400 / 404 / 405 / 409 / 422` share `_http_error`, which reads `err.code` from
the `HTTPException` Flask passes in (treating the argument as a bare status code
made every 404 report `500`). `500` is handled separately and logs a traceback.

## Tests

A 65-assertion smoke suite lives in
[`../tests/test_api.py`](../tests/test_api.py). It runs against a throwaway
database (`CSN_DB_PATH`) and covers every route, the auth happy/sad paths,
hashing at rest, ID generation, and JSON error shapes.

```bash
python tests/test_api.py
```
