# 🌲 Forest Fire Early Warning System — Nepal

A real-time wildfire alert system for Nepal that pulls live satellite hotspot
data from **NASA FIRMS**, plots detections on an interactive **Leaflet.js**
map, and dispatches automated **SMS / email alerts** to communities located
near active fires.

Built for the *Wildfire Ecology & Early Warning* fellowship project.

---

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Project Structure](#project-structure)
5. [Setup](#setup)
6. [Configuration Reference](#configuration-reference)
7. [Running the App](#running-the-app)
8. [API Reference](#api-reference)
9. [How Alerting Works](#how-alerting-works)
10. [Fire Ecology Notes](#fire-ecology-notes)
11. [Roadmap](#roadmap)
12. [Troubleshooting](#troubleshooting)

---

## Features

- **Live hotspot ingestion** from the NASA FIRMS Area API (VIIRS / MODIS),
  filtered to Nepal's bounding box, with confidence and Fire Radiative
  Power (FRP) thresholds.
- **Interactive map** (Leaflet.js) showing hotspots color-coded by
  intensity, at-risk community markers, and each community's alert radius.
- **Automated alerting**: any community within a configurable radius
  (default 10 km) of a hotspot is notified via **SMS (Twilio)** and
  **email (SMTP)**.
- **Alert de-duplication**: a cooldown window (default 6 hours) stops the
  same community from being re-alerted for the same fire detection on
  every polling cycle.
- **Dry-run mode**: alert logic can be exercised safely with no Twilio/SMTP
  credentials configured — messages are logged instead of sent.
- **REST API** for hotspots, communities, and alert history so the map,
  a mobile app, or a scheduled job can all consume the same backend.

## Architecture

```
                    ┌─────────────────────┐
                    │   NASA FIRMS API     │
                    │  (VIIRS / MODIS CSV) │
                    └──────────┬───────────┘
                               │ requests (HTTP/CSV)
                               ▼
                    ┌─────────────────────┐
                    │   firms_client.py    │  parses + filters
                    │  (FRP / confidence)  │  hotspots
                    └──────────┬───────────┘
                               │
              ┌────────────────┼─────────────────┐
              ▼                                   ▼
   ┌─────────────────────┐            ┌─────────────────────────┐
   │  Flask API (main.py) │            │      alert_engine.py     │
   │  /api/hotspots        │            │  haversine distance vs.  │
   │  /api/communities      │            │  communities.json        │
   │  /api/alerts/run        │──────────▶│  cooldown de-dup (JSON)   │
   └──────────┬───────────┘            └───────────┬──────────────┘
              │ GeoJSON                             │
              ▼                                     ▼
   ┌─────────────────────┐            ┌─────────────────────────┐
   │  Leaflet.js frontend  │            │  alerts/sms_alert.py     │
   │  (templates/index.html│            │  alerts/email_alert.py   │
   │   + static/js/map.js) │            │  (Twilio / SMTP)         │
   └─────────────────────┘            └─────────────────────────┘
```

## Tech Stack

| Layer            | Choice                                   |
|-------------------|-------------------------------------------|
| Data source        | NASA FIRMS Area API (VIIRS/MODIS NRT)     |
| Backend             | Python 3.10, Flask                        |
| Mapping frontend    | Leaflet.js + OpenStreetMap tiles          |
| SMS notifications   | Twilio                                    |
| Email notifications | SMTP (Gmail app password / any provider)  |
| Config              | python-dotenv (.env)                       |

## Project Structure

```
forest-fire/
├── main.py                # Flask app & REST routes
├── config.py               # Env-driven configuration
├── firms_client.py          # NASA FIRMS API client + CSV parsing
├── geo_utils.py              # Haversine distance helper
├── alert_engine.py            # Matches hotspots ↔ communities, dispatches alerts
├── alerts/
│   ├── sms_alert.py            # Twilio SMS sender
│   └── email_alert.py           # SMTP email sender
├── data/
│   ├── communities.json          # Sample at-risk communities (editable)
│   └── alert_log.json             # Auto-generated cooldown log (gitignored)
├── templates/
│   └── index.html                  # Map dashboard page
├── static/
│   ├── css/style.css                # Dashboard styling
│   └── js/map.js                     # Leaflet map logic + API calls
├── reports/                            # Generated PDF project report
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

### 1. Prerequisites

- Python 3.10+
- A free **NASA FIRMS MAP_KEY**: https://firms.modaps.eosdis.nasa.gov/api/map_key/
- *(Optional, for real SMS)* A Twilio account, phone number, Account SID & Auth Token
- *(Optional, for real email)* SMTP credentials (e.g. a Gmail App Password)

### 2. Install dependencies

```bash
cd forest-fire
python -m venv ../venv        # or reuse the repo-level venv
source ../venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in at minimum `FIRMS_MAP_KEY`. Twilio/SMTP variables
can stay empty — the app runs in **dry-run mode** and logs what it would
have sent.

### 4. Add / edit communities

Edit `data/communities.json` to reflect the real villages, wards, or
buffer-zone user committees you want to protect. Each entry needs
`name`, `district`, `latitude`, `longitude`, and (for real alerts) `phone`
and/or `email`.

## Configuration Reference

All settings live in `.env` (see `.env.example`) and are loaded by
`config.py`:

| Variable | Default | Meaning |
|---|---|---|
| `FIRMS_MAP_KEY` | *(none)* | Your NASA FIRMS API key |
| `FIRMS_SOURCE` | `VIIRS_SNPP_NRT` | Satellite/sensor source |
| `NEPAL_BBOX` | `80.0,26.3,88.3,30.5` | west,south,east,north bounding box |
| `FIRMS_DAY_RANGE` | `1` | Days of history to fetch (1–10) |
| `ALERT_RADIUS_KM` | `10` | Distance within which a community is "at risk" |
| `MIN_FRP` | `1.0` | Minimum Fire Radiative Power (MW) to count as a detection |
| `MIN_CONFIDENCE` | `nominal` | Minimum detection confidence (`low`/`nominal`/`high`) |
| `ALERT_COOLDOWN_HOURS` | `6` | Minimum hours between repeat alerts for the same fire+community |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` | *(none)* | Twilio SMS credentials |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | *(none)* | SMTP email credentials |

## Running the App

```bash
python main.py
```

Then open **http://localhost:5000** — the map loads current hotspots
inside Nepal, plots the sample at-risk communities with their alert
radius, and lets you trigger a manual alert check ("Run Alert Check")
from the sidebar.

To actually send SMS/email instead of a dry run, call the alert endpoint
directly:

```bash
curl -X POST "http://localhost:5000/api/alerts/run?dry_run=0"
```

### Running alerts on a schedule

For production use, poll FIRMS periodically instead of relying on someone
clicking the button. Add a cron job (or a systemd timer) that hits the
endpoint every 15–30 minutes, matching how often FIRMS NRT data updates:

```bash
*/15 * * * * curl -s -X POST "http://localhost:5000/api/alerts/run?dry_run=0"
```

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Map dashboard |
| `GET` | `/api/hotspots` | Current FIRMS hotspots as GeoJSON. Add `?refresh=1` to bypass cache |
| `GET` | `/api/communities` | At-risk communities as GeoJSON |
| `POST` | `/api/alerts/run?dry_run=1` | Match hotspots against communities and dispatch alerts (`dry_run=0` sends real SMS/email) |
| `GET` | `/api/alerts/history` | Raw cooldown log of previously dispatched alerts |

## How Alerting Works

1. `firms_client.fetch_hotspots()` queries the FIRMS Area API for the
   Nepal bounding box and parses the returned CSV, discarding rows below
   `MIN_FRP` or `MIN_CONFIDENCE`.
2. `alert_engine.find_at_risk()` computes the **haversine distance**
   between every community and every hotspot, keeping the nearest hotspot
   within `ALERT_RADIUS_KM`.
3. For each at-risk community, a message key
   (`community_id:acq_date:acq_time`) is checked against
   `data/alert_log.json`. If it was already alerted within
   `ALERT_COOLDOWN_HOURS`, it's skipped — this prevents spamming the same
   household every time the map polls FIRMS for the same fire.
4. Otherwise, `alerts/sms_alert.py` and `alerts/email_alert.py` send the
   notification (or log a dry-run message if credentials aren't set), and
   the log is updated.

## Fire Ecology Notes

Context the team explored while building this (useful for the report /
presentation):

- **Fuel load**: Nepal's Chure/Terai forests and community forests
  accumulate dry leaf litter and grass fuel in the pre-monsoon dry season
  (Feb–May), which is when the vast majority of FIRMS detections cluster.
- **VIIRS vs MODIS**: VIIRS (375 m resolution) detects smaller/cooler
  fires than MODIS (1 km resolution) but has a narrower swath; combining
  sources gives better recall at the cost of more false positives, which
  is why `MIN_FRP` / `MIN_CONFIDENCE` filtering matters.
- **Early warning value**: FIRMS NRT (Near Real-Time) data is typically
  available within 1–3 hours of satellite overpass — fast enough to warn
  communities before a fire front reaches them, but not instantaneous, so
  alerts should always be paired with local ground reporting.
- **False positives**: agricultural burning, industrial heat sources, and
  sun glint can trigger hotspot detections; confidence and FRP thresholds
  reduce (but don't eliminate) these.

## Roadmap

- [ ] Persist communities/alert log to a real database instead of JSON files
- [ ] Add a background scheduler (APScheduler / Celery beat) instead of
      cron for polling FIRMS
- [ ] Historical burn-scar and fire-frequency layers (MODIS Burned Area)
- [ ] SMS in Nepali (Devanagari) with localized templates
- [ ] Web push / mobile app notifications
- [ ] Role-based dashboard for district disaster management committees

## Troubleshooting

- **"FIRMS_MAP_KEY is not set"** — copy `.env.example` to `.env` and add
  your key from https://firms.modaps.eosdis.nasa.gov/api/map_key/
- **Empty hotspot list** — this is often correct (no active fires in the
  bounding box/day range). Try increasing `FIRMS_DAY_RANGE` or check
  https://firms.modaps.eosdis.nasa.gov/map/ for current global activity.
- **SMS/email not sending** — check the logs; without Twilio/SMTP
  credentials the app intentionally runs in dry-run mode and just logs
  what it would send.
# cosog_nepal
