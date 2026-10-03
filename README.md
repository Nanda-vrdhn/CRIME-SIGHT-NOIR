# CRIME-SIGHT-NOIR

CrimeSightNoir is an advanced, map-based Police Intelligence DBMS for South India.
Featuring a sleek, dark cyber-intelligence aesthetic, this centralized dashboard
allows law enforcement to visualize crime hotspots, manage active FIRs, and track
criminals and officers in real-time.

**Live demo:** https://crimedbmsminiproject.netlify.app/

---

## Repository layout

The project is split by concern instead of being a handful of loose files:

```
CRIME-SIGHT-NOIR/
├── README.md              ← you are here: project description & quick start
├── .gitignore
├── frontend/              ← the single-page UI
│   ├── README.md
│   └── index.html         ← markup, CSS and vanilla JS in one file
├── backend/               ← Flask API server
│   ├── README.md
│   ├── app.py             ← routes, validation, JSON error handling
│   ├── database.py        ← connections, schema creation, first-run seeding
│   ├── __init__.py
│   └── requirements.txt
├── authentication/        ← login / signup, split out as a Flask blueprint
│   ├── README.md
│   ├── auth.py
│   └── __init__.py
├── sql/                   ← database schema and seed data (single source of truth)
│   ├── README.md
│   ├── schema.sql         ← DDL, executed at startup
│   └── seed.sql           ← 25 stations, 20 officers, 11 criminals, 75 FIRs, 3 users
├── docs/                  ← extended documentation
│   ├── SETUP.md           ← install & run, environment variables
│   ├── API.md             ← every endpoint with request/response shapes
│   └── SECURITY.md        ← what is and is not protected
└── tests/                 ← API smoke tests (65 assertions)
    └── test_api.py
```

| Folder          | Responsibility                                             |
| --------------- | ---------------------------------------------------------- |
| `frontend/`     | Presentation: map, analytics, officer & criminal dashboards |
| `backend/`      | HTTP API, validation, business rules                        |
| `authentication/` | Accounts, password hashing, session payloads              |
| `sql/`          | Schema and seed data (no application logic)                 |
| `docs/`         | Long-form documentation                                     |
| `tests/`        | API smoke tests, run against a throwaway database           |

---

## Quick start

```bash
pip install -r backend/requirements.txt
python backend/app.py
```

Then open **http://localhost:4000/** — the server also serves the frontend, so no
second process or build step is needed.

The SQLite database is created and seeded automatically on first run at
`backend/crimesight.db`. Delete that file to reset all data.

### Demo accounts

| Role            | Username   | Password    | Permissions                          |
| --------------- | ---------- | ----------- | ------------------------------------ |
| Public          | `public`   | `public123` | View map, analytics, records         |
| Police Officer  | `officer`  | `police123` | File FIRs, add criminals             |
| Govt Official   | `admin`    | `govt2026`  | Everything a police officer can do   |

> These are demo accounts for a student mini-project — see
> [`docs/SECURITY.md`](docs/SECURITY.md) before putting this anywhere near a
> real network.

---

## Features

- **Map view** — 25 police stations across Telangana, Andhra Pradesh, Kerala,
  Tamil Nadu and Puducherry, with per-station case lists and suspect chips.
- **Analytics** — severity, status, state and crime-type breakdowns (Chart.js).
- **Officers** — workload and case history per officer.
- **Criminals** — searchable profile pages with every FIR on record and a
  mini-map of the stations that have handled them.
- **FIR registration** — new cases get an auto-generated `FIR-<year>-<n>` number
  and a severity derived from the crime type.
- **Authentication** — signup and login for the three roles above.

---

## API

Nine JSON GET endpoints plus four POST endpoints (login, signup, FIR, criminal),
and `GET /` which serves the page. Full request and response shapes in
[`docs/API.md`](docs/API.md).

```
POST /api/auth/login          POST /api/auth/signup
GET  /api/stations            GET  /api/stations/<id>/cases
GET  /api/cases               POST /api/cases
GET  /api/stats               GET  /api/analytics
GET  /api/officers            GET  /api/officers/<id>/cases
GET  /api/criminals           GET  /api/criminals/<id>
POST /api/criminals
```

## Tech stack

- **Frontend:** vanilla HTML/CSS/JS, Leaflet (map), Chart.js
- **Backend:** Python 3, Flask, flask-cors
- **Database:** SQLite via the standard-library `sqlite3` module

## License

Educational / coursework project.
