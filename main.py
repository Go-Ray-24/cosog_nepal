from flask import Flask, render_template, jsonify, request
import config
import os, json, csv
from datetime import datetime, timezone, timedelta
import requests
from alert import dispatch_nearest_authority_alert

app = Flask(__name__)

# In-memory dispatch history (most recent first). Resets on restart.
ALERT_HISTORY = []


# --------------------------------------------------------------------------
# Shared data helpers
# --------------------------------------------------------------------------
COMMUNITIES_FILE = os.path.join(os.path.dirname(__file__), "data", "communities.json")


def load_communities():
    if not os.path.exists(COMMUNITIES_FILE):
        return []
    with open(COMMUNITIES_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_communities(communities):
    with open(COMMUNITIES_FILE, "w", encoding="utf-8") as f:
        json.dump(communities, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _parse_acq_dt(acq_date, acq_time):
    """FIRMS gives acq_date as YYYY-MM-DD and acq_time as an HHMM integer string."""
    try:
        t = str(acq_time).strip().zfill(4)
        return datetime.strptime(f"{acq_date} {t}", "%Y-%m-%d %H%M").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def fetch_hotspots(source, days, bbox):
    """Query the NASA FIRMS Area API and return a normalised list of hotspots.

    The Area CSV API only accepts a day range of 1-5; anything else makes it
    return an "Invalid day range" error with no rows, so clamp it here.

    "Last 24 hours" (days=1) is special: FIRMS near-real-time data for the
    current UTC day is often not published yet, so a raw days=1 query comes
    back empty. Instead we pull a 2-day window and keep only the detections
    within 24 h of the most recent acquisition.
    """
    try:
        req_days = max(1, min(int(days), 5))
    except (TypeError, ValueError):
        req_days = 1

    last_24h = req_days == 1
    query_days = 2 if last_24h else req_days
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{config.FIRMS_MAP_KEY}/{source}/{bbox}/{query_days}"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200 or "Invalid" in response.text:
            print(f"[FIRMS API Error]: {response.text.strip()[:200]}")
            return []

        reader = csv.DictReader(response.text.strip().splitlines())
        hotspots = []
        for row in reader:
            try:
                frp = float(row.get("frp", 0.0))
                raw_conf = row.get("confidence", "n").lower()
                if raw_conf in ["l", "low"] or (raw_conf.isdigit() and int(raw_conf) < 40):
                    confidence = "low"
                elif raw_conf in ["h", "high"] or (raw_conf.isdigit() and int(raw_conf) >= 80):
                    confidence = "high"
                else:
                    confidence = "nominal"

                acq_dt = _parse_acq_dt(row.get("acq_date", ""), row.get("acq_time", ""))
                hotspots.append({
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                    "frp": frp,
                    "confidence": confidence,
                    "acq_date": row.get("acq_date", ""),
                    "acq_time": f"{row.get('acq_date', '')} {row.get('acq_time', '')}".strip(),
                    "daynight": row.get("daynight", ""),
                    "_dt": acq_dt,
                })
            except (ValueError, KeyError):
                continue

        if last_24h:
            times = [h["_dt"] for h in hotspots if h["_dt"]]
            if times:
                cutoff = max(times) - timedelta(hours=24)
                hotspots = [h for h in hotspots if h["_dt"] and h["_dt"] >= cutoff]

        for h in hotspots:
            h.pop("_dt", None)
        return hotspots
    except Exception as e:
        print(f"[Error fetching FIRMS]: {e}")
        return []


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("home.html", active="home")


@app.route("/monitoring")
def monitoring():
    return render_template("monitoring.html", active="monitoring", bbox=config.NEPAL_BBOX,
                           regions=config.REGIONS, default_region=config.DEFAULT_REGION)


@app.route("/analytics")
def analytics():
    return render_template("analytics.html", active="analytics",
                           regions=config.REGIONS, default_region=config.DEFAULT_REGION)


@app.route("/alerts")
def alerts():
    return render_template("alerts.html", active="alerts")


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
@app.route("/api/regions")
def api_regions():
    return jsonify([
        {"id": rid, "label": r["label"], "bbox": r["bbox"]}
        for rid, r in config.REGIONS.items()
    ])


def resolve_bbox(args):
    """Pick a bbox from an explicit ?bbox=, else a ?region= name, else the default."""
    if args.get("bbox"):
        return args["bbox"]
    region = config.REGIONS.get(args.get("region", "").lower())
    return region["bbox"] if region else config.NEPAL_BBOX


@app.route("/api/communities", methods=["GET", "POST"])
def api_communities():
    if request.method == "GET":
        return jsonify(load_communities())

    # POST: public registration of a new recipient
    data = request.json or {}
    required = ["name", "district", "latitude", "longitude", "email"]
    missing = [k for k in required if not str(data.get(k, "")).strip()]
    if missing:
        return jsonify({"status": "error", "message": f"Missing field(s): {', '.join(missing)}"}), 400

    try:
        lat = float(data["latitude"])
        lon = float(data["longitude"])
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Latitude and longitude must be numbers."}), 400
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return jsonify({"status": "error", "message": "Latitude/longitude out of range."}), 400

    email = str(data["email"]).strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"status": "error", "message": "Enter a valid email address."}), 400

    communities = load_communities()
    if any(c.get("email", "").lower() == email.lower() for c in communities):
        return jsonify({"status": "error", "message": "This email is already registered."}), 409

    try:
        population = int(data.get("population") or 0)
    except (TypeError, ValueError):
        population = 0

    nums = [int(c["id"].split("-")[-1]) for c in communities
            if str(c.get("id", "")).startswith("np-") and c["id"].split("-")[-1].isdigit()]
    new_id = f"np-{(max(nums) + 1 if nums else 1):03d}"

    entry = {
        "id": new_id,
        "name": str(data["name"]).strip(),
        "district": str(data["district"]).strip(),
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "population": population,
        "phone": str(data.get("phone", "")).strip(),
        "email": email,
    }
    communities.append(entry)
    save_communities(communities)
    return jsonify({"status": "success", "entry": entry}), 201


@app.route("/api/hotspots")
def api_hotspots():
    source = request.args.get("source", getattr(config, "FIRMS_SOURCE", "VIIRS_NOAA21_NRT"))
    days = request.args.get("days", "1")
    return jsonify(fetch_hotspots(source, days, resolve_bbox(request.args)))


@app.route("/api/stats")
def api_stats():
    source = request.args.get("source", getattr(config, "FIRMS_SOURCE", "VIIRS_NOAA21_NRT"))
    days = request.args.get("days", "5")
    hotspots = fetch_hotspots(source, days, resolve_bbox(request.args))

    by_confidence = {"high": 0, "nominal": 0, "low": 0}
    by_daynight = {"D": 0, "N": 0}
    by_date = {}
    frps = []
    for h in hotspots:
        by_confidence[h["confidence"]] = by_confidence.get(h["confidence"], 0) + 1
        dn = h.get("daynight", "")
        if dn in by_daynight:
            by_daynight[dn] += 1
        d = h.get("acq_date", "unknown")
        by_date[d] = by_date.get(d, 0) + 1
        frps.append(h["frp"])

    # nearest-community exposure: count hotspots within 10 km of any community
    from alert import haversine_distance
    communities = load_communities()
    exposure = []
    for c in communities:
        clat, clon = c.get("latitude"), c.get("longitude")
        if clat is None or clon is None:
            continue
        near = sum(1 for h in hotspots
                   if haversine_distance(clat, clon, h["latitude"], h["longitude"]) <= 10)
        exposure.append({"name": c.get("name"), "district": c.get("district"), "count": near})
    exposure.sort(key=lambda x: x["count"], reverse=True)

    timeseries = [{"date": d, "count": by_date[d]} for d in sorted(by_date)]
    top_frp = sorted(hotspots, key=lambda h: h["frp"], reverse=True)[:10]

    return jsonify({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "days": days,
        "total": len(hotspots),
        "by_confidence": by_confidence,
        "by_daynight": by_daynight,
        "timeseries": timeseries,
        "exposure": exposure,
        "top_frp": top_frp,
        "frp": {
            "total": round(sum(frps), 1),
            "avg": round(sum(frps) / len(frps), 1) if frps else 0,
            "max": round(max(frps), 1) if frps else 0,
        },
    })


@app.route("/api/send-alert", methods=["POST"])
def send_alert():
    data = request.json or {}
    fires = data.get("fires", [])
    communities = data.get("communities", []) or load_communities()

    result = dispatch_nearest_authority_alert(fires, communities)
    if result.get("status") == "success":
        r = result.get("recipient", {})
        ALERT_HISTORY.insert(0, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recipient": r,
            "fire_count": len(fires),
        })
    status_code = 200 if result.get("status") == "success" else 400
    return jsonify(result), status_code


@app.route("/api/alert-history")
def alert_history():
    return jsonify(ALERT_HISTORY)


if __name__ == "__main__":
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.DEBUG)
