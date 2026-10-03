"""Smoke tests for the CRIME SIGHT NOIR API.

Run, from anywhere:

    python tests/test_api.py

Every route, both auth flows, password hashing, ID generation and the JSON
error shapes are covered (65 assertions). The suite writes to a throwaway
database, so it never touches backend/crimesight.db.
"""
import os
import sys
import tempfile
import traceback

# Repository root == the parent of this tests/ directory.
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, ROOT)

# Isolate the test database from the developer's real one.
_tmp = tempfile.mkdtemp(prefix="csn-test-")
os.environ["CSN_DB_PATH"] = os.path.join(_tmp, "test.db")

from backend.app import app            # noqa: E402
from backend.database import init_db, table_counts  # noqa: E402

FAILURES = []
PASSES = []


def check(label, cond, detail=""):
    if cond:
        PASSES.append(label)
    else:
        FAILURES.append(f"{label} :: {detail}")
        print(f"  FAIL  {label}  {detail}")


init_db()
counts = table_counts()
print("counts:", counts)
check("seed stations == 25", counts["police_stations"] == 25, str(counts))
check("seed officers == 20", counts["officers"] == 20, str(counts))
check("seed criminals == 11", counts["criminals"] == 11, str(counts))
check("seed cases == 75", counts["cases"] == 75, str(counts))
check("seed users == 3", counts["users"] == 3, str(counts))

c = app.test_client()


def j(resp):
    return resp.get_json()


# ── reads ──────────────────────────────────────────────────────────────────
r = c.get("/api/stations")
d = j(r)
check("GET /api/stations 200", r.status_code == 200, r.status_code)
check("stations count 25", isinstance(d, list) and len(d) == 25, str(len(d or [])))
check("station critical_count is int", isinstance(d[0]["critical_count"], int),
      repr(d[0].get("critical_count")))

r = c.get("/api/cases")
check("GET /api/cases 200 -> 75", r.status_code == 200 and len(j(r)) == 75,
      f"{r.status_code} {len(j(r) or [])}")
check("GET /api/cases includes station district",
      j(r)[0].get("district") not in (None, ""), str(j(r)[0].get("district")))

fns = [x["fir_number"] for x in j(r)]
check("cases ordered numerically (not 1,10,11...2)",
      fns == sorted(fns, key=lambda s: (len(s), s)),
      f"first 8: {fns[:8]}")

r = c.get("/api/cases?severity=Critical")
check("filter severity", len(j(r)) > 0, "no critical cases")

r = c.get("/api/cases?state=Kerala&psCode=NOPE-999")
check("impossible filter -> empty", j(r) == [], str(j(r)))

r = c.get("/api/stations/1/cases")
check("station cases 200", r.status_code == 200 and len(j(r)) > 0, r.status_code)

r = c.get("/api/stats")
s = j(r)
check("stats totals", s["total_cases"] == 75 and s["total_stations"] == 25, str(s))
check("stats not null", all(v is not None for v in s.values()), str(s))

r = c.get("/api/officers")
check("officers 20", len(j(r)) == 20, str(len(j(r) or [])))
check("officers counts are ints",
      all(isinstance(o["critical_cases"], int) for o in j(r)), "")

r = c.get("/api/officers/ASN-9003/cases")
check("officer cases 200", r.status_code == 200, r.status_code)

r = c.get("/api/criminals")
check("criminals 11", len(j(r)) == 11, str(len(j(r) or [])))

r = c.get("/api/criminals/CRIM-100")
check("criminal detail 200", r.status_code == 200, r.status_code)
check("criminal stations list", len(j(r)["stations"]) > 0, str(j(r).get("stations")))

r = c.get("/api/criminals/CRIM-999")
check("unknown criminal 404 json", r.status_code == 404 and "error" in j(r),
      f"{r.status_code} {j(r)}")

r = c.get("/api/analytics")
a = j(r)
check("analytics 200", r.status_code == 200, r.status_code)
check("analytics has no nulls", all(v is not None for v in a.values()), str(a))
check("analytics byState has 5 states", len(a["byState"]) == 5, str(a["byState"]))

# ── 404 / 405 are JSON, not HTML ──────────────────────────────────────────
r = c.get("/api/does-not-exist")
check("404 is JSON", r.status_code == 404 and "error" in (j(r) or {}), str(j(r)))
r = c.get("/api/auth/login")
check("405 is JSON", r.status_code == 405 and "error" in (j(r) or {}), str(j(r)))

# ── auth: happy path ──────────────────────────────────────────────────────
r = c.post("/api/auth/login", json={"username": "public", "password": "public123"})
d = j(r)
check("login public 200", r.status_code == 200, f"{r.status_code} {d}")
check("login returns token", bool(d.get("token")), str(d))
check("login role public", d.get("role") == "public", str(d))

r = c.post("/api/auth/login", json={"username": "officer", "password": "police123"})
check("login officer 200", r.status_code == 200, f"{r.status_code} {j(r)}")

r = c.post("/api/auth/login", json={"username": "admin", "password": "govt2026"})
check("login admin 200", r.status_code == 200, f"{r.status_code} {j(r)}")

# ── auth: rejections ──────────────────────────────────────────────────────
r = c.post("/api/auth/login", json={"username": "public", "password": "wrong"})
check("bad password 401", r.status_code == 401, r.status_code)
r = c.post("/api/auth/login", json={"username": "nobody", "password": "x"})
check("unknown user 401", r.status_code == 401, r.status_code)
r = c.post("/api/auth/login", json={})
check("empty login 400", r.status_code == 400, r.status_code)
r = c.post("/api/auth/login", data="not json", content_type="text/plain")
check("non-json login 400 not 500", r.status_code == 400, r.status_code)

# ── auth: signup ──────────────────────────────────────────────────────────
r = c.post("/api/auth/signup", json={
    "name": "Test User", "username": "testuser", "password": "secret123",
    "role": "public",
})
d = j(r)
check("signup public 201", r.status_code == 201, f"{r.status_code} {d}")
check("signup token", bool(d.get("token")), str(d))

r = c.post("/api/auth/signup", json={
    "name": "Test User", "username": "testuser", "password": "secret123",
    "role": "public",
})
check("duplicate signup 409", r.status_code == 409, r.status_code)

r = c.post("/api/auth/signup", json={
    "name": "Bad Name", "username": "a b!", "password": "secret123", "role": "public",
})
check("invalid username 400", r.status_code == 400, r.status_code)

r = c.post("/api/auth/signup", json={
    "name": "Short", "username": "shorty", "password": "123", "role": "public",
})
check("short password 400", r.status_code == 400, r.status_code)

r = c.post("/api/auth/signup", json={
    "name": "Cop", "username": "cop1", "password": "secret123", "role": "police",
})
check("police without badge 400", r.status_code == 400, f"{r.status_code} {j(r)}")

r = c.post("/api/auth/signup", json={
    "name": "Cop", "username": "cop1", "password": "secret123", "role": "police",
    "badge": "42", "rank": "Inspector", "stationCode": "PS-430",
    "stationName": "Hyderabad Central PS", "district": "Hyderabad",
    "state": "Telangana", "squad": "Squad Bh-11",
})
d = j(r)
check("police signup 201", r.status_code == 201, f"{r.status_code} {d}")
check("signup profile camelCase stationName",
      d.get("stationName") == "Hyderabad Central PS", str(d))

# login again -> profile keys must be camelCase too (original returned snake_case)
r = c.post("/api/auth/login", json={"username": "cop1", "password": "secret123"})
d = j(r)
check("login returns stationName (camelCase)", d.get("stationName") == "Hyderabad Central PS",
      str(d))
check("login returns rank/badge", d.get("rank") == "Inspector" and d.get("badge") == "42",
      str(d))
check("login does not leak password", "password" not in d, str(d.keys()))

r = c.post("/api/auth/signup", json={
    "name": "Gov", "username": "gov1", "password": "secret123", "role": "admin",
    "officialId": "GOV-1", "designation": "SP", "department": "Home",
})
d = j(r)
check("admin signup 201", r.status_code == 201, f"{r.status_code} {d}")
check("admin officialId camelCase", d.get("officialId") == "GOV-1", str(d))

# ── passwords are hashed at rest ──────────────────────────────────────────
from backend.database import get_db  # noqa: E402
conn = get_db()
rows = conn.execute("SELECT username, password FROM users").fetchall()
conn.close()
check("all passwords hashed",
      all(rw["password"].startswith(("pbkdf2:", "scrypt:", "argon2:")) for rw in rows),
      str([rw["password"][:20] for rw in rows]))

# ── create FIR ────────────────────────────────────────────────────────────
r = c.post("/api/cases", json={"stationId": 1, "crimeType": "HOMICIDE"})
d = j(r)
check("create case 201", r.status_code == 201, f"{r.status_code} {d}")
check("new FIR number FIR-2026-76", d.get("firNumber") == "FIR-2026-76", str(d))
check("severity auto Critical", d.get("severity") == "Critical", str(d))

r = c.post("/api/cases", json={"stationId": 9999, "crimeType": "FRAUD"})
check("unknown station 400", r.status_code == 400, f"{r.status_code} {j(r)}")

r = c.post("/api/cases", json={"stationId": 1, "crimeType": "FRAUD",
                               "officerId": "ASN-NOPE"})
check("unknown officer 400", r.status_code == 400, f"{r.status_code} {j(r)}")

r = c.post("/api/cases", json={"crimeType": "FRAUD"})
check("missing stationId 400", r.status_code == 400, r.status_code)

r = c.post("/api/cases", data="not json", content_type="text/plain")
check("non-json case 400 not 500", r.status_code == 400, r.status_code)

r = c.post("/api/cases", json={"stationId": "one", "crimeType": "FRAUD"})
check("string stationId 400", r.status_code == 400, r.status_code)

# ── create criminal ───────────────────────────────────────────────────────
r = c.post("/api/criminals", json={"name": "New Suspect", "age": 30,
                                   "address": "1 Test Road"})
d = j(r)
check("create criminal 201", r.status_code == 201, f"{r.status_code} {d}")
check("new criminal id CRIM-111", d.get("id") == "CRIM-111", str(d))
check("new photo id IMG-0012", d.get("photoId") == "IMG-0012", str(d))

r = c.post("/api/criminals", json={})
check("criminal without name 400", r.status_code == 400, r.status_code)

r = c.get("/api/criminals?q=test")
check("search finds new criminal", any(x["id"] == "CRIM-111" for x in j(r)), str(j(r)))

# ── index serves the frontend ─────────────────────────────────────────────
r = c.get("/")
check("GET / serves HTML", r.status_code == 200 and b"<!DOCTYPE html>" in r.data,
      f"{r.status_code} {r.data[:80]!r}")

print()
print(f"passed={len(PASSES)} failed={len(FAILURES)}")
for f in FAILURES:
    print("  -", f)
sys.exit(1 if FAILURES else 0)
