# `frontend/` — the single-page UI

`index.html` is the whole client: markup, CSS and vanilla JavaScript in one
file, with Leaflet and Chart.js pulled from CDNs.

It is served directly by the Flask backend at `http://localhost:4000/`, so there
is no build step, no bundler and no second server.

## Layout of the file

| Region | Contents |
| ------ | -------- |
| `<head>` styles | dark theme, layout, component classes |
| `#dome-entrance` | splash overlay; click it to start the intro |
| `#intro-sequence` | animated title card |
| `#login-screen` | sign-in / sign-up tabs |
| `#app` | navbar, map, analytics, officers, criminals, modals |
| `<script>` (first)  | `startIntroSequence()` |
| `<script>` (second) | everything else — data, API, rendering |

## Connecting to the API

```js
const API_BASE = window.CSN_API_BASE
  || (location.port === '4000' ? location.origin + '/api' : 'http://localhost:4000/api');
```

- **Served by Flask** → same origin, so any host/port works.
- **Opened from disk (`file://`) or a static host such as Netlify** → falls back
  to the local dev server.
- **Override** by defining `window.CSN_API_BASE` *before* the second `<script>`
  block:

  ```html
  <script>window.CSN_API_BASE = 'https://api.example.com/api';</script>
  ```

> This used to be a hardcoded `http://localhost:4000/api`, which meant the
> deployed Netlify site could only ever talk to the visitor's own machine.

## Data model

Four globals are filled by `fetchInitialData()`:

| Global  | Source            | Key fields |
| ------- | ----------------- | ---------- |
| `ST`    | `/api/stations`   | `id, ps, name, district, state, lat, lng, sector` |
| `OL`    | `/api/officers`   | `id, name, rank, squad` |
| `CRL`   | `/api/criminals`  | `id, name, age, address, photo, alias` |
| `CASES` | `/api/cases`      | short keys: `fn` (FIR no.), `sid`, `oi`, `ci`, `ct`, `st`, `severity`, `on`, `cn`, `rem` … |

`CRM` and `OM` are lookup maps (`CRM['CRIM-100']`), rebuilt whenever the lists
are refetched.

`STATIC_STATIONS` is a built-in fallback copy of the 25 stations, so the signup
form and the map still work when the backend is offline.

## Rendering and escaping

Anything interpolated into `innerHTML` goes through **`esc()`**:

```js
esc(cr.name)   // → &lt;script&gt;…  instead of being parsed as HTML
```

This matters because criminal names, addresses and FIR remarks are free text
entered by users through the API — without escaping, one record would execute
script for everyone who opened the criminal list (stored XSS). Fields written
with `textContent` (via the `g(id, value)` helper) are already safe and are
deliberately *not* escaped, since escaping there would show literal `&amp;`.

## Key functions

| Function | Role |
| -------- | ---- |
| `window.onload` | load stations, restore a saved session, then `startApp()` |
| `startApp()` | hide login, remove the splash, build the role badge |
| `showSec(n)` | switch map / analytics / officers / criminals tabs |
| `fetchInitialData()` | refetch all four lists, rebuild lookup maps |
| `doLogin()` / `doSignup()` | auth calls; errors come from `apiError(res, fallback)` |
| `openFIR()` / `submitFIR()` | file a new case, then reset `charts.done` |
| `openStn(station)` | station detail panel — takes the **station object**, not an id |
| `openCDM(case)` | case detail modal |
| `openCP(id)` / `openOP(id)` | criminal / officer profile modals |
| `initAnalytics()` | (re)build the four Chart.js charts |

## Charts

`initAnalytics()` bails out early when `charts.done` is true. Filing an FIR sets
`charts.done = false`, so the next visit to Analytics rebuilds them — which
means the previous instances must be destroyed first or Chart.js throws
*"Canvas is already in use"*. The function therefore tears down `charts.c1…c4`
before creating new ones.

Percentages are computed with a `pct(n)` helper that returns `0` instead of
`NaN` when there are no cases to divide by.
