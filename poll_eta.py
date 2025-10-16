#!/usr/bin/env python3
"""
Minimal Routes API ETA logger.
Fetches real-time trip duration using Google Maps Routes API (v2),
and appends to eta_log.csv in the same folder.
"""

import os, csv, json, datetime, requests
from zoneinfo import ZoneInfo

# ----------------------------
# Configuration
# ----------------------------
API_KEY = "YOUR_API_KEY_HERE"  # <- replace with your Google Maps API key
ORIGIN = "267 Princeton St, Boston, MA"
DESTINATION = "425 Waverley Oaks Rd #250, Waltham, MA 02452"
TIMEZONE = "America/New_York"       # Local time zone
LOG_FILE = "eta_log.csv"            # CSV stored next to this script
# ----------------------------

def within_window(local_time: datetime.datetime) -> bool:
    """Run only between 5 AM and 8 PM local time."""
    return 5 <= local_time.hour < 20

def routes_api_request():
    """Call the Google Routes API and return JSON data."""
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"

    # UTC time (ISO 8601 with Z suffix), add 30s so the request is in the future
    now_utc = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=30)
    departure_time = now_utc.isoformat(timespec="seconds").replace("+00:00", "Z")

    payload = {
        "origin": {"address": ORIGIN},
        "destination": {"address": DESTINATION},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "departureTime": departure_time,
    }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.staticDuration,routes.description",
    }

    response = requests.post(url, headers=headers, json=payload, timeout=15)
    response.raise_for_status()
    return response.json()

def format_duration(proto_str: str) -> int:
    """Convert Google duration string like '123.4s' to seconds (int)."""
    return int(float(proto_str[:-1])) if proto_str and proto_str.endswith("s") else 0

def log_eta():
    """Fetch ETA, print result, and append to CSV."""
    # Determine script directory for log file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(script_dir, LOG_FILE)

    # Skip outside hours
    local_time = datetime.datetime.now(ZoneInfo(TIMEZONE))
    if not within_window(local_time):
        print(f"[{local_time:%H:%M}] Outside time window; skipping.")
        return

    data = routes_api_request()
    routes = data.get("routes", [])
    if not routes:
        print("No routes returned.")
        return

    r = routes[0]
    duration_s = format_duration(r["duration"])
    static_s = format_duration(r["staticDuration"])
    dist_m = r["distanceMeters"]
    description = r.get("description", "")

    eta_min = round(duration_s / 60, 1)
    static_min = round(static_s / 60, 1)
    dist_mi = round(dist_m / 1609.34, 2)

    row = {
        "timestamp": local_time.isoformat(timespec="seconds"),
        "origin": ORIGIN,
        "destination": DESTINATION,
        "distance_mi": dist_mi,
        "eta_min": eta_min,
        "freeflow_min": static_min,
        "route_description": description,
    }

    write_header = not os.path.exists(log_path)
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        if write_header:
            w.writeheader()
        w.writerow(row)

    print(json.dumps(row, indent=2))

if __name__ == "__main__":
    try:
        log_eta()
    except Exception as e:
        import traceback, requests
        if isinstance(e, requests.HTTPError) and e.response is not None:
            print("HTTPError status:", e.response.status_code)
            print("Response text:", e.response.text)  # <-- shows Google’s detailed error JSON
        else:
            traceback.print_exc()
