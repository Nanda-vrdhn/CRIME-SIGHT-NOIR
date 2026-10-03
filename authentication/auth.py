"""Authentication endpoints: ``POST /api/auth/login`` and ``POST /api/auth/signup``.

Passwords are stored as Werkzeug pbkdf2:sha256 hashes. Rows created by older
versions of this project held plain-text passwords; those still verify and are
re-hashed transparently on the next successful login.

Note on the session token: it is an opaque, unique identifier returned to the
browser for convenience. It is *not* signed and is *not* checked on the other
API routes, which are read-only demos. See ``docs/SECURITY.md``.
"""
from __future__ import annotations

import hmac
import re
import secrets

from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from backend.database import get_db

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

#: DB column -> key returned to the client. The frontend expects camelCase.
_PROFILE_COLUMNS = {
    "badge": "badge",
    "rank": "rank",
    "station_name": "stationName",
    "district": "district",
    "state": "state",
    "squad": "squad",
    "official_id": "officialId",
    "designation": "designation",
    "department": "department",
    "zone": "zone",
}

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
_ROLES = ("public", "police", "admin")
_HASH_PREFIXES = ("pbkdf2:", "scrypt:", "argon2:")


def _json():
    """Parse the request body without raising on a missing/invalid payload."""
    return request.get_json(silent=True) or {}


def _check_password(stored: str, given: str) -> bool:
    """Verify a password against a hash, tolerating legacy plain-text rows."""
    if not stored or not given:
        return False
    if stored.startswith(_HASH_PREFIXES):
        return check_password_hash(stored, given)
    try:
        return hmac.compare_digest(stored, given)
    except (TypeError, UnicodeEncodeError):
        return stored == given


def _profile(row: dict) -> dict:
    out = {}
    for column, key in _PROFILE_COLUMNS.items():
        value = row.get(column)
        if value not in (None, ""):
            out[key] = value
    return out


def _session(row: dict) -> dict:
    """Build the object the frontend stores in localStorage."""
    resp = {
        "username": row["username"],
        "role": row["role"],
        "display": row["display"],
        "stationCode": row.get("station_code"),
        "token": f"csn-{row['role']}-{secrets.token_hex(16)}",
    }
    resp.update(_profile(row))
    return resp


@auth_bp.post("/login")
def login():
    data = _json()
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row is None or not _check_password(row.get("password"), password):
            return jsonify({"error": "Invalid credentials"}), 401

        # Upgrade a legacy plain-text password the first time it is used.
        stored = row.get("password")
        if stored and not stored.startswith(_HASH_PREFIXES):
            hashed = generate_password_hash(password)
            conn.execute(
                "UPDATE users SET password = ? WHERE username = ?",
                (hashed, username),
            )
            conn.commit()
            row = dict(row)
            row["password"] = hashed

        return jsonify(_session(row))
    finally:
        conn.close()


@auth_bp.post("/signup")
def signup():
    data = _json()

    name = str(data.get("name") or "").strip()
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    role = str(data.get("role") or "public").strip()
    station_code = data.get("stationCode") or None

    if not name or not username or not password:
        return jsonify({"error": "Name, username and password are required"}), 400
    if not _USERNAME_RE.match(username):
        return jsonify(
            {"error": "Username must be 3-32 characters: letters, digits, . _ -"}
        ), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if role not in _ROLES:
        return jsonify({"error": f"role must be one of {', '.join(_ROLES)}"}), 400

    profile = {
        "badge": data.get("badge"),
        "rank": data.get("rank"),
        "station_name": data.get("stationName"),
        "district": data.get("district"),
        "state": data.get("state"),
        "squad": data.get("squad"),
        "official_id": data.get("officialId"),
        "designation": data.get("designation"),
        "department": data.get("department"),
        "zone": data.get("zone"),
    }

    # Role-specific requirements, mirrored from the signup form.
    if role == "police" and not all(
        [profile["badge"], profile["rank"], station_code]
    ):
        return jsonify(
            {"error": "Badge number, rank and station are required for Police Officers"}
        ), 400
    if role == "admin" and not all(
        [profile["official_id"], profile["designation"], profile["department"]]
    ):
        return jsonify(
            {"error": "Official ID, designation and department are required for Govt Officials"}
        ), 400

    conn = get_db()
    try:
        if conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone():
            return jsonify({"error": "Username already exists"}), 409

        conn.execute(
            """
            INSERT INTO users
              (username, password, role, display, station_code,
               badge, rank, station_name, district, state, squad,
               official_id, designation, department, zone)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                username,
                generate_password_hash(password),
                role,
                name,
                station_code,
                profile["badge"],
                profile["rank"],
                profile["station_name"],
                profile["district"],
                profile["state"],
                profile["squad"],
                profile["official_id"],
                profile["designation"],
                profile["department"],
                profile["zone"],
            ),
        )
        conn.commit()

        row = {
            "username": username,
            "role": role,
            "display": name,
            "station_code": station_code,
            **profile,
        }
        return jsonify(_session(row)), 201
    finally:
        conn.close()
