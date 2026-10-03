# API reference

Base URL: `http://localhost:4000/api`

All responses are JSON. Errors are always:

```json
{ "error": { "status": 404, "message": "Not found" } }
```

Status codes used: `200`, `201`, `400` (validation), `401` (bad credentials),
`404`, `405`, `409` (username taken), `500`.

---

## Authentication

### `POST /api/auth/login`

```jsonc
{ "username": "officer", "password": "police123" }
```

**200**
```jsonc
{
  "username": "officer", "role": "police", "display": "Police Officer",
  "stationCode": null,
  "token": "csn-police-9f3c…",
  "badge": "42", "rank": "Inspector", "stationName": "Hyderabad Central PS",
  "district": "Hyderabad", "state": "Telangana", "squad": "Squad Bh-11"
}
```

Profile keys are **camelCase** and only present when the account has them.
`401` on a bad username/password, `400` if either field is empty or the body is
not JSON.

### `POST /api/auth/signup`

```jsonc
{
  "name": "Cop", "username": "cop1", "password": "secret123",
  "role": "police",                       // public | police | admin
  "stationCode": "PS-430", "stationName": "Hyderabad Central PS",
  "badge": "42", "rank": "Inspector", "district": "Hyderabad",
  "state": "Telangana", "squad": "Squad Bh-11"
}
```

`role` decides which extra fields are required:

| Role | Required |
| ---- | -------- |
| `public` | — |
| `police` | `badge`, `rank`, `stationCode` |
| `admin`  | `officialId`, `designation`, `department` |

**201** with the same session object as login. `400` on validation failure,
`409` if the username exists.

---

## Stations

### `GET /api/stations`

```jsonc
[{
  "id": 9, "ps_code": "PS-462", "name": "Tirupati Hill PS",
  "district": "Chittoor", "state": "Andhra Pradesh",
  "lat": 13.6288, "lng": 79.4192, "sector": "Sector-AP4",
  "total_cases": 3, "critical_count": 1, "open_count": 2
}]
```

25 rows, ordered `state, district`.

### `GET /api/stations/{id}/cases`

Query params: `severity` (`Critical|High|Medium`), `status`
(`Open|Closed|Under Investigation`).

Returns each case joined with its station, officer and criminal:

```jsonc
[{
  "fir_number": "FIR-2026-1", "severity": "Medium", "status": "Open",
  "crime_type": "VEHICLE", "completion_pct": 49, "handling": "Interrogation",
  "investigation_type": "Solo", "arrest_date": "2020-03-01",
  "ps_code": "PS-430", "station_name": "Hyderabad Central PS",
  "district": "Hyderabad", "state": "Telangana", "sector": "Sector-TS1",
  "officer_name": "Vikram Rao", "officer_rank": "Inspector",
  "officer_squad": "Squad Bh-11",
  "criminal_name": "Vikram Rao", "criminal_age": 40,
  "criminal_address": "508, Sector 12", "criminal_photo": "IMG-0001"
}]
```

Ordered Critical → High → Medium, then status.

---

## Cases

### `GET /api/cases`

Query params: `severity`, `status`, `state`, `psCode`.

```jsonc
[{
  "id": 1, "fir_number": "FIR-2026-1", "station_id": 1,
  "officer_id": "ASN-9003", "criminal_id": "CRIM-100",
  "assign_id": "ASN-9003", "case_code": "CASE-2001 OFF-2037",
  "status": "Open", "severity": "Medium", "crime_type": "VEHICLE",
  "crime_count": 4, "completion_pct": 49, "handling": "Interrogation",
  "investigation_type": "Solo", "arrest_date": "2020-03-01",
  "photo_resolution": "1920x1080", "remarks": "Standard observation",
  "transfers": 2, "experience_years": 6,
  "ps_code": "PS-430", "station_name": "Hyderabad Central PS",
  "district": "Hyderabad", "state": "Telangana",
  "officer_name": "Vikram Rao", "criminal_name": "Vikram Rao"
}]
```

Returned in numeric FIR order (`FIR-2026-1, 2, … 10`), not lexicographic.

### `POST /api/cases`

```jsonc
{
  "stationId": 1,                 // required, integer
  "crimeType": "HOMICIDE",         // required
  "officerId": "ASN-9003",         // optional, must exist
  "criminalId": "CRIM-100",        // optional, must exist
  "status": "Open", "handling": "Active", "investigationType": "Solo",
  "crimeCount": 1, "completionPct": 0,
  "remarks": "…", "arrestDate": "2026-10-03"
}
```

**201**
```jsonc
{ "firNumber": "FIR-2026-76", "stationId": 1,
  "crimeType": "HOMICIDE", "severity": "Critical", "status": "Open" }
```

`fir_number` is allocated per calendar year. `severity` is derived from
`crimeType`. `400` if the station/officer/criminal is unknown or required fields
are missing; `completionPct` is clamped to 0–100.

### `GET /api/stats`

```jsonc
{ "total_cases": 75, "total_stations": 25,
  "critical_cases": 11, "open_cases": 38, "closed_cases": 17 }
```

All values are `0`, never `null`, even on an empty database.

---

## Officers

### `GET /api/officers`

```jsonc
[{
  "id": "ASN-9003", "name": "Vikram Rao",
  "rank": "Inspector", "squad": "Squad Bh-11",
  "total_cases": 5, "critical_cases": 1, "open_cases": 5, "closed_cases": 0
}]
```

### `GET /api/officers/{id}/cases`

Returns that officer's FIRs joined with station and criminal:

```jsonc
[{
  "fir_number": "FIR-2026-1", "crime_type": "VEHICLE",
  "severity": "Medium", "status": "Open",
  "completion_pct": 49, "handling": "Interrogation", "arrest_date": "2020-03-01",
  "station_name": "Hyderabad Central PS", "ps_code": "PS-430",
  "district": "Hyderabad", "state": "Telangana",
  "criminal_name": "Vikram Rao", "criminal_id": "CRIM-100"
}]
```

---

## Criminals

### `GET /api/criminals?q=`

`q` is an optional substring matched against name, id and address.

```jsonc
[{
  "id": "CRIM-100", "name": "Vikram Rao", "age": 40,
  "address": "508, Sector 12", "photo_id": "IMG-0001", "alias": null,
  "fir_count": 10, "station_count": 9
}]
```

### `GET /api/criminals/{id}`

```jsonc
{
  "criminal": { "id": "CRIM-100", "name": "Vikram Rao", "age": 40, "…" : "…" },
  "cases":    [ { "fir_number": "…", "station_name": "…", "lat": 17.38, "lng": 78.48, "…" : "…" } ],
  "stations": [ { "id": 1, "ps_code": "PS-430", "name": "…", "fir_count": 3 } ]
}
```

`cases` is ordered newest arrest first; `stations` only contains stations that
have actually handled this person (used for the mini-map). `404` if the id is
unknown.

### `POST /api/criminals`

```jsonc
{ "name": "New Suspect", "age": 30, "address": "1 Test Road", "alias": "…" }
```

`name` is required (max 200 chars). `age` is clamped to 0–150; `address`
defaults to `"Unknown"`.

**201**
```jsonc
{ "id": "CRIM-111", "name": "New Suspect", "age": 30,
  "address": "1 Test Road", "photoId": "IMG-0012", "alias": "" }
```

The id and photo id are allocated by the server — the client does not guess
them.

---

## Analytics

### `GET /api/analytics`

```jsonc
{
  "totalCases": 75, "totalStations": 25, "totalOfficers": 20, "totalCriminals": 11,
  "criticalCases": 11, "highCases": 34, "mediumCases": 30,
  "openCases": 38, "closedCases": 17, "underInvCases": 20,
  "byState": { "Telangana": 18, "Andhra Pradesh": 18, "Kerala": 18, "Tamil Nadu": 18, "Puducherry": 3 },
  "byType":  { "ROBBY": "…", "…": "…" }
}
```

`byType` is capped at the 10 most frequent crime types. Every numeric value is
`0` rather than `null` when there is no data.

---

## Serving the frontend

### `GET /`

Serves `frontend/index.html`. If that file is missing the server returns
`500` with a JSON message naming the path it expected.
