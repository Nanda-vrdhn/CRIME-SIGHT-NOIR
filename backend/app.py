"""CRIME SIGHT NOIR - Flask API server.

Run:
    pip install -r backend/requirements.txt
    python backend/app.py

Environment:
    PORT        listen port                 (default 4000)
    HOST        bind address                (default 127.0.0.1; use 0.0.0.0
                                             to expose on the LAN)
    FLASK_DEBUG "1" enables the Werkzeug debugger (never on a public host)
    CSN_DB_PATH override the SQLite file location
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Make the repository root importable no matter where the process is started.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from authentication.auth import auth_bp  # noqa: E402
from backend.database import DB_PATH, FRONTEND_FILE, get_db, init_db  # noqa: E402

# Force UTF-8 output on Windows so the emoji in the banner don't crash the
# console. Guarded: sys.stdout can be None (pythonw.exe) or a non-text stream.
_stdout = sys.stdout
if _stdout is not None and hasattr(_stdout, "reconfigure"):
    try:
        _stdout.reconfigure(encoding="utf-8", errors="replace")
    except (ValueError, OSError):
        pass

PORT = int(os.environ.get("PORT", "4000"))
HOST = os.environ.get("HOST", "127.0.0.1")
DEBUG = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")

app = Flask(__name__)
CORS(app)
app.register_blueprint(auth_bp)


# ── Helpers ────────────────────────────────────────────────────────────────

def get_severity(crime_type: str) -> str:
    """Classify a free-text crime type into Critical / High / Medium."""
    u = (crime_type or "").upper()
    if re.search(r"HOMICIDE|KIDNAP|SEXUAL|ARSON|HUMAN TRAF", u):
        return "Critical"
    if re.search(r"ROBBERY|ASSAULT|FIREARM|EXTORT|DRUG|COUNTER|IDENTITY", u):
        return "High"
    return "Medium"


def _body() -> dict:
    """Request payload as a dict; never None, never raises."""
    return request.get_json(silent=True) or {}


def _next_fir_number(conn) -> str:
    """Highest existing FIR number for the current year, plus one.

    Parses numerically instead of assuming every row matches ``FIR-2026-N``,
    which is what made the original version raise ValueError on unexpected data.
    """
    prefix = f"FIR-{datetime.now().year}-"
    best = 0
    for row in conn.execute(
        "SELECT fir_number FROM cases WHERE fir_number LIKE ?", (prefix + "%",)
    ):
        match = re.search(r"(\d+)$", row["fir_number"] or "")
        if match:
            best = max(best, int(match.group(1)))
    return f"{prefix}{best + 1}"


def _next_criminal_id(conn) -> str:
    """Next free ``CRIM-<n>`` id.

    The original sorted the text ids (``ORDER BY id DESC``) which returns
    ``CRIM-99`` for a table holding ``CRIM-100``..``CRIM-110`` and then crashes
    in ``int()``. Numbers are parsed instead.
    """
    best = None
    for row in conn.execute("SELECT id FROM criminals"):
        match = re.fullmatch(r"CRIM-(\d+)", row["id"] or "")
        if match:
            n = int(match.group(1))
            best = n if best is None else max(best, n)
    return f"CRIM-{100 if best is None else best + 1}"


def _exists(conn, table: str, column: str, value) -> bool:
    if value in (None, ""):
        return True
    return (
        conn.execute(f"SELECT 1 FROM {table} WHERE {column} = ?", (value,)).fetchone()
        is not None
    )


# ── Static frontend ────────────────────────────────────────────────────────

@app.route("/")
def index():
    if not FRONTEND_FILE.is_file():
        return jsonify(
            {"error": f"Frontend not found at {FRONTEND_FILE}"}
        ), 500
    return send_from_directory(str(FRONTEND_FILE.parent), FRONTEND_FILE.name)


# ── GET /api/stations ──────────────────────────────────────────────────────

@app.get("/api/stations")
def get_stations():
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT ps.*,
                   COUNT(c.id)                                             AS total_cases,
                   COALESCE(SUM(CASE WHEN c.severity='Critical' THEN 1 ELSE 0 END), 0) AS critical_count,
                   COALESCE(SUM(CASE WHEN c.status='Open'       THEN 1 ELSE 0 END), 0) AS open_count
            FROM police_stations ps
            LEFT JOIN cases c ON c.station_id = ps.id
            GROUP BY ps.id
            ORDER BY ps.state, ps.district
            """
        ).fetchall()
        return jsonify(rows)
    finally:
        conn.close()


# ── GET /api/stations/<id>/cases ───────────────────────────────────────────

@app.get("/api/stations/<int:station_id>/cases")
def get_station_cases(station_id: int):
    severity = request.args.get("severity")
    status = request.args.get("status")
    conn = get_db()
    try:
        query = """
            SELECT c.*,
                   ps.ps_code, ps.name AS station_name, ps.district, ps.state, ps.sector,
                   o.name  AS officer_name,  o.rank  AS officer_rank, o.squad AS officer_squad,
                   cr.name AS criminal_name, cr.age  AS criminal_age,
                   cr.address AS criminal_address, cr.photo_id AS criminal_photo
            FROM cases c
            INNER JOIN police_stations ps ON ps.id = c.station_id
            LEFT  JOIN officers         o  ON o.id  = c.officer_id
            LEFT  JOIN criminals        cr ON cr.id = c.criminal_id
            WHERE c.station_id = ?
        """
        params: list = [station_id]
        if severity:
            query += " AND c.severity = ?"
            params.append(severity)
        if status:
            query += " AND c.status = ?"
            params.append(status)
        query += (
            " ORDER BY CASE c.severity WHEN 'Critical' THEN 1 WHEN 'High' THEN 2"
            " ELSE 3 END, c.status"
        )
        return jsonify(conn.execute(query, params).fetchall())
    finally:
        conn.close()


# ── GET /api/cases ─────────────────────────────────────────────────────────

@app.get("/api/cases")
def get_cases():
    severity = request.args.get("severity")
    status = request.args.get("status")
    state = request.args.get("state")
    ps_code = request.args.get("psCode")
    conn = get_db()
    try:
        query = """
            SELECT c.*, ps.ps_code, ps.name AS station_name,
                   ps.district AS district, ps.state,
                   o.name AS officer_name, cr.name AS criminal_name
            FROM cases c
            INNER JOIN police_stations ps ON ps.id = c.station_id
            LEFT  JOIN officers         o  ON o.id  = c.officer_id
            LEFT  JOIN criminals        cr ON cr.id = c.criminal_id
            WHERE 1=1
        """
        params: list = []
        if severity:
            query += " AND c.severity=?"
            params.append(severity)
        if status:
            query += " AND c.status=?"
            params.append(status)
        if state:
            query += " AND ps.state=?"
            params.append(state)
        if ps_code:
            query += " AND ps.ps_code=?"
            params.append(ps_code)
        # fir_number is TEXT, so plain ORDER BY yields 1, 10, 11, ... 2.
        # LENGTH first restores numeric order (suffixes are not zero-padded).
        query += " ORDER BY LENGTH(c.fir_number), c.fir_number"
        return jsonify(conn.execute(query, params).fetchall())
    finally:
        conn.close()


# ── POST /api/cases ────────────────────────────────────────────────────────

@app.post("/api/cases")
def create_case():
    data = _body()
    station_id = data.get("stationId")
    crime_type = str(data.get("crimeType") or "").strip()

    if not isinstance(station_id, int) or not crime_type:
        return jsonify({"error": "stationId (integer) and crimeType are required"}), 400

    officer_id = data.get("officerId") or None
    criminal_id = data.get("criminalId") or None
    status = str(data.get("status") or "Open")
    handling = str(data.get("handling") or "Active")
    investigation_type = str(data.get("investigationType") or "Solo")
    crime_count = _int(data.get("crimeCount"), 1, minimum=1)
    completion_pct = _int(data.get("completionPct"), 0, minimum=0, maximum=100)
    remarks = str(data.get("remarks") or "—")
    arrest_date = str(data.get("arrestDate") or datetime.now().strftime("%Y-%m-%d"))

    conn = get_db()
    try:
        if not _exists(conn, "police_stations", "id", station_id):
            return jsonify({"error": f"Unknown stationId {station_id}"}), 400
        if not _exists(conn, "officers", "id", officer_id):
            return jsonify({"error": f"Unknown officerId {officer_id}"}), 400
        if not _exists(conn, "criminals", "id", criminal_id):
            return jsonify({"error": f"Unknown criminalId {criminal_id}"}), 400

        fir_number = _next_fir_number(conn)
        severity = get_severity(crime_type)
        conn.execute(
            """
            INSERT INTO cases
              (fir_number, station_id, officer_id, criminal_id, severity, crime_type,
               crime_count, status, handling, investigation_type, completion_pct,
               remarks, arrest_date, photo_resolution, assign_id, case_code)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'1920x1080','ASN-NEW','CASE-NEW')
            """,
            (
                fir_number, station_id, officer_id, criminal_id, severity, crime_type,
                crime_count, status, handling, investigation_type, completion_pct,
                remarks, arrest_date,
            ),
        )
        conn.commit()
        return jsonify(
            {
                "firNumber": fir_number,
                "stationId": station_id,
                "crimeType": crime_type,
                "severity": severity,
                "status": status,
            }
        ), 201
    finally:
        conn.close()


def _int(value, default, minimum=None, maximum=None) -> int:
    """Coerce a client-supplied value to an int, clamped to a range."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None and n < minimum:
        return minimum
    if maximum is not None and n > maximum:
        return maximum
    return n


# ── GET /api/stats ─────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*)                                                AS total_cases,
                   (SELECT COUNT(*) FROM police_stations)                  AS total_stations,
                   COALESCE(SUM(CASE WHEN severity='Critical' THEN 1 ELSE 0 END), 0) AS critical_cases,
                   COALESCE(SUM(CASE WHEN status='Open'       THEN 1 ELSE 0 END), 0) AS open_cases,
                   COALESCE(SUM(CASE WHEN status='Closed'     THEN 1 ELSE 0 END), 0) AS closed_cases
            FROM cases
            """
        ).fetchone()
        return jsonify(row)
    finally:
        conn.close()


# ── GET /api/officers ──────────────────────────────────────────────────────

@app.get("/api/officers")
def get_officers():
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT o.*,
                   COUNT(c.id)                                             AS total_cases,
                   COALESCE(SUM(CASE WHEN c.severity='Critical' THEN 1 ELSE 0 END), 0) AS critical_cases,
                   COALESCE(SUM(CASE WHEN c.status='Open'       THEN 1 ELSE 0 END), 0) AS open_cases,
                   COALESCE(SUM(CASE WHEN c.status='Closed'     THEN 1 ELSE 0 END), 0) AS closed_cases
            FROM officers o
            LEFT JOIN cases c ON c.officer_id = o.id
            GROUP BY o.id
            ORDER BY total_cases DESC
            """
        ).fetchall()
        return jsonify(rows)
    finally:
        conn.close()


# ── GET /api/officers/<id>/cases ───────────────────────────────────────────

@app.get("/api/officers/<officer_id>/cases")
def get_officer_cases(officer_id: str):
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT c.fir_number, c.crime_type, c.severity, c.status,
                   c.completion_pct, c.handling, c.arrest_date,
                   ps.name AS station_name, ps.ps_code, ps.district, ps.state,
                   cr.name AS criminal_name, cr.id AS criminal_id
            FROM cases c
            INNER JOIN police_stations ps ON ps.id = c.station_id
            LEFT  JOIN criminals        cr ON cr.id = c.criminal_id
            WHERE c.officer_id = ?
            ORDER BY CASE c.severity WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 ELSE 3 END
            """,
            (officer_id,),
        ).fetchall()
        return jsonify(rows)
    finally:
        conn.close()


# ── GET /api/criminals ─────────────────────────────────────────────────────

@app.get("/api/criminals")
def get_criminals():
    q = request.args.get("q", "").strip()
    conn = get_db()
    try:
        query = """
            SELECT cr.*,
                   COUNT(c.id)                  AS fir_count,
                   COUNT(DISTINCT c.station_id) AS station_count
            FROM criminals cr
            LEFT JOIN cases c ON c.criminal_id = cr.id
            WHERE 1=1
        """
        params: list = []
        if q:
            query += " AND (cr.name LIKE ? OR cr.id LIKE ? OR cr.address LIKE ?)"
            like = f"%{q}%"
            params.extend([like, like, like])
        query += " GROUP BY cr.id ORDER BY fir_count DESC"
        return jsonify(conn.execute(query, params).fetchall())
    finally:
        conn.close()


# ── GET /api/criminals/<id> ────────────────────────────────────────────────

@app.get("/api/criminals/<criminal_id>")
def get_criminal(criminal_id: str):
    conn = get_db()
    try:
        criminal = conn.execute(
            "SELECT * FROM criminals WHERE id = ?", (criminal_id,)
        ).fetchone()
        if not criminal:
            return jsonify({"error": "Criminal not found"}), 404

        cases = conn.execute(
            """
            SELECT c.fir_number, c.crime_type, c.severity, c.status,
                   c.completion_pct, c.handling, c.investigation_type, c.arrest_date,
                   ps.name AS station_name, ps.ps_code, ps.district, ps.state,
                   ps.lat, ps.lng,
                   o.name AS officer_name, o.rank AS officer_rank
            FROM cases c
            INNER JOIN police_stations ps ON ps.id = c.station_id
            LEFT  JOIN officers         o  ON o.id  = c.officer_id
            WHERE c.criminal_id = ?
            ORDER BY c.arrest_date DESC
            """,
            (criminal_id,),
        ).fetchall()

        stations = conn.execute(
            """
            SELECT ps.*, COUNT(c.id) AS fir_count
            FROM police_stations ps
            LEFT JOIN cases c ON c.station_id = ps.id AND c.criminal_id = ?
            GROUP BY ps.id
            HAVING fir_count > 0
            ORDER BY fir_count DESC
            """,
            (criminal_id,),
        ).fetchall()

        return jsonify({"criminal": criminal, "cases": cases, "stations": stations})
    finally:
        conn.close()


# ── POST /api/criminals ────────────────────────────────────────────────────

@app.post("/api/criminals")
def create_criminal():
    data = _body()
    name = str(data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    if len(name) > 200:
        return jsonify({"error": "Name must be 200 characters or fewer"}), 400

    age = _int(data.get("age"), 25, minimum=0, maximum=150)
    address = str(data.get("address") or "").strip() or "Unknown"
    alias = str(data.get("alias") or "").strip()
    photo_id = str(data.get("photoId") or "").strip()

    conn = get_db()
    try:
        new_id = _next_criminal_id(conn)
        if not photo_id:
            number = re.search(r"(\d+)$", new_id)
            photo_id = f"IMG-{int(number.group(1)) - 99:04d}" if number else "IMG-0000"

        conn.execute(
            "INSERT INTO criminals (id,name,age,address,photo_id,alias) "
            "VALUES (?,?,?,?,?,?)",
            (new_id, name, age, address, photo_id, alias),
        )
        conn.commit()
        return jsonify(
            {
                "id": new_id,
                "name": name,
                "age": age,
                "address": address,
                "photoId": photo_id,
                "alias": alias,
            }
        ), 201
    finally:
        conn.close()


# ── GET /api/analytics ─────────────────────────────────────────────────────

@app.get("/api/analytics")
def get_analytics():
    conn = get_db()
    try:
        totals = conn.execute(
            """
            SELECT COUNT(*)                                                AS total,
                   COALESCE(SUM(CASE WHEN severity='Critical' THEN 1 ELSE 0 END), 0) AS crit,
                   COALESCE(SUM(CASE WHEN severity='High'     THEN 1 ELSE 0 END), 0) AS hi,
                   COALESCE(SUM(CASE WHEN severity='Medium'   THEN 1 ELSE 0 END), 0) AS med,
                   COALESCE(SUM(CASE WHEN status='Open'                THEN 1 ELSE 0 END), 0) AS opn,
                   COALESCE(SUM(CASE WHEN status='Closed'              THEN 1 ELSE 0 END), 0) AS cls,
                   COALESCE(SUM(CASE WHEN status='Under Investigation' THEN 1 ELSE 0 END), 0) AS unv
            FROM cases
            """
        ).fetchone()

        by_state = {
            r["state"]: r["count"]
            for r in conn.execute(
                """
                SELECT ps.state, COUNT(c.id) AS count
                FROM cases c INNER JOIN police_stations ps ON ps.id = c.station_id
                GROUP BY ps.state ORDER BY count DESC
                """
            ).fetchall()
        }
        by_type = {
            r["crime_type"]: r["count"]
            for r in conn.execute(
                """
                SELECT crime_type, COUNT(*) AS count
                FROM cases GROUP BY crime_type ORDER BY count DESC LIMIT 10
                """
            ).fetchall()
        }
        counts = {
            key: conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
            for key, table in (
                ("totalStations", "police_stations"),
                ("totalOfficers", "officers"),
                ("totalCriminals", "criminals"),
            )
        }
        return jsonify(
            {
                "totalCases": totals["total"],
                **counts,
                "criticalCases": totals["crit"],
                "highCases": totals["hi"],
                "mediumCases": totals["med"],
                "openCases": totals["opn"],
                "closedCases": totals["cls"],
                "underInvCases": totals["unv"],
                "byState": by_state,
                "byType": by_type,
            }
        )
    finally:
        conn.close()


# ── JSON error handlers (the original returned HTML error pages) ───────────

@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(409)
@app.errorhandler(422)
def _http_error(err):
    """Flask passes the HTTPException instance, not the bare status code."""
    status = getattr(err, "code", None)
    if not isinstance(status, int):
        status = 500
    message = _MESSAGE.get(status, "Error")
    description = getattr(err, "description", None)
    if description and description != _MESSAGE.get(status):
        message = description
    return jsonify({"error": {"status": status, "message": message}}), status


@app.errorhandler(500)
def _server_error(_error):
    app.logger.exception("Unhandled server error")
    return jsonify({"error": {"status": 500, "message": "Internal server error"}}), 500


_MESSAGE = {
    400: "Bad request",
    404: "Not found",
    405: "Method not allowed",
    409: "Conflict",
    422: "Unprocessable entity",
}


# ── Entry point ────────────────────────────────────────────────────────────

def main() -> None:
    print("\n🔍 CRIME SIGHT NOIR — Flask backend")
    print(f"   Database : {DB_PATH}")
    init_db()
    print(f"\n   Server   : http://{HOST}:{PORT}")
    print(f"   Frontend : http://{HOST}:{PORT}/")
    print("\n   POST /api/auth/login      POST /api/auth/signup")
    print("   GET  /api/stations        GET  /api/stations/<id>/cases")
    print("   GET  /api/cases           POST /api/cases")
    print("   GET  /api/stats           GET  /api/analytics")
    print("   GET  /api/officers        GET  /api/officers/<id>/cases")
    print("   GET  /api/criminals       GET  /api/criminals/<id>")
    print("   POST /api/criminals\n")
    app.run(host=HOST, port=PORT, debug=DEBUG)


if __name__ == "__main__":
    main()
