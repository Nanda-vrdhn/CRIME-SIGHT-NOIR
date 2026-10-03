# Setup & operations

## Requirements

- Python **3.9+** (developed and tested on 3.12)
- `pip` — no other tooling, database server or build step is required

SQLite ships with Python, and the frontend is a single static file served by the
backend.

## Install and run

```bash
git clone https://github.com/Nanda-vrdhn/CRIME-SIGHT-NOIR.git
cd CRIME-SIGHT-NOIR

pip install -r backend/requirements.txt
python backend/app.py
```

Open **http://localhost:4000/**

On first run the server:

1. creates `backend/crimesight.db`,
2. executes `sql/schema.sql`,
3. executes `sql/seed.sql` (only when the station table is empty),
4. adds any missing `users` columns needed by an older database,
5. listens on `127.0.0.1:4000`.

Nothing to migrate, nothing to configure.

## Environment variables

| Variable         | Default                    | Purpose |
| ---------------- | -------------------------- | ------- |
| `PORT`           | `4000`                     | Listen port |
| `HOST`           | `127.0.0.1`                | Bind address. Use `0.0.0.0` to accept LAN connections |
| `FLASK_DEBUG`    | *(off)*                    | `1` turns on the Werkzeug debugger |
| `CSN_DB_PATH`    | `backend/crimesight.db`    | Override the SQLite file location |

Examples (PowerShell):

```powershell
$env:PORT = "8080";            python backend/app.py
$env:HOST = "0.0.0.0";         python backend/app.py
$env:FLASK_DEBUG = "1";        python backend/app.py   # local debugging only
```

## Resetting the data

```powershell
Remove-Item backend\crimesight.db*
```

Restart the server and it reseeds from `sql/seed.sql`.

## Running on a different port or host

```powershell
$env:PORT = "5000"; python backend/app.py
```

The frontend follows automatically — when the page is served by Flask it uses
the same origin, so no configuration change is needed.

## Tests

```bash
python tests/test_api.py
```

65 assertions covering every route, both auth flows, password hashing, ID
generation and the JSON error shapes. The suite writes to a temporary database
and does not touch `backend/crimesight.db`.

## Troubleshooting

| Symptom | Cause / fix |
| ------- | ----------- |
| `ModuleNotFoundError: No module named 'flask'` | `pip install -r backend/requirements.txt` |
| `Missing SQL file: …\sql\schema.sql` | Incomplete checkout — `sql/` must be committed alongside `backend/` |
| Login says *"Backend is offline"* | The server isn't running, or `API_BASE` points somewhere else |
| Port already in use | `set PORT=4001` or stop the other process |
| Data looks wrong after an edit | Delete `backend/crimesight.db*` to reseed |
| Emoji crash in the console (`UnicodeEncodeError`) | stdout is not UTF-8; `app.py` reconfigures it, but a `pythonw.exe`/redirect setup may still need `PYTHONIOENCODING=utf-8` |
