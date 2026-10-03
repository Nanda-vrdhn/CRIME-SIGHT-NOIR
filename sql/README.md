# `sql/` — schema and seed data

Both files here are the **single source of truth** for the database. Nothing else
in the repository defines tables or demo data; `backend/database.py` simply
executes these two files at startup.

| File         | Purpose                                                             |
| ------------ | ------------------------------------------------------------------- |
| `schema.sql` | `CREATE TABLE IF NOT EXISTS …` for all five tables                   |
| `seed.sql`   | `BEGIN TRANSACTION;` … `COMMIT;` inserting the demo dataset          |

## Why SQL and not Python dicts

The original project stored the seed data as Python dictionaries inside the
backend file, which meant the schema and the data were only reachable by reading
700+ lines of application code. Keeping them here means:

- a DBA can load the database without running the app,
- the backend no longer carries ~160 lines of seed constants,
- schema changes are reviewable as SQL diffs.

## Tables

| Table            | Rows | Notes                                                   |
| ---------------- | ---- | ------------------------------------------------------- |
| `police_stations`| 25   | `ps_code` is unique; ids 1–25 are explicit so FIRs that reference them stay valid |
| `officers`       | 20   | `id` looks like `ASN-9003`                              |
| `criminals`      | 11   | `id` looks like `CRIM-100`, `photo_id` like `IMG-0001`  |
| `cases`          | 75   | `fir_number` (`FIR-2026-1`) is the natural key          |
| `users`          | 3    | demo logins; `password` is a Werkzeug pbkdf2:sha256 hash|

## Loading it manually

```bash
sqlite3 backend/crimesight.db < sql/schema.sql
sqlite3 backend/crimesight.db < sql/seed.sql
```

…though the server does this for you, so you only need this if you want to
rebuild the database by hand.

## Resetting

```bash
rm backend/crimesight.db*
```

The next `python backend/app.py` recreates and reseeds it.

## Notes for contributors

- **Add a table** → add it to `schema.sql`; there is no other migration step.
- **Add seed rows** → edit `seed.sql`. Keep `INSERT OR IGNORE` so the script
  stays idempotent.
- **`station_id` in `cases` is a fixed integer** matching the explicit id in the
  `police_stations` insert directly above it. If you renumber stations you must
  renumber the cases too.
- **Never store a plain-text password.** Generate a hash with:

  ```python
  from werkzeug.security import generate_password_hash
  print(generate_password_hash("your-password"))
  ```
