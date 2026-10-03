-- ====================================================================
-- CRIME SIGHT NOIR - DATABASE SCHEMA (SQLite)
-- Single source of truth: executed by backend/database.py at startup.
-- ====================================================================

CREATE TABLE IF NOT EXISTS police_stations (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ps_code  TEXT NOT NULL UNIQUE,
            name     TEXT NOT NULL,
            district TEXT NOT NULL,
            state    TEXT NOT NULL,
            lat      REAL NOT NULL,
            lng      REAL NOT NULL,
            sector   TEXT
        );
        CREATE TABLE IF NOT EXISTS officers (
            id    TEXT PRIMARY KEY,
            name  TEXT NOT NULL,
            squad TEXT,
            rank  TEXT
        );
        CREATE TABLE IF NOT EXISTS criminals (
            id       TEXT PRIMARY KEY,
            name     TEXT NOT NULL,
            age      INTEGER,
            address  TEXT,
            photo_id TEXT,
            alias    TEXT
        );
        CREATE TABLE IF NOT EXISTS cases (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            fir_number         TEXT NOT NULL UNIQUE,
            station_id         INTEGER,
            officer_id         TEXT,
            criminal_id        TEXT,
            assign_id          TEXT,
            case_code          TEXT,
            status             TEXT NOT NULL,
            severity           TEXT NOT NULL,
            crime_type         TEXT NOT NULL,
            crime_count        INTEGER DEFAULT 1,
            completion_pct     INTEGER DEFAULT 0,
            handling           TEXT,
            investigation_type TEXT,
            arrest_date        TEXT,
            photo_resolution   TEXT,
            remarks            TEXT,
            transfers          INTEGER DEFAULT 0,
            experience_years   INTEGER DEFAULT 0,
            FOREIGN KEY (station_id)  REFERENCES police_stations(id),
            FOREIGN KEY (officer_id)  REFERENCES officers(id),
            FOREIGN KEY (criminal_id) REFERENCES criminals(id)
        );
        CREATE TABLE IF NOT EXISTS users (
            username    TEXT PRIMARY KEY,
            password    TEXT NOT NULL,
            role        TEXT NOT NULL,
            display     TEXT NOT NULL,
            station_code TEXT,
            badge       TEXT,
            rank        TEXT,
            station_name TEXT,
            district    TEXT,
            state       TEXT,
            squad       TEXT,
            official_id TEXT,
            designation TEXT,
            department  TEXT,
            zone        TEXT
        );
