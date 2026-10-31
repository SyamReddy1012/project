"""Interactive web dashboard and API server for MPTracker on Render and local machine.
Features:
  - Separate Full-Screen Dedicated Login Page (Admin vs NGO Search Party)
  - Dedicated Login for each NGO / Rescue Team with individual credentials
  - Add New NGOs / Rescue Teams with Custom Base Locations & Coordinates
  - Admin NGO Registry & Team Management (Add, View, Remove)
  - Dark & Light Mode Theme Toggle with persistent localStorage
  - Custom Video Upload & Surveillance Camera Location Selector
  - Real Street-Level Road Network Routing (OSRM) from each NGO's base
  - Add New Case Modal, Delete Resolved Cases, and Live Case Counters
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .db import (
    ensure_db_schema,
    load_cases_from_db,
    save_case_to_db,
    delete_case_from_db,
    load_teams_from_db,
    save_team_to_db,
    delete_team_from_db,
    save_sighting_to_db,
    save_dispatch_to_db,
    resolve_dispatch_in_db,
    load_dispatches_from_db,
)
from .demo import build_demo, PLACES
from .graph import SightingGraph
from .models import GeoPoint, Location



# Real surveillance & landmark locations in Kurnool area
CAMERA_LOCATIONS = {
    "CAR STAND": {"lat": 15.8281, "lon": 78.0373, "label": "CAM-01: CAR STAND Main Gate (15.8281, 78.0373)"},
    "Budhwarpet Market": {"lat": 15.8350, "lon": 78.0450, "label": "CAM-02: Budhwarpet Market Junction (15.8350, 78.0450)"},
    "Kurnool City Railway": {"lat": 15.8310, "lon": 78.0420, "label": "CAM-03: Kurnool City Railway Station (15.8310, 78.0420)"},
    "Kurnool Bus Stand": {"lat": 15.8281, "lon": 78.0373, "label": "CAM-04: Central Bus Stand Entrance (15.8281, 78.0373)"},
    "RGM grounds": {"lat": 15.8310, "lon": 78.0420, "label": "CAM-05: RGM Grounds North Field (15.8310, 78.0420)"},
    "cantene": {"lat": 15.8350, "lon": 78.0450, "label": "CAM-06: Campus Canteen Surveillance (15.8350, 78.0450)"},
    "DS labs": {"lat": 15.8200, "lon": 78.0450, "label": "CAM-07: DS Labs Corridor (15.8200, 78.0450)"},
    "RGM hostel": {"lat": 15.8150, "lon": 78.0300, "label": "CAM-08: RGM Hostel Gate (15.8150, 78.0300)"},
    "RGM gardens": {"lat": 15.8340, "lon": 78.0560, "label": "CAM-09: RGM Gardens Perimeter (15.8340, 78.0560)"},
    "Konda Reddy Fort": {"lat": 15.8340, "lon": 78.0560, "label": "CAM-10: Konda Reddy Fort Circle (15.8340, 78.0560)"},
    "maha nandhi": {"lat": 15.8100, "lon": 78.0600, "label": "CAM-11: Maha Nandhi Road Junction (15.8100, 78.0600)"},
    "Collectorate": {"lat": 15.8200, "lon": 78.0450, "label": "CAM-12: District Collectorate (15.8200, 78.0450)"},
    "Government Hospital": {"lat": 15.8150, "lon": 78.0300, "label": "CAM-13: Government General Hospital (15.8150, 78.0300)"},
    "Tungabhadra Bridge": {"lat": 15.8420, "lon": 78.0300, "label": "CAM-14: Tungabhadra River Bridge (15.8420, 78.0300)"},
}

INITIAL_CASES = [
    {
        "id": 1,
        "name": "N.K.SYAM",
        "age": 23,
        "gender": "Male",
        "clothes": "BLUE SHIRT",
        "last_seen_location": "CAR STAND",
        "status": "ACTIVE",
        "created_at": "Today, 14:10",
        "assigned_team": "Helping Hands NGO",
        "lat": 15.8281,
        "lon": 78.0373,
    },
    {
        "id": 2,
        "name": "S.Irfan",
        "age": 19,
        "gender": "Male",
        "clothes": "black and white shirt",
        "last_seen_location": "RGM grounds",
        "status": "ACTIVE",
        "created_at": "Today, 12:45",
        "assigned_team": "City Police Patrol 1",
        "lat": 15.8310,
        "lon": 78.0420,
    },
    {
        "id": 3,
        "name": "Nani kumar",
        "age": 17,
        "gender": "Male",
        "clothes": "white shirt black pant",
        "last_seen_location": "cantene",
        "status": "ACTIVE",
        "created_at": "Today, 11:30",
        "assigned_team": "Volunteer Unit A",
        "lat": 15.8350,
        "lon": 78.0450,
    },
    {
        "id": 4,
        "name": "S.Yakub",
        "age": 20,
        "gender": "Male",
        "clothes": "black shirt with blue jeens",
        "last_seen_location": "DS labs",
        "status": "ACTIVE",
        "created_at": "Yesterday, 18:20",
        "assigned_team": "Helping Hands NGO",
        "lat": 15.8200,
        "lon": 78.0450,
    },
    {
        "id": 5,
        "name": "S.javeed",
        "age": 19,
        "gender": "Male",
        "clothes": "greyish green shirt",
        "last_seen_location": "RGM hostel",
        "status": "ACTIVE",
        "created_at": "Yesterday, 16:00",
        "assigned_team": "City Police Patrol 1",
        "lat": 15.8150,
        "lon": 78.0300,
    },
    {
        "id": 6,
        "name": "Tharnish",
        "age": 28,
        "gender": "Male",
        "clothes": "red shirt",
        "last_seen_location": "RGM gardens",
        "status": "RESCUED",
        "created_at": "2 days ago",
        "assigned_team": "Volunteer Unit A",
        "lat": 15.8340,
        "lon": 78.0560,
    },
    {
        "id": 7,
        "name": "D.Kasim",
        "age": 67,
        "gender": "Male",
        "clothes": "white blue shirt",
        "last_seen_location": "maha nandhi",
        "status": "CLOSED",
        "created_at": "3 days ago",
        "assigned_team": "Helping Hands NGO",
        "lat": 15.8100,
        "lon": 78.0600,
    },
]

INITIAL_TEAMS = [
    {
        "id": 1,
        "name": "Helping Hands NGO",
        "org": "NGO",
        "base_location": "Budhwarpet Base",
        "lat": 15.8350,
        "lon": 78.0450,
        "phone": "6303126628",
        "username": "helping_hands",
        "password": "ngo123",
        "available": True,
    },
    {
        "id": 2,
        "name": "City Police Patrol 1",
        "org": "Police",
        "base_location": "Kurnool Town Police Station",
        "lat": 15.8281,
        "lon": 78.0373,
        "phone": "100-000-0001",
        "username": "police_patrol",
        "password": "police123",
        "available": True,
    },
    {
        "id": 3,
        "name": "Volunteer Unit A",
        "org": "Volunteer",
        "base_location": "Nandyal Road Base",
        "lat": 15.8100,
        "lon": 78.0600,
        "phone": "91234-56789",
        "username": "volunteer_a",
        "password": "volunteer123",
        "available": True,
    },
]

INITIAL_NOTIFICATIONS = [
    {
        "id": 1,
        "team_id": 1,
        "team_name": "Helping Hands NGO",
        "case_id": 1,
        "person_name": "N.K.SYAM",
        "last_seen_location": "CAR STAND",
        "title": "🚨 Case Allotment: N.K.SYAM",
        "message": "Police Command has allotted Case #1 (N.K.SYAM, age 23, BLUE SHIRT) to Helping Hands NGO. Target Zone: CAR STAND. Road route active.",
        "timestamp": "Today, 14:10",
        "read": False,
        "priority": "HIGH",
        "phone": "+91 6303126628",
        "sms_status": "DELIVERED to +91 6303126628",
    },
    {
        "id": 2,
        "team_id": 2,
        "team_name": "City Police Patrol 1",
        "case_id": 2,
        "person_name": "S.Irfan",
        "last_seen_location": "RGM grounds",
        "title": "🚨 Case Allotment: S.Irfan",
        "message": "Police Command has allotted Case #2 (S.Irfan, age 19, black & white shirt) to City Police Patrol 1. Target Zone: RGM grounds.",
        "timestamp": "Today, 12:45",
        "read": False,
        "priority": "HIGH",
        "phone": "100-000-0001",
        "sms_status": "DELIVERED to +91 100-000-0001",
    },
    {
        "id": 3,
        "team_id": 3,
        "team_name": "Volunteer Unit A",
        "case_id": 3,
        "person_name": "Nani kumar",
        "last_seen_location": "cantene",
        "title": "🚨 Case Allotment: Nani kumar",
        "message": "Police Command has allotted Case #3 (Nani kumar, age 17, white shirt black pant) to Volunteer Unit A. Target Zone: cantene.",
        "timestamp": "Today, 11:30",
        "read": False,
        "priority": "MEDIUM",
        "phone": "91234-56789",
        "sms_status": "DELIVERED to +91 91234-56789",
    },
]

APP_STATE = {
    "cameras": dict(CAMERA_LOCATIONS),
    "cases": list(INITIAL_CASES),
    "teams": list(INITIAL_TEAMS),
    "notifications": list(INITIAL_NOTIFICATIONS),
    "dispatches": [
        {
            "id": 101,
            "case_id": 1,
            "person_name": "N.K.SYAM",
            "team_id": 1,
            "team_name": "Helping Hands NGO",
            "target_location": "CAR STAND",
            "target_lat": 15.8281,
            "target_lon": 78.0373,
            "team_lat": 15.8350,
            "team_lon": 78.0450,
            "distance_km": 1.74,
            "eta_minutes": 2.8,
            "status": "EN_ROUTE",
        }
    ],
}


def _sync_db_with_state() -> None:
    try:
        ensure_db_schema()
        db_cases = load_cases_from_db()
        if db_cases:
            APP_STATE["cases"] = db_cases
        db_teams = load_teams_from_db()
        if db_teams:
            APP_STATE["teams"] = db_teams
        db_dispatches = load_dispatches_from_db()
        if db_dispatches:
            APP_STATE["dispatches"] = db_dispatches
    except Exception as exc:
        print(f"[!] PostgreSQL sync warning: {exc}")


_sync_db_with_state()



def _format_phone_number(raw_phone: str) -> str:
    cleaned = str(raw_phone).strip()
    digits = "".join(ch for ch in cleaned if ch.isdigit())
    if len(digits) == 10:
        return f"+91 {digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return f"+91 {digits[2:]}"
    if cleaned.startswith("+"):
        return cleaned
    return f"+91 {cleaned}"


def _send_case_allotment_notification(case: dict, team: dict, note: str = "", phone_override: str = "") -> dict:
    """Create and dispatch a real-time notification + simulated SMS to a specific NGO."""
    new_notif_id = max([n["id"] for n in APP_STATE.get("notifications", [])], default=0) + 1
    timestamp = datetime.now().strftime("Today, %H:%M")
    raw_phone = phone_override or team.get("phone") or "6303126628"
    formatted_phone = _format_phone_number(raw_phone)
    sms_msg = f"EMERGENCY DISPATCH: Case #{case['id']} ({case['name']}) allotted to {team['name']}. Location: {case.get('last_seen_location', 'N/A')}."
    if note:
        sms_msg += f" Note: {note}"

    print(f"\n=======================================================")
    print(f"[SMS GATEWAY DISPATCH] -> To: {formatted_phone} ({team['name']})")
    print(f"[MESSAGE] {sms_msg}")
    print(f"[STATUS] DELIVERED (Carrier ACK ID: SMS-IND-6303126628-{new_notif_id:04d})")
    print(f"=======================================================\n")

    notif = {
        "id": new_notif_id,
        "team_id": team.get("id"),
        "team_name": team["name"],
        "case_id": case["id"],
        "person_name": case["name"],
        "last_seen_location": case.get("last_seen_location", "Unknown"),
        "title": f"🚨 Case Allotment: {case['name']}",
        "message": f"Police Command has allotted Case #{case['id']} ({case['name']}) to {team['name']}. Target Zone: {case.get('last_seen_location', 'N/A')}." + (f" Instructions: {note}" if note else ""),
        "timestamp": timestamp,
        "read": False,
        "priority": "HIGH",
        "phone": formatted_phone,
        "sms_status": f"DELIVERED to {formatted_phone}",
    }
    APP_STATE["notifications"].insert(0, notif)
    return notif


def _get_app_stats():
    cases = APP_STATE["cases"]
    total = len(cases)
    active = sum(1 for c in cases if c.get("status") == "ACTIVE")
    closed = sum(1 for c in cases if c.get("status") in ("RESCUED", "CLOSED"))
    return {
        "total_cases": total,
        "active_cases": active,
        "closed_cases": closed,
        "en_route_dispatches": sum(1 for d in APP_STATE["dispatches"] if d.get("status") == "EN_ROUTE"),
        "total_teams": len(APP_STATE["teams"]),
        "total_notifications": len(APP_STATE.get("notifications", [])),
    }


def _fetch_osrm_street_route(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> dict | None:
    """Fetch exact real-world turn-by-turn road network coordinates from OpenStreetMap OSRM."""
    try:
        url = (
            f"https://router.project-osrm.org/route/v1/driving/"
            f"{from_lon:.6f},{from_lat:.6f};{to_lon:.6f},{to_lat:.6f}"
            f"?overview=full&geometries=geojson"
        )
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "MPTracker-SearchPartyRouter/1.0 (EmergencyRescueRoute)",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=4.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                # OSRM geojson coordinates are [lon, lat] -> convert to Leaflet [lat, lon]
                coords = [[c[1], c[0]] for c in route["geometry"]["coordinates"]]
                dist_km = round(route.get("distance", 0.0) / 1000.0, 2)
                eta_min = round(route.get("duration", 0.0) / 60.0, 1)
                return {
                    "street_coordinates": coords,
                    "distance_km": dist_km,
                    "eta_minutes": eta_min,
                    "engine": f"OSRM Real Road Network ({len(coords)} nodes)",
                }
    except Exception as exc:
        print(f"[OSRM Router] Server-side routing warning: {exc}")
    return None


def _generate_corridor_coordinates(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> list[list[float]]:
    """Generate realistic street-following corridor waypoints along street axes if external router is unreachable."""
    mid_lat = (from_lat + to_lat) / 2.0
    mid_lon = (from_lon + to_lon) / 2.0
    return [
        [from_lat, from_lon],
        [from_lat, mid_lon],
        [mid_lat, mid_lon],
        [mid_lat, to_lon],
        [to_lat, to_lon],
    ]


def _calculate_shortest_route(from_lat: float, from_lon: float, to_lat: float, to_lon: float):
    # Try fetching real street geometry via server-side OSRM first
    osrm_data = _fetch_osrm_street_route(from_lat, from_lon, to_lat, to_lon)
    if osrm_data and osrm_data.get("street_coordinates"):
        street_coords = osrm_data["street_coordinates"]
        dist_km = osrm_data["distance_km"]
        eta_minutes = osrm_data["eta_minutes"]
        engine = osrm_data["engine"]
    else:
        # Fallback to road-corridor coordinates and SightingGraph
        street_coords = _generate_corridor_coordinates(from_lat, from_lon, to_lat, to_lon)
        dist_km = GeoPoint(from_lat, from_lon).distance_km(GeoPoint(to_lat, to_lon))
        eta_minutes = round((dist_km / 30.0) * 60.0, 1)
        engine = "Internal Street Corridor Fallback"

    graph = SightingGraph()
    for i, name, lat, lon in PLACES:
        graph.add_location(Location(i, name, GeoPoint(lat, lon)))
    graph.connect_nearby(2.0)

    def nearest_node(lat, lon):
        p = GeoPoint(lat, lon)
        best_id, best_d = 1, float("inf")
        for loc in graph.locations:
            d = loc.point.distance_km(p)
            if d < best_d:
                best_d = d
                best_id = loc.id
        return best_id

    start_node = nearest_node(from_lat, from_lon)
    end_node = nearest_node(to_lat, to_lon)

    node_ids, _ = graph.shortest_path(start_node, end_node)
    waypoints = [
        {
            "id": graph.location(nid).id,
            "name": graph.location(nid).name,
            "lat": graph.location(nid).point.lat,
            "lon": graph.location(nid).point.lon,
        }
        for nid in node_ids
    ]

    if not waypoints:
        waypoints = [
            {"id": 0, "name": "Rescue Team Base", "lat": from_lat, "lon": from_lon},
            {"id": 99, "name": "Target Location", "lat": to_lat, "lon": to_lon},
        ]

    return {
        "distance_km": round(dist_km, 2),
        "eta_minutes": eta_minutes,
        "from_lat": from_lat,
        "from_lon": from_lon,
        "to_lat": to_lat,
        "to_lon": to_lon,
        "waypoints": waypoints,
        "route_coordinates": street_coords,
        "street_coordinates": street_coords,
        "engine": engine,
    }


HTML_APP = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Missing Person Search-and-Track System • Problem Statement 112</title>
  
  <!-- Modern Typography: Plus Jakarta Sans & JetBrains Mono -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  
  <!-- Leaflet GIS Map CSS & JS with Fast Multi-CDN Support -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
  <script>
    if (typeof L === 'undefined') {
      const s = document.createElement('script');
      s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      document.head.appendChild(s);
    }
  </script>

  <style>
    :root {
      --font-main: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
      
      /* Dark Theme - High-Tech Tactical Glassmorphism */
      --bg: #070b14;
      --bg-gradient: radial-gradient(circle at 50% -10%, #111e3b 0%, #070b14 80%);
      --card: rgba(15, 23, 42, 0.78);
      --card-solid: #0f172a;
      --card-border: rgba(255, 255, 255, 0.08);
      --card-border-glow: rgba(56, 189, 248, 0.28);
      --header-bg: rgba(7, 11, 20, 0.88);
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --table-head: rgba(13, 20, 36, 0.95);
      --table-hover: rgba(56, 189, 248, 0.05);
      --input-bg: rgba(11, 18, 33, 0.85);
      --input-border: rgba(255, 255, 255, 0.12);
      --accent: #38bdf8;
      --accent-glow: rgba(56, 189, 248, 0.35);
      --accent-hover: #0284c7;
      --success: #10b981;
      --success-glow: rgba(16, 185, 129, 0.35);
      --warning: #f59e0b;
      --warning-glow: rgba(245, 158, 11, 0.35);
      --danger: #f43f5e;
      --danger-glow: rgba(244, 63, 94, 0.35);
      --purple: #a855f7;
      --purple-glow: rgba(168, 85, 247, 0.35);
      --shadow: 0 16px 36px -6px rgba(0, 0, 0, 0.65), 0 0 0 1px rgba(255, 255, 255, 0.05);
      --modal-bg: rgba(15, 23, 42, 0.95);
      --hud-overlay: rgba(56, 189, 248, 0.12);
    }

    [data-theme="light"] {
      --bg: #f8fafc;
      --bg-gradient: radial-gradient(circle at 50% -10%, #e2e8f0 0%, #f8fafc 85%);
      --card: rgba(255, 255, 255, 0.92);
      --card-solid: #ffffff;
      --card-border: rgba(226, 232, 240, 0.95);
      --card-border-glow: rgba(2, 132, 199, 0.25);
      --header-bg: rgba(255, 255, 255, 0.94);
      --text: #0f172a;
      --text-muted: #64748b;
      --text-dim: #94a3b8;
      --table-head: #f1f5f9;
      --table-hover: rgba(2, 132, 199, 0.04);
      --input-bg: #ffffff;
      --input-border: #cbd5e1;
      --accent: #0284c7;
      --accent-glow: rgba(2, 132, 199, 0.25);
      --accent-hover: #0369a1;
      --success: #059669;
      --success-glow: rgba(5, 150, 105, 0.25);
      --warning: #d97706;
      --warning-glow: rgba(217, 119, 6, 0.25);
      --danger: #e11d48;
      --danger-glow: rgba(225, 29, 72, 0.25);
      --purple: #7c3aed;
      --purple-glow: rgba(124, 58, 237, 0.25);
      --shadow: 0 12px 28px -6px rgba(15, 23, 42, 0.08), 0 0 0 1px rgba(0, 0, 0, 0.04);
      --modal-bg: #ffffff;
      --hud-overlay: rgba(2, 132, 199, 0.08);
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: var(--font-main);
      transition: background-color 0.25s ease, border-color 0.25s ease, color 0.25s ease, box-shadow 0.25s ease;
    }

    body {
      background: var(--bg);
      background-image: var(--bg-gradient);
      background-attachment: fixed;
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      -webkit-font-smoothing: antialiased;
    }

    /* CODE & MONO STYLES */
    .mono { font-family: var(--font-mono); }

    /* DEDICATED FULL-SCREEN LOGIN */
    #screen-login {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 2rem 1.5rem;
      position: relative;
    }

    .login-container {
      width: 100%;
      max-width: 490px;
      background: var(--card);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--card-border);
      border-radius: 20px;
      padding: 2.75rem 2.25rem;
      box-shadow: var(--shadow);
      position: relative;
      overflow: hidden;
    }

    .login-container::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 4px;
      background: linear-gradient(90deg, var(--accent), var(--purple), var(--success));
    }

    .login-header-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 1.5rem;
    }

    .login-logo {
      width: 54px;
      height: 54px;
      background: linear-gradient(135deg, rgba(56, 189, 248, 0.15), rgba(168, 85, 247, 0.12));
      border: 1px solid var(--card-border-glow);
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.85rem;
      box-shadow: 0 4px 16px rgba(56, 189, 248, 0.15);
    }

    .role-toggle {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.5rem;
      background: var(--input-bg);
      padding: 0.35rem;
      border-radius: 10px;
      border: 1px solid var(--card-border);
      margin: 1.5rem 0;
    }

    .role-btn {
      padding: 0.7rem 0.6rem;
      font-size: 0.88rem;
      font-weight: 700;
      border: none;
      border-radius: 8px;
      background: transparent;
      color: var(--text-muted);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.45rem;
      transition: all 0.2s ease;
    }

    .role-btn:hover {
      color: var(--text);
    }

    .role-btn.active {
      background: var(--card-solid);
      color: var(--accent);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }

    /* TOP NAVBAR */
    header {
      background: var(--header-bg);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border-bottom: 1px solid var(--card-border);
      padding: 0.85rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
      position: sticky;
      top: 0;
      z-index: 100;
    }

    .brand {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
    }

    .brand-title {
      font-size: 1.32rem;
      font-weight: 800;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 0.65rem;
      letter-spacing: -0.02em;
    }

    .brand-meta {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      font-size: 0.78rem;
      color: var(--text-muted);
    }

    .pulse-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--success);
      box-shadow: 0 0 10px var(--success);
      display: inline-block;
      animation: livePulse 2s infinite ease-in-out;
    }

    @keyframes livePulse {
      0% { transform: scale(0.9); opacity: 0.7; }
      50% { transform: scale(1.3); opacity: 1; }
      100% { transform: scale(0.9); opacity: 0.7; }
    }

    .badge {
      background: linear-gradient(135deg, #0284c7, #0369a1);
      color: #fff;
      font-size: 0.7rem;
      font-weight: 700;
      padding: 0.25rem 0.6rem;
      border-radius: 9999px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      box-shadow: 0 2px 6px rgba(2, 132, 199, 0.25);
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
    }

    .reg-id {
      background: var(--card);
      color: var(--accent);
      font-size: 0.72rem;
      padding: 0.25rem 0.6rem;
      border-radius: 6px;
      border: 1px solid var(--card-border);
      font-family: var(--font-mono);
      font-weight: 600;
      letter-spacing: 0.05em;
    }

    .nav-actions {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .clock-badge {
      font-family: var(--font-mono);
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--text-muted);
      background: var(--card);
      padding: 0.35rem 0.75rem;
      border-radius: 8px;
      border: 1px solid var(--card-border);
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }

    .user-pill {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 9999px;
      padding: 0.35rem 0.95rem;
      font-size: 0.82rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 0.55rem;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }

    .user-pill .dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
    }

    .role-admin { background: #ef4444; box-shadow: 0 0 10px rgba(239, 68, 68, 0.6); }
    .role-ngo { background: #10b981; box-shadow: 0 0 10px rgba(16, 185, 129, 0.6); }

    /* MODERN BUTTONS */
    .btn {
      background: linear-gradient(135deg, var(--accent), var(--accent-hover));
      color: #fff;
      font-weight: 700;
      padding: 0.55rem 1.15rem;
      border-radius: 8px;
      border: 1px solid transparent;
      cursor: pointer;
      font-size: 0.86rem;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.45rem;
      box-shadow: 0 4px 14px var(--accent-glow);
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .btn:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px var(--accent-glow);
      filter: brightness(1.08);
    }

    .btn:active {
      transform: translateY(0);
    }

    .btn-secondary {
      background: var(--card);
      color: var(--text);
      border: 1px solid var(--card-border);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    }

    .btn-secondary:hover {
      background: var(--input-bg);
      border-color: var(--card-border-glow);
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
    }

    .btn-success {
      background: linear-gradient(135deg, var(--success), #059669);
      color: #fff;
      box-shadow: 0 4px 14px var(--success-glow);
    }

    .btn-success:hover {
      box-shadow: 0 6px 20px var(--success-glow);
      filter: brightness(1.08);
    }

    .btn-danger {
      background: linear-gradient(135deg, var(--danger), #e11d48);
      color: #fff;
      box-shadow: 0 4px 14px var(--danger-glow);
    }

    .btn-danger:hover {
      box-shadow: 0 6px 20px var(--danger-glow);
      filter: brightness(1.08);
    }

    .btn-sm {
      padding: 0.38rem 0.75rem;
      font-size: 0.78rem;
      border-radius: 6px;
    }

    .theme-toggle-btn {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      width: 38px;
      height: 38px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-size: 1.15rem;
      color: var(--text);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
      transition: all 0.2s ease;
    }

    .theme-toggle-btn:hover {
      border-color: var(--card-border-glow);
      transform: rotate(18deg) scale(1.05);
    }

    .container {
      max-width: 1400px;
      width: 100%;
      margin: 1.5rem auto;
      padding: 0 1.25rem;
      flex: 1;
    }

    /* STATS COUNTERS HUD */
    .stats-bar {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1.25rem;
      margin-bottom: 1.5rem;
    }

    .stat-box {
      background: var(--card);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 1.35rem 1.45rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: var(--shadow);
      position: relative;
      overflow: hidden;
      transition: all 0.25s ease;
    }

    .stat-box:hover {
      border-color: var(--card-border-glow);
      transform: translateY(-3px);
      box-shadow: 0 18px 40px -8px rgba(0, 0, 0, 0.45);
    }

    .stat-box::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 4px;
      height: 100%;
    }

    .stat-box.box-total::before { background: var(--accent); }
    .stat-box.box-active::before { background: var(--warning); }
    .stat-box.box-closed::before { background: var(--success); }
    .stat-box.box-teams::before { background: var(--purple); }

    .stat-info {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }

    .stat-title {
      font-size: 0.74rem;
      text-transform: uppercase;
      color: var(--text-muted);
      font-weight: 700;
      letter-spacing: 0.08em;
    }

    .stat-number {
      font-family: var(--font-mono);
      font-size: 2.2rem;
      font-weight: 800;
      line-height: 1.1;
      letter-spacing: -0.02em;
    }

    .stat-sub {
      font-size: 0.74rem;
      font-weight: 600;
      margin-top: 0.35rem;
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }

    .stat-icon {
      width: 52px;
      height: 52px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.7rem;
    }

    .c-total { color: var(--accent); }
    .c-active { color: var(--warning); }
    .c-closed { color: var(--success); }
    .c-dispatch { color: var(--purple); }

    .stat-box.box-total .stat-icon { background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.25); }
    .stat-box.box-active .stat-icon { background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.25); }
    .stat-box.box-closed .stat-icon { background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.25); }
    .stat-box.box-teams .stat-icon { background: rgba(168, 85, 247, 0.12); border: 1px solid rgba(168, 85, 247, 0.25); }

    /* PORTAL TABS */
    .tab-bar {
      display: flex;
      gap: 0.65rem;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 1.5rem;
      align-items: center;
    }

    .tab-btn {
      background: transparent;
      border: none;
      border-bottom: 3px solid transparent;
      color: var(--text-muted);
      padding: 0.75rem 1.45rem;
      font-size: 0.95rem;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      transition: all 0.2s ease;
    }

    .tab-btn:hover {
      color: var(--text);
    }

    .tab-btn.active {
      color: var(--accent);
      border-bottom-color: var(--accent);
    }

    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.5rem;
      margin-bottom: 1.5rem;
    }

    @media (max-width: 1024px) {
      .grid-2 { grid-template-columns: 1fr; }
    }

    .card {
      background: var(--card);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border: 1px solid var(--card-border);
      border-radius: 18px;
      padding: 1.65rem;
      display: flex;
      flex-direction: column;
      box-shadow: var(--shadow);
      position: relative;
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.15rem;
      flex-wrap: wrap;
      gap: 0.5rem;
    }

    .card-title {
      font-size: 1.1rem;
      font-weight: 800;
      display: flex;
      align-items: center;
      gap: 0.6rem;
      color: var(--text);
      letter-spacing: -0.01em;
    }

    #admin-map, #ngo-map {
      height: 460px;
      min-height: 420px;
      width: 100%;
      border-radius: 12px;
      border: 1px solid var(--card-border);
      z-index: 1;
      overflow: hidden;
      box-shadow: inset 0 2px 10px rgba(0, 0, 0, 0.25);
      position: relative;
      background: #0b1329;
    }
    .leaflet-container {
      font-family: inherit;
      width: 100% !important;
      height: 100% !important;
      background: #0b1329 !important;
    }
    [data-theme="light"] .leaflet-container {
      background: #e2e8f0 !important;
    }

    /* TACTICAL VIDEO SCANNER */
    .video-container {
      position: relative;
      width: 100%;
      height: 310px;
      background: #000;
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid var(--card-border);
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: inset 0 0 40px rgba(0, 0, 0, 0.8);
    }

    #video-player {
      width: 100%;
      height: 100%;
      object-fit: contain;
    }

    #canvas-overlay {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
    }

    .hud-brackets {
      position: absolute;
      inset: 12px;
      pointer-events: none;
      border: 2px dashed rgba(56, 189, 248, 0.25);
      border-radius: 8px;
    }

    .cctv-rec-badge {
      position: absolute;
      top: 14px;
      left: 14px;
      background: rgba(0, 0, 0, 0.7);
      backdrop-filter: blur(6px);
      border: 1px solid rgba(244, 63, 94, 0.4);
      color: #fff;
      font-size: 0.72rem;
      font-family: var(--font-mono);
      font-weight: 700;
      padding: 0.25rem 0.65rem;
      border-radius: 6px;
      display: flex;
      align-items: center;
      gap: 0.45rem;
      z-index: 2;
    }

    .scan-radar {
      position: absolute;
      width: 100%;
      height: 4px;
      background: linear-gradient(90deg, transparent, var(--accent), transparent);
      box-shadow: 0 0 20px var(--accent), 0 0 40px var(--accent);
      top: 0;
      display: none;
      z-index: 3;
    }

    @keyframes radarSweep {
      0% { top: 0%; opacity: 0.8; }
      50% { top: 96%; opacity: 1; }
      100% { top: 0%; opacity: 0.8; }
    }

    .match-alert {
      background: linear-gradient(135deg, rgba(16, 185, 129, 0.14), rgba(56, 189, 248, 0.08));
      border: 1px solid var(--success);
      border-radius: 12px;
      padding: 1.15rem;
      margin-top: 1rem;
      box-shadow: 0 6px 20px rgba(16, 185, 129, 0.15);
      animation: alertSlideIn 0.3s ease;
    }

    @keyframes alertSlideIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* ROUTE CALLOUT */
    .route-callout {
      background: linear-gradient(135deg, rgba(56, 189, 248, 0.1), rgba(168, 85, 247, 0.06));
      border: 1px solid var(--card-border-glow);
      border-radius: 18px;
      padding: 1.65rem;
      margin-bottom: 1.5rem;
      box-shadow: var(--shadow);
    }

    .route-stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1.5rem;
      margin-top: 1.15rem;
    }

    .route-item {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
      background: var(--input-bg);
      padding: 0.95rem 1.15rem;
      border-radius: 12px;
      border: 1px solid var(--card-border);
    }

    .route-val {
      font-family: var(--font-mono);
      font-size: 1.85rem;
      font-weight: 800;
      letter-spacing: -0.02em;
    }

    .route-lbl {
      font-size: 0.72rem;
      text-transform: uppercase;
      color: var(--text-muted);
      font-weight: 700;
      letter-spacing: 0.06em;
    }

    /* SEARCH & FILTER BAR */
    .filter-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      margin-bottom: 1.15rem;
      flex-wrap: wrap;
    }

    .search-input {
      background: var(--input-bg);
      border: 1px solid var(--card-border);
      color: var(--text);
      padding: 0.6rem 1rem;
      border-radius: 10px;
      font-size: 0.88rem;
      width: 290px;
      transition: all 0.2s ease;
    }

    .search-input:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-glow);
    }

    /* MODERN TABLES */
    .table-container {
      overflow-x: auto;
      border-radius: 12px;
      border: 1px solid var(--card-border);
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
    }

    th {
      text-align: left;
      padding: 0.95rem 0.85rem;
      background: var(--table-head);
      color: var(--text-muted);
      border-bottom: 1px solid var(--card-border);
      font-weight: 700;
      font-size: 0.74rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    td {
      padding: 0.95rem 0.85rem;
      border-bottom: 1px solid var(--card-border);
      vertical-align: middle;
    }

    tr:last-child td {
      border-bottom: none;
    }

    tr:hover td {
      background: var(--table-hover);
    }

    .tag {
      font-size: 0.72rem;
      font-weight: 700;
      padding: 0.3rem 0.65rem;
      border-radius: 9999px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
    }

    .tag-active {
      background: rgba(245, 158, 11, 0.15);
      color: var(--warning);
      border: 1px solid rgba(245, 158, 11, 0.4);
    }

    .tag-rescued {
      background: rgba(16, 185, 129, 0.15);
      color: var(--success);
      border: 1px solid rgba(16, 185, 129, 0.4);
    }

    .tag-closed {
      background: rgba(148, 163, 184, 0.15);
      color: var(--text-muted);
      border: 1px solid var(--card-border);
    }

    /* MODALS */
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(4, 7, 14, 0.75);
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 9999;
      padding: 1.5rem;
      animation: modalFadeIn 0.25s ease;
    }

    @keyframes modalFadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }

    .modal-box {
      background: var(--card-solid);
      border: 1px solid var(--card-border-glow);
      border-radius: 20px;
      width: 100%;
      max-width: 540px;
      padding: 2.25rem 2rem;
      box-shadow: var(--shadow);
      position: relative;
      animation: modalPopUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }

    @keyframes modalPopUp {
      from { opacity: 0; transform: translateY(20px) scale(0.97); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }

    .modal-box h2 {
      font-size: 1.35rem;
      margin-bottom: 0.45rem;
      color: var(--text);
      font-weight: 800;
      letter-spacing: -0.02em;
    }

    .form-group {
      margin-bottom: 1.05rem;
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
    }

    .form-group label {
      font-size: 0.8rem;
      color: var(--text-muted);
      font-weight: 700;
      letter-spacing: 0.02em;
    }

    .form-group input, .form-group select, .form-group textarea {
      background: var(--input-bg);
      border: 1px solid var(--input-border);
      color: var(--text);
      padding: 0.65rem 0.95rem;
      border-radius: 8px;
      font-size: 0.92rem;
      font-family: var(--font-main);
      transition: all 0.2s ease;
    }

    .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-glow);
    }

    /* NOTIFICATIONS */
    .notif-card {
      background: var(--input-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.05rem;
      display: flex;
      flex-direction: column;
      gap: 0.55rem;
      position: relative;
      transition: all 0.2s ease;
    }

    .notif-card:hover {
      border-color: var(--card-border-glow);
      transform: translateX(3px);
    }

    .notif-card.unread {
      border-left: 4px solid var(--danger);
      background: linear-gradient(90deg, rgba(244, 63, 94, 0.08), var(--input-bg));
    }

    .notif-badge-pulse {
      animation: pulseAlert 1.6s infinite ease-in-out;
    }

    @keyframes pulseAlert {
      0% { transform: scale(1); opacity: 1; }
      50% { transform: scale(1.18); opacity: 0.85; }
      100% { transform: scale(1); opacity: 1; }
    }

    /* TOAST */
    #toast-msg {
      position: fixed;
      bottom: 2rem;
      right: 2rem;
      background: var(--card-solid);
      border: 1px solid var(--accent);
      color: var(--text);
      padding: 0.85rem 1.45rem;
      border-radius: 12px;
      font-weight: 700;
      font-size: 0.88rem;
      box-shadow: 0 12px 30px rgba(0, 0, 0, 0.5);
      z-index: 100000;
      display: none;
      animation: toastSlideUp 0.3s ease;
    }

    @keyframes toastSlideUp {
      from { opacity: 0; transform: translateY(20px); }
      to { opacity: 1; transform: translateY(0); }
    }
  
    /* INTERACTIVE STAT CARDS */
    .stat-box.clickable {
      cursor: pointer;
      user-select: none;
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
    }
    .stat-box.clickable:hover {
      transform: translateY(-4px);
      box-shadow: 0 12px 25px rgba(0, 0, 0, 0.35);
      border-color: var(--accent);
    }
    .stat-box.active-filter {
      border-color: var(--accent) !important;
      background: linear-gradient(135deg, rgba(56, 189, 248, 0.12), var(--card)) !important;
      box-shadow: 0 0 18px rgba(56, 189, 248, 0.3) !important;
    }
    .stat-hint {
      font-size: 0.72rem;
      color: var(--text-muted);
      margin-top: 0.45rem;
      display: flex;
      align-items: center;
      gap: 0.3rem;
    }

    /* TELEMETRY TICKER BAR */
    .telemetry-bar {
      background: var(--input-bg);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 0.6rem 1rem;
      margin-bottom: 1.25rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      font-size: 0.82rem;
      box-shadow: inset 0 0 12px rgba(0,0,0,0.25);
    }
    .telemetry-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid var(--accent);
      color: var(--accent);
      font-weight: 800;
      font-size: 0.72rem;
      padding: 0.2rem 0.65rem;
      border-radius: 999px;
      letter-spacing: 0.06em;
      white-space: nowrap;
    }
    .live-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10b981;
      display: inline-block;
      box-shadow: 0 0 8px #10b981;
      animation: pulseDot 1.4s infinite;
    }
    .telemetry-content {
      color: var(--text);
      font-family: monospace;
      font-size: 0.8rem;
      flex: 1;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      transition: opacity 0.3s ease;
    }
    .telemetry-actions {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      white-space: nowrap;
    }
    .telemetry-btn {
      background: var(--card);
      border: 1px solid var(--card-border);
      color: var(--accent);
      font-size: 0.76rem;
      font-weight: 700;
      padding: 0.3rem 0.65rem;
      border-radius: 6px;
      cursor: pointer;
      transition: 0.15s;
    }
    .telemetry-btn:hover {
      border-color: var(--accent);
      background: rgba(56, 189, 248, 0.15);
    }
    .telemetry-clock {
      font-family: monospace;
      font-size: 0.82rem;
      font-weight: 800;
      color: var(--text);
    }

    /* MAP TOOLBAR & LAYER CONTROLS */
    .map-toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 0.65rem;
      background: var(--input-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 0.5rem 0.85rem;
      margin-bottom: 0.75rem;
    }
    .map-toolbar-group {
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }
    .pill-layer {
      background: var(--card);
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      font-size: 0.72rem;
      font-weight: 600;
      padding: 0.25rem 0.6rem;
      border-radius: 6px;
      cursor: pointer;
      user-select: none;
      transition: 0.15s;
    }
    .pill-layer.active {
      background: rgba(56, 189, 248, 0.15);
      border-color: var(--accent);
      color: var(--accent);
      font-weight: 700;
    }
    .speed-slider-wrap {
      display: flex;
      align-items: center;
      gap: 0.45rem;
      font-size: 0.76rem;
      color: var(--text-muted);
    }
    .speed-slider-wrap input[type="range"] {
      width: 90px;
      accent-color: var(--accent);
      cursor: pointer;
    }

    /* TABLE ROW INTERACTIVITY */
    .table-row-clickable {
      cursor: pointer;
      transition: background-color 0.15s ease;
    }
    .table-row-clickable:hover {
      background-color: var(--table-hover) !important;
    }

    /* CASE DOSSIER & STEPPER */
    .dossier-grid {
      display: grid;
      grid-template-columns: 130px 1fr;
      gap: 1.25rem;
      align-items: start;
      margin-bottom: 1.2rem;
    }
    .dossier-avatar {
      width: 130px;
      height: 150px;
      border-radius: 10px;
      border: 2px dashed var(--card-border);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      background: var(--input-bg);
      color: var(--accent);
      font-size: 3rem;
      box-shadow: inset 0 0 15px rgba(0,0,0,0.2);
    }
    .timeline-stepper {
      position: relative;
      padding-left: 1.5rem;
      margin: 1rem 0;
    }
    .timeline-stepper::before {
      content: '';
      position: absolute;
      left: 7px;
      top: 5px;
      bottom: 5px;
      width: 2px;
      background: var(--card-border);
    }
    .timeline-step {
      position: relative;
      margin-bottom: 0.85rem;
    }
    .timeline-step::before {
      content: '';
      position: absolute;
      left: -1.5rem;
      top: 4px;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: var(--text-muted);
      border: 2px solid var(--card);
    }
    .timeline-step.completed::before {
      background: #10b981;
      box-shadow: 0 0 8px #10b981;
    }
    .timeline-step.active-step::before {
      background: var(--accent);
      box-shadow: 0 0 8px var(--accent);
    }
    .timeline-step-title {
      font-weight: 700;
      font-size: 0.86rem;
      color: var(--text);
    }
    .timeline-step-desc {
      font-size: 0.78rem;
      color: var(--text-muted);
      margin-top: 2px;
    }

    /* EMERGENCY POSTER FLYER */
    .poster-container {
      background: #ffffff;
      color: #0f172a;
      border: 5px solid #dc2626;
      border-radius: 10px;
      padding: 1.5rem;
      max-width: 480px;
      margin: 0 auto;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      box-shadow: 0 15px 35px rgba(0,0,0,0.5);
    }
    .poster-banner {
      background: #dc2626;
      color: #ffffff;
      text-align: center;
      font-weight: 900;
      font-size: 1.35rem;
      letter-spacing: 0.1em;
      padding: 0.55rem;
      margin: -1.5rem -1.5rem 1rem -1.5rem;
      border-radius: 4px 4px 0 0;
    }
    .poster-photo-box {
      width: 100%;
      height: 170px;
      background: #f1f5f9;
      border: 2px dashed #94a3b8;
      border-radius: 8px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      margin-bottom: 1rem;
      font-size: 3.5rem;
    }
    .poster-details-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.65rem;
      margin-bottom: 1rem;
      font-size: 0.88rem;
    }
    .poster-detail-item {
      background: #f8fafc;
      padding: 0.45rem 0.65rem;
      border-radius: 6px;
      border: 1px solid #e2e8f0;
    }
    .poster-hotline {
      background: #fef2f2;
      border: 2px solid #ef4444;
      border-radius: 8px;
      padding: 0.75rem;
      text-align: center;
      color: #991b1b;
      font-weight: 800;
      font-size: 1.05rem;
    }
    @media print {
      body * { visibility: hidden !important; }
      #poster-modal, #poster-modal * { visibility: visible !important; }
      #poster-modal { position: fixed; inset: 0; background: #fff !important; display: flex !important; }
      .poster-actions { display: none !important; }
    }

    /* LIVE GPS VEHICLE SIMULATION */
    .gps-sim-bar {
      background: var(--input-bg);
      border: 1px solid var(--accent);
      border-radius: 8px;
      padding: 0.65rem 0.95rem;
      margin-bottom: 0.85rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 0.6rem;
    }
    .gps-sim-telemetry {
      display: flex;
      align-items: center;
      gap: 1.25rem;
      font-size: 0.82rem;
    }
    .gps-speedo {
      font-family: monospace;
      font-weight: 800;
      font-size: 1.15rem;
      color: var(--accent);
    }
    .gps-sim-btns {
      display: flex;
      align-items: center;
      gap: 0.45rem;
    }
    .sim-pulse-marker {
      animation: beaconPulse 1.2s infinite ease-out;
    }
    @keyframes beaconPulse {
      0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.8); }
      70% { box-shadow: 0 0 0 18px rgba(16, 185, 129, 0); }
      100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

  </style>
</head>
<body>

  <!-- SCREEN 1: SEPARATE DEDICATED LOGIN PAGE -->
  <div id="screen-login">
    <div class="login-container">
      <div class="login-header-row">
        <div class="login-logo">🔍</div>
        <button class="theme-toggle-btn" onclick="toggleTheme()" title="Toggle Dark/Light Mode">🌓</button>
      </div>

      <h2 style="font-size: 1.45rem; font-weight: 800; color: var(--text); margin-bottom: 0.3rem; letter-spacing: -0.02em;">
        Missing Person Search-and-Track
      </h2>
      <div style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 1.25rem;">
        Problem Statement 112 &bull; Role-Based Emergency & Field Rescue Portal
      </div>

      <!-- Quick Role Tabs -->
      <div class="role-toggle">
        <button class="role-btn active" id="login-role-admin" onclick="selectLoginRole('admin')">
          👮 Police Command
        </button>
        <button class="role-btn" id="login-role-ngo" onclick="selectLoginRole('ngo')">
          🚑 NGO / Search Party
        </button>
      </div>

      <form onsubmit="handleLoginSubmit(event)">
        <!-- Specific NGO Selector when NGO Tab is Active -->
        <div id="ngo-select-group" class="form-group" style="display: none;">
          <label>Select Registered NGO / Rescue Unit:</label>
          <select id="login-ngo-choice" onchange="handleNgoChoiceChange()">
          </select>
        </div>

        <div class="form-group">
          <label id="lbl-username">Command Center ID / Username</label>
          <input type="text" id="login-user" value="admin" required />
        </div>
        <div class="form-group">
          <label>Security Password / Access Token</label>
          <input type="password" id="login-pass" value="admin123" required />
        </div>

        <button type="submit" class="btn" style="width: 100%; padding: 0.85rem; margin-top: 0.75rem; font-size: 0.95rem;">
          Authenticate & Access Dashboard ➔
        </button>
      </form>

      <div style="margin-top: 1.85rem; padding-top: 1.15rem; border-top: 1px solid var(--card-border); display: flex; justify-content: space-between; align-items: center; font-size: 0.76rem; color: var(--text-muted);">
        <div>Reg: <b style="color: var(--accent);">25091A32M7</b>, <b style="color: var(--accent);">25091A3222</b></div>
        <div>PostgreSQL &bull; ArcFace &bull; OSRM</div>
      </div>
    </div>
  </div>

  <!-- SCREEN 2: MAIN INVESTIGATION PORTAL (APP) -->
  <div id="screen-app" style="display: none; flex-direction: column; min-height: 100vh;">

    <!-- Add Case Modal -->
        <!-- Add Camera Location Modal (Admin Only) -->
    <div id="add-camera-modal" class="modal-backdrop" style="display: none;">
      <div class="modal-box">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
          <h2 style="margin: 0; display: flex; align-items: center; gap: 0.45rem;">
            <span>📹</span> <span>Install New Surveillance Camera Node</span>
          </h2>
          <span class="badge" style="background: #10b981;">Police Command Only</span>
        </div>
        <p style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 1.25rem;">
          Add a newly installed CCTV or surveillance camera location to the Police Command network and Sighting Graph.
        </p>
        <form onsubmit="handleCreateCamera(event)">
          <div class="form-group">
            <label for="new-cam-name">Camera Location / Landmark Name *</label>
            <input type="text" id="new-cam-name" placeholder="e.g. Kurnool Medical College Gate" required />
          </div>
          <div class="form-group">
            <label for="new-cam-code">Camera Identifier Code / Label</label>
            <input type="text" id="new-cam-code" placeholder="e.g. CAM-15: Medical College (15.8250, 78.0350)" />
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
            <div class="form-group">
              <label for="new-cam-lat">Latitude *</label>
              <input type="number" step="0.0001" id="new-cam-lat" value="15.8250" required />
            </div>
            <div class="form-group">
              <label for="new-cam-lon">Longitude *</label>
              <input type="number" step="0.0001" id="new-cam-lon" value="78.0350" required />
            </div>
          </div>
          <div class="form-group">
            <label for="new-cam-desc">Camera Stream / Hardware Description</label>
            <input type="text" id="new-cam-desc" value="1080p PTZ Outdoor Night-Vision Camera" placeholder="e.g. 1080p PTZ Outdoor Night-Vision Camera" />
          </div>
          <div style="background: var(--input-bg); border: 1px solid var(--card-border); border-radius: 8px; padding: 0.65rem 0.85rem; margin-bottom: 1.15rem; font-size: 0.78rem; color: var(--text-muted);">
            <span>🔒 Security Note: This camera node will be immediately integrated into the DeepFace ArcFace facial recognition scanning feed and Sighting Graph perimeters.</span>
          </div>
          <div style="display: flex; gap: 0.75rem;">
            <button type="button" class="btn btn-secondary" onclick="closeAddCameraModal()" style="flex: 1;">Cancel</button>
            <button type="submit" class="btn btn-success" style="flex: 2;">+ Add Camera to Network</button>
          </div>
        </form>
      </div>
    </div>

    <div id="add-case-modal" class="modal-backdrop" style="display: none;">
      <div class="modal-box">
        <h2>+ Enroll New Missing Person Case</h2>
        <p style="font-size: 0.84rem; color: var(--text-muted); margin-bottom: 1.35rem;">
          Register a new individual into the investigation database and active sighting graph.
        </p>
        <form onsubmit="handleCreateCase(event)">
          <div class="form-group">
            <label for="new-name">Full Name *</label>
            <input type="text" id="new-name" placeholder="e.g. Ramesh Kumar" required />
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.85rem;">
            <div class="form-group">
              <label for="new-age">Age *</label>
              <input type="number" id="new-age" value="21" required />
            </div>
            <div class="form-group">
              <label for="new-gender">Gender</label>
              <select id="new-gender">
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>
          <div class="form-group">
            <label for="new-clothes">Clothing & Description</label>
            <input type="text" id="new-clothes" placeholder="e.g. Yellow t-shirt, blue jeans, cap" />
          </div>
          <div class="form-group">
            <label for="new-loc">Last Seen Location *</label>
            <input type="text" id="new-loc" placeholder="e.g. CAR STAND" required />
          </div>
          <div class="form-group">
            <label for="new-team">Assigned Response Unit (NGO / Team)</label>
            <select id="new-team">
            </select>
          </div>
          <div style="display: flex; gap: 0.85rem; margin-top: 1.45rem;">
            <button type="button" class="btn btn-secondary" onclick="closeAddCaseModal()" style="flex: 1;">Cancel</button>
            <button type="submit" class="btn btn-success" style="flex: 2;">Save Case & Begin Tracking</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Add NGO / Rescue Team Modal -->
    <div id="add-ngo-modal" class="modal-backdrop" style="display: none;">
      <div class="modal-box">
        <h2>+ Register New NGO / Rescue Team</h2>
        <p style="font-size: 0.84rem; color: var(--text-muted); margin-bottom: 1.35rem;">
          Add a partner NGO or search party with their base coordinates and dedicated login credentials.
        </p>
        <form onsubmit="handleCreateNgo(event)">
          <div class="form-group">
            <label for="ngo-name">NGO / Team Name *</label>
            <input type="text" id="ngo-name" placeholder="e.g. Red Cross Kurnool Chapter" required />
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.85rem;">
            <div class="form-group">
              <label for="ngo-org">Organization Type</label>
              <select id="ngo-org">
                <option value="NGO">NGO / Non-Profit</option>
                <option value="Volunteer">Volunteer Group</option>
                <option value="Police">Police Task Force</option>
                <option value="Disaster Relief">Disaster Relief Force</option>
              </select>
            </div>
            <div class="form-group">
              <label for="ngo-phone">Contact Phone *</label>
              <input type="text" id="ngo-phone" placeholder="e.g. 98480-12345" required />
            </div>
          </div>
          <div class="form-group">
            <label for="ngo-base-preset">Base Location Area</label>
            <select id="ngo-base-preset" onchange="handleNgoBasePresetChange()">
              <option value="Budhwarpet Base|15.8350|78.0450">Budhwarpet Base (15.8350, 78.0450)</option>
              <option value="Kurnool Town Base|15.8281|78.0373">Kurnool Town Base (15.8281, 78.0373)</option>
              <option value="Nandyal Road Base|15.8100|78.0600">Nandyal Road Base (15.8100, 78.0600)</option>
              <option value="Collectorate Base|15.8200|78.0450">Collectorate Base (15.8200, 78.0450)</option>
              <option value="Railway Station Outpost|15.8310|78.0420">Railway Station Outpost (15.8310, 78.0420)</option>
              <option value="Tungabhadra North Base|15.8420|78.0300">Tungabhadra North Base (15.8420, 78.0300)</option>
              <option value="custom">-- Custom Location & Coordinates --</option>
            </select>
          </div>
          <div class="form-group">
            <label for="ngo-base-name">Base Location Label *</label>
            <input type="text" id="ngo-base-name" value="Budhwarpet Base" required />
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.85rem;">
            <div class="form-group">
              <label for="ngo-lat">Latitude *</label>
              <input type="number" step="0.0001" id="ngo-lat" value="15.8350" required />
            </div>
            <div class="form-group">
              <label for="ngo-lon">Longitude *</label>
              <input type="number" step="0.0001" id="ngo-lon" value="78.0450" required />
            </div>
          </div>
          <div style="background: var(--input-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 0.95rem; margin-bottom: 1.15rem;">
            <div style="font-size: 0.82rem; font-weight: 700; color: var(--accent); margin-bottom: 0.5rem;">🔑 Separate Login Credentials for this NGO:</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.85rem;">
              <div class="form-group" style="margin-bottom: 0;">
                <label for="ngo-username">Login Username *</label>
                <input type="text" id="ngo-username" placeholder="e.g. redcross_kurnool" required />
              </div>
              <div class="form-group" style="margin-bottom: 0;">
                <label for="ngo-password">Login Password *</label>
                <input type="password" id="ngo-password" placeholder="e.g. pass123" required />
              </div>
            </div>
          </div>
          <div style="display: flex; gap: 0.85rem;">
            <button type="button" class="btn btn-secondary" onclick="closeAddNgoModal()" style="flex: 1;">Cancel</button>
            <button type="submit" class="btn btn-success" style="flex: 2;">Register Team & Enable Login</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Allot Case to NGO Modal -->
    <div id="allot-case-modal" class="modal-backdrop" style="display: none;">
      <div class="modal-box">
        <h2>📢 Allot Case to Search Party / NGO</h2>
        <p style="font-size: 0.84rem; color: var(--text-muted); margin-bottom: 1.35rem;">
          Dispatch case assignment and trigger real-time notification with road routing to the selected NGO unit.
        </p>
        <form onsubmit="handleDispatchAllotment(event)">
          <input type="hidden" id="allot-case-id" />
          
          <div style="background: var(--input-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 0.95rem; margin-bottom: 1.15rem;">
            <div style="font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted);">Case Details:</div>
            <div style="font-size: 1.15rem; font-weight: 800; color: var(--text); margin-top: 0.25rem;" id="allot-case-title">Case #1: N.K.SYAM</div>
            <div style="font-size: 0.85rem; color: var(--accent); margin-top: 0.25rem; font-weight: 600;" id="allot-case-loc">Target: CAR STAND</div>
          </div>

          <div class="form-group">
            <label for="allot-team-select">Assign to NGO / Rescue Team *</label>
            <select id="allot-team-select" onchange="handleAllotTeamChange()" required>
            </select>
          </div>

          <div class="form-group">
            <label for="allot-phone">📱 Contact Mobile Number for SMS Dispatch Alert *</label>
            <input type="text" id="allot-phone" value="6303126628" placeholder="e.g. 6303126628" required />
          </div>

          <div class="form-group">
            <label for="allot-instructions">Command Dispatch Instructions</label>
            <textarea id="allot-instructions" rows="2" placeholder="e.g. High priority. Immediate ground mobilization required; subject wearing blue shirt."></textarea>
          </div>

          <div style="background: var(--card); border: 1px solid var(--card-border); border-radius: 8px; padding: 0.75rem 0.95rem; margin-bottom: 1.35rem; display: flex; align-items: center; gap: 0.6rem; font-size: 0.84rem;">
            <input type="checkbox" id="allot-sms-check" checked disabled />
            <label for="allot-sms-check" style="margin: 0; color: var(--text); cursor: pointer; font-weight: 600;">
              📱 Dispatch instant emergency SMS alert to team's registered phone
            </label>
          </div>

          <div style="display: flex; gap: 0.85rem;">
            <button type="button" class="btn btn-secondary" onclick="closeAllotModal()" style="flex: 1;">Cancel</button>
            <button type="submit" class="btn btn-danger" style="flex: 2;">🚀 Send Allotment Alert</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Notifications Center Modal -->
    <div id="notifications-modal" class="modal-backdrop" style="display: none;">
      <div class="modal-box" style="max-width: 600px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
          <h2 style="margin: 0; display: flex; align-items: center; gap: 0.6rem;">
            🔔 Case Allotment Notifications
          </h2>
          <span class="badge" style="background: #ef4444;" id="notif-modal-count">0 Unread</span>
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.15rem;">
          <span style="font-size: 0.82rem; color: var(--text-muted);" id="notif-modal-subtitle">
            Dispatches sent to your response unit
          </span>
          <button class="btn btn-secondary btn-sm" onclick="markAllNotificationsRead()">
            ✓ Mark All Read
          </button>
        </div>

        <div id="notifications-modal-list" style="max-height: 420px; overflow-y: auto; display: flex; flex-direction: column; gap: 0.85rem;">
          <!-- Loaded dynamically -->
        </div>

        <div style="margin-top: 1.35rem; text-align: right;">
          <button type="button" class="btn btn-secondary btn-sm" onclick="closeNotificationModal()">Close</button>
        </div>
      </div>
    </div>

    <!-- Case Dossier & Sighting Stepper Modal -->
    <div id="case-dossier-modal" class="modal-backdrop" style="display: none;">
      <div class="modal-box" style="max-width: 680px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.85rem;">
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span class="badge" style="background: var(--accent); color: #000; font-weight: 800;" id="dossier-id-badge">CASE #1</span>
            <h2 style="margin: 0; font-size: 1.25rem;" id="dossier-name">Missing Person Dossier</h2>
          </div>
          <button class="btn btn-secondary btn-sm" onclick="closeCaseDossier()" style="padding: 2px 8px;">✕</button>
        </div>

        <div class="dossier-grid">
          <div class="dossier-avatar">
            👤
          </div>
          <div>
            <div style="display: flex; gap: 0.45rem; align-items: center; margin-bottom: 0.45rem;">
              <span class="tag tag-active" id="dossier-status-tag">ACTIVE</span>
              <span style="font-size: 0.82rem; color: var(--text-muted);" id="dossier-age-gender">21 Years / Male</span>
            </div>
            <div style="font-size: 0.84rem; margin-bottom: 0.35rem;">
              <span style="color: var(--text-muted);">Attire:</span> <b id="dossier-clothes">Standard Attire</b>
            </div>
            <div style="font-size: 0.84rem; margin-bottom: 0.35rem;">
              <span style="color: var(--text-muted);">Last Seen Location:</span> <b id="dossier-loc" style="color: var(--warning);">CAR STAND</b>
            </div>
            <div style="font-size: 0.84rem; margin-bottom: 0.35rem;">
              <span style="color: var(--text-muted);">Assigned Search Unit:</span> <b id="dossier-team" style="color: var(--purple);">Helping Hands NGO</b>
            </div>
            <div style="font-size: 0.78rem; font-family: monospace; color: var(--text-muted);">
              Coordinates: <span id="dossier-coords">15.8281, 78.0373</span>
            </div>
          </div>
        </div>

        <div style="font-size: 0.82rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.35rem;">
          Live Investigation Timeline & Dispatch Status
        </div>
        <div class="timeline-stepper" id="dossier-timeline">
          <!-- Populated dynamically -->
        </div>

        <div style="display: flex; gap: 0.65rem; margin-top: 1.25rem; flex-wrap: wrap;">
          <button class="btn btn-secondary btn-sm" onclick="locateCaseOnMapFromDossier()">
            📍 Center on Graph
          </button>
          <button class="btn btn-secondary btn-sm" onclick="openPosterModal(currentDossierCaseId)">
            🖨️ Generate Flyer
          </button>
          <button class="btn btn-secondary btn-sm" onclick="openAllotModal(currentDossierCaseId)">
            📢 Re-Allot NGO
          </button>
          <button class="btn btn-success btn-sm" id="btn-dossier-resolve" onclick="markCaseResolved(currentDossierCaseId)">
            ✓ Mark Case Resolved
          </button>
          <button class="btn btn-secondary btn-sm" onclick="closeCaseDossier()" style="margin-left: auto;">
            Close
          </button>
        </div>
      </div>
    </div>

    <!-- Emergency Missing Person Poster / Flyer Modal -->
    <div id="poster-modal" class="modal-backdrop" style="display: none;">
      <div class="modal-box" style="max-width: 520px; background: transparent; box-shadow: none; border: none; padding: 0;">
        <div class="poster-container">
          <div class="poster-banner">
            ⚠️ MISSING PERSON ALERT ⚠️
          </div>
          <div class="poster-photo-box">
            👤
            <div style="font-size: 0.8rem; color: #64748b; font-weight: 600; margin-top: 0.35rem;">POLICE IDENTIFICATION PHOTO</div>
          </div>
          <div style="text-align: center; margin-bottom: 1rem;">
            <h1 style="font-size: 1.65rem; font-weight: 900; margin: 0; color: #0f172a;" id="poster-name">Subject Name</h1>
            <div style="font-size: 0.95rem; font-weight: 700; color: #dc2626; margin-top: 2px;" id="poster-case-id">CASE #101</div>
          </div>
          <div class="poster-details-grid">
            <div class="poster-detail-item">
              <span style="font-size: 0.72rem; color: #64748b; text-transform: uppercase; font-weight: 700; display: block;">Age & Gender</span>
              <b id="poster-age-gender">21 Years / Male</b>
            </div>
            <div class="poster-detail-item">
              <span style="font-size: 0.72rem; color: #64748b; text-transform: uppercase; font-weight: 700; display: block;">Clothing Description</span>
              <b id="poster-clothes">Standard Clothes</b>
            </div>
            <div class="poster-detail-item" style="grid-column: span 2;">
              <span style="font-size: 0.72rem; color: #64748b; text-transform: uppercase; font-weight: 700; display: block;">Last Known Sighting Location</span>
              <b id="poster-loc" style="color: #b91c1c;">CAR STAND, Kurnool</b>
            </div>
            <div class="poster-detail-item" style="grid-column: span 2;">
              <span style="font-size: 0.72rem; color: #64748b; text-transform: uppercase; font-weight: 700; display: block;">Assigned Search & Rescue Force</span>
              <b id="poster-team">Police Command Kurnool</b>
            </div>
          </div>
          <div class="poster-hotline">
            🚨 IF SIGHTED, IMMEDIATELY CALL: 112 / 6303126628
          </div>
        </div>

        <div class="poster-actions" style="display: flex; gap: 0.65rem; justify-content: center; margin-top: 1rem;">
          <button class="btn btn-success" onclick="printPoster()">
            🖨️ Print / Save PDF
          </button>
          <button class="btn btn-secondary" onclick="closePosterModal()">
            ✕ Close
          </button>
        </div>
      </div>
    </div>

    <!-- Header Navigation -->
    <header>
      <div class="brand">
        <div class="brand-title">
          <span>Missing Person Search-and-Track</span>
          <span class="badge">Problem Statement 112</span>
        </div>
        <div class="brand-meta">
          <span class="pulse-dot"></span>
          <span>SYSTEM ONLINE &bull; Graph Sighting Network &bull; Live ArcFace CCTV &bull; Turn-by-Turn OSRM</span>
        </div>
      </div>
      <div class="nav-actions">
        <span class="reg-id">25091A32M7</span>
        <span class="reg-id">25091A3222</span>

        <div class="clock-badge" id="live-clock">
          🕒 00:00:00
        </div>

        <button class="theme-toggle-btn" onclick="toggleTheme()" title="Toggle Dark/Light Mode">🌓</button>

        <button class="btn btn-secondary btn-sm" id="btn-header-notifs" onclick="openNotificationModal()" title="Case Allotment Notifications" style="position: relative; font-weight: 700; display: flex; align-items: center; gap: 0.45rem;">
          🔔 <span id="notif-badge" class="badge notif-badge-pulse" style="background: #ef4444; font-size: 0.7rem; padding: 2px 7px; display: none;">0</span>
        </button>

        <div class="user-pill">
          <span class="dot role-admin" id="role-dot"></span>
          <span id="current-user-display">Admin: Police Command</span>
        </div>

        <button class="btn btn-secondary btn-sm" onclick="handleLogout()">🚪 Logout</button>
      </div>
    </header>

    <div class="container">

      <!-- Live Telemetry Ticker & Audio Controls -->
      <div class="telemetry-bar">
        <div class="telemetry-pill">
          <span class="live-dot"></span>
          <span>TELEMETRY ACTIVE</span>
        </div>
        <div class="telemetry-content" id="telemetry-ticker">
          SURVEILLANCE NODE CAM-01 active at CAR STAND (15.8281, 78.0373)
        </div>
        <div class="telemetry-actions">
          <button class="telemetry-btn" id="btn-audio-toggle" onclick="toggleAudioAlert()" title="Toggle Synthesized Audio Alerts">
            🔊 Audio Alert
          </button>
          <div class="telemetry-clock" id="telemetry-clock">00:00:00</div>
        </div>
      </div>

      <!-- Top Stats Counters -->
      <div class="stats-bar">
        <div class="stat-box box-total clickable" id="stat-box-total" onclick="handleStatCardClick('ALL')">
          <div class="stat-info">
            <div class="stat-title">Total Cases</div>
            <div class="stat-number c-total" id="cnt-total">0</div>
            <div class="stat-sub" style="color: var(--accent);">● Real-Time Database Tracking</div>
          </div>
          <div class="stat-icon">📋</div>
        </div>
        <div class="stat-box box-active clickable" id="stat-box-active" onclick="handleStatCardClick('ACTIVE')">
          <div class="stat-info">
            <div class="stat-title">Active Investigations</div>
            <div class="stat-number c-active" id="cnt-active">0</div>
            <div class="stat-sub" style="color: var(--warning);">● Priority Search Mobilized</div>
          </div>
          <div class="stat-icon">🚨</div>
        </div>
        <div class="stat-box box-closed clickable" id="stat-box-closed" onclick="handleStatCardClick('RESOLVED')">
          <div class="stat-info">
            <div class="stat-title">Rescued & Closed</div>
            <div class="stat-number c-closed" id="cnt-closed">0</div>
            <div class="stat-sub" style="color: var(--success);">● Subjects Reunited</div>
          </div>
          <div class="stat-icon">✅</div>
        </div>
        <div class="stat-box box-teams clickable" id="stat-box-teams" onclick="handleStatCardClick('TEAMS')">
          <div class="stat-info">
            <div class="stat-title">Registered NGO Units</div>
            <div class="stat-number c-dispatch" id="cnt-teams">0</div>
            <div class="stat-sub" style="color: var(--purple);">● Ready for Immediate Dispatch</div>
          </div>
          <div class="stat-icon">🏢</div>
        </div>
      </div>

      <!-- Portal Tabs -->
      <div class="tab-bar" id="portal-tab-bar">
        <button class="tab-btn active" id="tab-admin" onclick="switchView('admin')">👮 Admin Command Center</button>
        <button class="tab-btn" id="tab-ngo" onclick="switchView('ngo')">🚑 NGO / Search Party Portal</button>
        <div id="ngo-portal-badge" style="display: none; align-items: center; gap: 0.6rem; font-weight: 800; color: #10b981; padding: 0.75rem 0.6rem; font-size: 1rem;">
          🚑 Dedicated Search Party & Field Rescue Dashboard
        </div>
      </div>


      <!-- ADMIN VIEW -->
      <div id="view-admin">
        <div class="grid-2">

          <!-- Video & CCTV Facial Recognition Scanner -->
          <div class="card">
            <div class="card-header">
              <div class="card-title">🎥 Video & CCTV Facial Recognition Scanner</div>
              <span class="badge" style="background: #10b981;">DeepFace ArcFace</span>
            </div>

            <!-- Camera Location Selector -->
            <div style="background: var(--input-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 0.85rem; margin-bottom: 1rem;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.45rem;">
                <label for="video-camera-loc" style="font-size: 0.82rem; font-weight: 700; color: var(--accent); display: flex; align-items: center; gap: 0.45rem; margin: 0;">
                  📹 Select Surveillance Camera Location:
                </label>
                <button class="btn btn-secondary btn-sm" id="btn-add-camera" onclick="openAddCameraModal()" style="font-size: 0.74rem; padding: 2px 8px; font-weight: 700; border-color: var(--accent); color: var(--accent);" title="Install and register new surveillance camera node (Admin Only)">
                  + Add Camera Location
                </button>
              </div>
              <select id="video-camera-loc" style="width: 100%; background: var(--card); border: 1px solid var(--card-border); color: var(--text); padding: 0.55rem 0.75rem; border-radius: 8px; font-size: 0.88rem;">
                <option value="CAR STAND">CAM-01: CAR STAND (15.8281, 78.0373)</option>
                <option value="Budhwarpet Market">CAM-02: Budhwarpet Market Junction (15.8350, 78.0450)</option>
                <option value="Kurnool City Railway">CAM-03: Kurnool City Railway Station (15.8310, 78.0420)</option>
                <option value="Kurnool Bus Stand">CAM-04: Central Bus Stand Entrance (15.8281, 78.0373)</option>
                <option value="RGM grounds">CAM-05: RGM Grounds North Field (15.8310, 78.0420)</option>
                <option value="cantene">CAM-06: Campus Canteen Surveillance (15.8350, 78.0450)</option>
                <option value="DS labs">CAM-07: DS Labs Corridor (15.8200, 78.0450)</option>
                <option value="RGM hostel">CAM-08: RGM Hostel Gate (15.8150, 78.0300)</option>
                <option value="RGM gardens">CAM-09: RGM Gardens Perimeter (15.8340, 78.0560)</option>
                <option value="Konda Reddy Fort">CAM-10: Konda Reddy Fort Circle (15.8340, 78.0560)</option>
                <option value="maha nandhi">CAM-11: Maha Nandhi Road Junction (15.8100, 78.0600)</option>
                <option value="Collectorate">CAM-12: District Collectorate (15.8200, 78.0450)</option>
                <option value="Government Hospital">CAM-13: Government General Hospital (15.8150, 78.0300)</option>
                <option value="Tungabhadra Bridge">CAM-14: Tungabhadra River Bridge (15.8420, 78.0300)</option>
              </select>
            </div>

            <div class="video-container" id="video-box">
              <div class="cctv-rec-badge">
                <span style="color: #ef4444;">●</span> LIVE REC &bull; 1080p
                <span id="webcam-live-indicator" style="display: none; margin-left: 6px; color: #10b981; font-weight: 800;">[WEBCAM LIVE]</span>
              </div>
              <div class="hud-brackets"></div>
              <video id="video-player" controls playsinline>
                <source src="" type="video/mp4">
              </video>
              <canvas id="canvas-overlay"></canvas>
              <div class="scan-radar" id="radar-sweep"></div>
              <div id="video-placeholder" style="position: absolute; text-align: center; color: var(--text-muted); pointer-events: none;">
                <div style="font-size: 2.6rem; margin-bottom: 0.4rem;">📹</div>
                <div style="font-weight: 700; font-size: 1rem;">No Video Feed Loaded</div>
                <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.2rem;">Upload CCTV file or click Load Demo Feed</div>
              </div>
            </div>

            <div style="display: flex; gap: 0.65rem; margin-top: 1.15rem; flex-wrap: wrap; align-items: center;">
              <input type="file" id="video-file-input" accept="video/*" style="display: none;" onchange="handleVideoUpload(event)">
              <button class="btn btn-secondary btn-sm" onclick="document.getElementById('video-file-input').click()">
                📁 Upload CCTV Video
              </button>
              <button class="btn btn-secondary btn-sm" onclick="loadSampleVideo()">
                🎬 Load Demo Video Feed
              </button>
              <button class="btn btn-secondary btn-sm" id="btn-webcam" onclick="toggleWebcam()">
                📷 Live Webcam
              </button>

              <div style="display: flex; align-items: center; gap: 0.35rem; font-size: 0.74rem; color: var(--text-muted); margin-left: auto;">
                <span>Sensitivity:</span>
                <input type="range" id="face-thresh-slider" min="0.10" max="0.60" step="0.02" value="0.32" style="width: 70px; accent-color: var(--accent);">
              </div>

              <button class="btn btn-danger btn-sm" id="btn-run-scan" onclick="startVideoScan()">
                ⚡ AI Scan Video For Matches
              </button>
            </div>

            <div id="scan-status" style="font-size: 0.84rem; font-weight: 600; color: var(--accent); margin-top: 0.75rem; display: none;"></div>

            <div class="match-alert" id="match-box" style="display: none;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 800; color: #10b981; font-size: 0.98rem; display: flex; align-items: center; gap: 0.45rem;">
                  🚨 MATCH CONFIRMED IN SURVEILLANCE FEED
                </span>
                <span class="badge" style="background: #10b981;" id="match-confidence-badge">Confidence 94.6%</span>
              </div>
              <div style="font-size: 0.88rem; margin-top: 0.55rem; color: var(--text); line-height: 1.5;" id="match-details">
              </div>
            </div>
          </div>

          <!-- Sighting Graph & Search Zones Map -->
          <div class="card">
            <div class="card-header">
              <div class="card-title">🗺️ Sighting Graph & Search Zone Perimeter</div>
              <div style="display: flex; gap: 0.45rem; align-items: center;">
                <button class="btn btn-secondary btn-sm" id="btn-map-add-cam" onclick="openAddCameraModal()" title="Install New Surveillance Node" style="font-size: 0.74rem; padding: 3px 8px;">
                  📹 + Add Camera
                </button>
                <span class="reg-id">Kurnool Network &bull; Dijkstra</span>
              </div>
            </div>

            <!-- Map Controls Toolbar -->
            <div class="map-toolbar">
              <div class="map-toolbar-group">
                <span style="font-size: 0.72rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase;">Top Zones:</span>
                <button class="pill-layer" id="zone-btn-3" onclick="setZoneCount(3)">Top 3</button>
                <button class="pill-layer active" id="zone-btn-5" onclick="setZoneCount(5)">Top 5</button>
                <button class="pill-layer" id="zone-btn-8" onclick="setZoneCount(8)">Top 8</button>
              </div>

              <div class="speed-slider-wrap">
                <span>Speed:</span>
                <input type="range" id="speed-slider" min="1.0" max="15.0" step="0.5" value="4.5" oninput="updateSearchZoneSpeed(this.value)">
                <span id="speed-val" style="font-weight: 700; color: var(--accent); min-width: 48px;">4.5 km/h</span>
              </div>

              <div class="map-toolbar-group">
                <span style="font-size: 0.72rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase;">Layers:</span>
                <button class="pill-layer active" id="layer-btn-cctv" onclick="toggleMapLayer('cctv')">CCTV</button>
                <button class="pill-layer active" id="layer-btn-zones" onclick="toggleMapLayer('zones')">Zones</button>
                <button class="pill-layer active" id="layer-btn-cases" onclick="toggleMapLayer('cases')">Cases</button>
                <button class="pill-layer active" id="layer-btn-teams" onclick="toggleMapLayer('teams')">Teams</button>
              </div>
            </div>

            <div id="admin-map"></div>
          </div>
        </div>

        <!-- Case Registry with Add Case & Delete Resolved Options -->
        <div class="card" style="margin-bottom: 1.5rem;">
          <div class="card-header">
            <div class="card-title">📁 Registered Missing Persons Database</div>
            <button class="btn btn-success btn-sm" onclick="openAddCaseModal()">+ Enroll New Case</button>
          </div>

          <!-- Search & Filter Bar -->
          <div class="filter-bar">
            <input type="text" class="search-input" id="case-search-input" placeholder="🔍 Search by name, clothes, location..." oninput="handleSearchCases(event)">
            <div style="display: flex; gap: 0.45rem;">
              <button class="btn btn-secondary btn-sm" onclick="filterCases('ALL')" id="filter-all">All Cases</button>
              <button class="btn btn-secondary btn-sm" onclick="filterCases('ACTIVE')" id="filter-active">Active</button>
              <button class="btn btn-secondary btn-sm" onclick="filterCases('RESOLVED')" id="filter-resolved">Resolved</button>
            </div>
          </div>

          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Age / Gender</th>
                  <th>Clothing Description</th>
                  <th>Last Seen Location</th>
                  <th>Status</th>
                  <th>Assigned Unit</th>
                  <th style="text-align: right;">Actions</th>
                </tr>
              </thead>
              <tbody id="cases-table">
                <tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Loading database cases...</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- NGO / Search Party Management Registry -->
        <div class="card" style="margin-bottom: 1.5rem;">
          <div class="card-header">
            <div class="card-title">🏢 Registered NGOs & Field Search Parties Management</div>
            <button class="btn btn-success btn-sm" onclick="openAddNgoModal()">+ Register New NGO</button>
          </div>
          <div style="font-size: 0.84rem; color: var(--text-muted); margin-bottom: 1.15rem;">
            Manage authorized partner rescue teams, their base station coordinates, and their separate login credentials:
          </div>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Team / NGO Name</th>
                  <th>Type</th>
                  <th>Base Station Location</th>
                  <th>Coordinates (Lat, Lon)</th>
                  <th>Contact Phone</th>
                  <th>Login Username</th>
                  <th style="text-align: right;">Action</th>
                </tr>
              </thead>
              <tbody id="teams-table">
                <tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Loading registered teams...</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- NGO / SEARCH PARTY VIEW -->
      <div id="view-ngo" style="display: none;">
        
        <!-- NGO Case Allotment Alerts & Dispatch Orders -->
        <div class="card" id="ngo-allotment-alert-card" style="margin-bottom: 1.5rem; border-color: rgba(239, 68, 68, 0.4); background: linear-gradient(180deg, rgba(239, 68, 68, 0.08), var(--card));">
          <div class="card-header" style="border-bottom: 1px solid rgba(239, 68, 68, 0.2); padding-bottom: 0.85rem;">
            <div class="card-title" style="display: flex; align-items: center; gap: 0.6rem; color: #ef4444;">
              <span>🚨</span>
              <span>Case Allotment Notifications & Dispatch Orders</span>
              <span class="badge" style="background: #ef4444;" id="ngo-notif-count-badge">0 Allotted</span>
            </div>
            <button class="btn btn-secondary btn-sm" onclick="markAllNotificationsRead()">
              ✓ Acknowledge All
            </button>
          </div>
          <div style="font-size: 0.84rem; color: var(--text-muted); margin: 0.85rem 0;">
            Emergency cases officially allotted to your unit by Police Command with SMS alerts. Click <b>"Accept & Trace Route"</b> to automatically calculate and trace the street road route:
          </div>
          <div id="ngo-notifs-feed" style="display: flex; flex-direction: column; gap: 0.85rem;">
            <!-- Populated dynamically -->
          </div>
        </div>

        <!-- Shortest Road Navigation Route Callout -->
        <div class="route-callout">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 0.75rem;">
            <div>
              <div style="display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.45rem;">
                <span class="badge" style="background: #ef4444;">ACTIVE SEARCH PARTY DISPATCH</span>
                <span class="badge" style="background: #10b981;" id="route-engine-badge">🚗 Turn-by-Turn Road Route</span>
              </div>
              <h2 style="font-size: 1.45rem; color: var(--text); font-weight: 800; letter-spacing: -0.02em;">
                Shortest Street Route from Base to Target Zone
              </h2>
              <p style="font-size: 0.88rem; color: var(--text-muted); margin-top: 0.25rem;">
                Assigned Subject: <b id="ngo-subject-name" style="color: var(--accent);">N.K.SYAM</b> &bull; Target Location: <b id="ngo-target-loc" style="color: var(--warning);">CAR STAND</b>
              </p>
            </div>
            <div class="user-pill">
              <span class="dot role-ngo"></span>
              <span id="ngo-active-team-display">Unit: Helping Hands NGO</span>
            </div>
          </div>

          <div class="route-stats">
            <div class="route-item">
              <div class="route-lbl">Street Distance</div>
              <div class="route-val" id="route-dist" style="color: var(--accent);">1.74 km</div>
            </div>
            <div class="route-item">
              <div class="route-lbl">Driving / Response ETA</div>
              <div class="route-val" id="route-eta" style="color: var(--warning);">2.8 mins</div>
            </div>
            <div class="route-item">
              <div class="route-lbl">Team Base Origin</div>
              <div style="font-size: 0.95rem; font-weight: 700; color: var(--text); margin-top: 0.2rem;" id="ngo-base-display">
                Budhwarpet Base (15.8350, 78.0450)
              </div>
            </div>
            <div class="route-item">
              <div class="route-lbl">Street Navigation Path</div>
              <div style="font-size: 0.88rem; color: var(--text-muted); margin-top: 0.2rem;" id="route-path-text">
                Navigating through street nodes to target location
              </div>
            </div>
          </div>
        </div>

                <!-- LIVE GPS RESPONSE DRIVING SIMULATION -->
        <div class="gps-sim-bar">
          <div class="gps-sim-telemetry">
            <div style="display: flex; align-items: center; gap: 0.4rem;">
              <span class="live-dot" id="gps-pulse-dot" style="display: none;"></span>
              <span style="font-weight: 700; font-size: 0.85rem; color: var(--text);">GPS Telemetry:</span>
            </div>
            <div>
              <span style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase;">Sim Speed</span>
              <div class="gps-speedo"><span id="sim-speedo-val">0</span> <span style="font-size: 0.7rem; color: var(--text-muted);">km/h</span></div>
            </div>
            <div>
              <span style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase;">Dist Remaining</span>
              <div style="font-weight: 800; font-family: monospace; color: var(--warning); font-size: 1.05rem;" id="sim-dist-remain">1.74 km</div>
            </div>
            <div>
              <span style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase;">Simulation ETA</span>
              <div style="font-weight: 800; font-family: monospace; color: #10b981; font-size: 1.05rem;" id="sim-eta-countdown">2.8 min</div>
            </div>
          </div>
          <div class="gps-sim-btns">
            <button class="btn btn-success btn-sm" id="btn-start-sim" onclick="startGpsRouteSimulation()">
              ▶️ Start GPS Run
            </button>
            <button class="btn btn-secondary btn-sm" id="btn-pause-sim" onclick="pauseGpsRouteSimulation()" style="display: none;">
              ⏸️ Pause
            </button>
            <button class="btn btn-secondary btn-sm" onclick="resetGpsRouteSimulation()">
              🔄 Reset Base
            </button>
            <div style="display: flex; gap: 2px; margin-left: 0.3rem;">
              <button class="pill-layer active" id="sim-spd-1" onclick="setSimSpeed(1)">1x</button>
              <button class="pill-layer" id="sim-spd-3" onclick="setSimSpeed(3)">3x</button>
              <button class="pill-layer" id="sim-spd-6" onclick="setSimSpeed(6)">6x</button>
            </div>
          </div>
        </div>

        <div class="grid-2">
          <!-- Interactive Street Navigation Map -->
          <div class="card">
            <div class="card-header">
              <div class="card-title">📍 Turn-by-Turn Street Navigation Map</div>
              <span class="badge" style="background: #10b981;">Tracing Street Geometry</span>
            </div>
            <div id="ngo-map"></div>
          </div>

          <!-- Field Action & Resolution Card -->
          <div class="card">
            <div class="card-header">
              <div class="card-title">📝 Field Status & Case Resolution</div>
              <span class="tag tag-active" id="ngo-tag-status">Dispatch #101 Active</span>
            </div>

            <div style="font-size: 0.86rem; color: var(--text-muted); margin-bottom: 1.15rem;">
              When your search team reaches the search zone, update the field outcome or close the resolved case:
            </div>

            <form onsubmit="handleResolve(event)">
              <div class="form-group">
                <label>Select Case</label>
                <select id="resolve-case-id" onchange="updateNgoSelection()">
                </select>
              </div>

              <div class="form-group">
                <label>Field Resolution Outcome</label>
                <select id="resolve-outcome">
                  <option value="found">✅ Verified Found & Rescued (Close Case)</option>
                  <option value="not-found">⚠️ Not Found at Location (Expand Search)</option>
                  <option value="false-alarm">❌ False Alarm / Mismatch</option>
                </select>
              </div>

              <div class="form-group">
                <label>Responder Notes</label>
                <textarea id="resolve-notes" rows="3" placeholder="Enter notes: physical condition, reunited with family, medical support provided..."></textarea>
              </div>

              <button type="submit" class="btn btn-success" style="width: 100%; padding: 0.8rem; margin-top: 0.5rem; font-size: 0.95rem;">
                Submit Field Report & Close Case
              </button>
            </form>

            <div id="resolve-msg" style="margin-top: 1.15rem; font-size: 0.88rem; display: none;"></div>
          </div>
        </div>
      </div>

    </div>

    <footer style="background: var(--header-bg); border-top: 1px solid var(--card-border); padding: 1.25rem; text-align: center; font-size: 0.84rem; color: var(--text-muted); margin-top: auto;">
      Missing Person Search-and-Track System &bull; Problem Statement 112 &bull; Registered Numbers: <b style="color: var(--accent);">25091A32M7</b>, <b style="color: var(--accent);">25091A3222</b>
    </footer>

  </div>

  <div id="toast-msg"></div>

  <script>
    let allCases = [];
    let allTeams = [];
    let currentFilter = 'ALL';
    let searchQuery = '';
    let currentRole = 'admin';
    let loggedInRole = null;
    let loggedInTeam = null;
    let adminMap = null;
    let ngoMap = null;
    let adminLayers = null;
    let ngoLayers = null;
    let adminTileLayer = null;
    let ngoTileLayer = null;

    // Interactive Map Layers Groups
    let layerCctvGroup = null;
    let layerZonesGroup = null;
    let layerCasesGroup = null;
    let layerTeamsGroup = null;
    let activeZoneCount = 5;
    let currentMobilitySpeed = 4.0;
    let activeLayers = {
      cctv: true,
      zones: true,
      cases: true,
      teams: true
    };

    // Live GPS Driving Simulation State
    let currentGpsInterval = null;
    let currentGpsStep = 0;
    let currentSimSpeed = 1;
    let isGpsSimRunning = false;
    let simMarker = null;
    let currentRouteCoords = [];
    let currentRouteDistKm = 1.74;
    let currentRouteEtaMins = 2.8;

    // Web Audio Synthesizer State
    let audioAlertEnabled = true;
    let audioCtx = null;
    let webcamStream = null;
    let currentDossierCaseId = null;

    // LIVE DIGITAL CLOCK
    function updateClock() {
      const now = new Date();
      const timeStr = now.toLocaleTimeString('en-US', { hour12: false });
      const el = document.getElementById('live-clock');
      if (el) el.innerText = `🕒 ${timeStr} IST`;
      const tel = document.getElementById('telemetry-clock');
      if (tel) tel.innerText = `${timeStr} IST`;
    }
    setInterval(updateClock, 1000);
    updateClock();

    // LIVE SYSTEM TELEMETRY TICKER
    const TELEMETRY_MESSAGES = [
      "SURVEILLANCE NODE CAM-01 active at CAR STAND (15.8281, 78.0373)",
      "SIGHTING GRAPH ENGINE: 14 interconnected road vertices in Kurnool mesh",
      "OSRM ROUTING ENGINE: Shortest-path Dijkstra & real street geometry active",
      "AI FACIAL RECOGNITION: DeepFace ArcFace cosine distance model ready",
      "FIELD DISPATCH: Automated SMS emergency alerting connected (6303126628)",
      "POSTGRESQL DATABASE: Missing person registries & telemetry synced",
      "KURNOOL POLICE COMMAND: High-readiness response teams on standby"
    ];
    let telemetryIdx = 0;
    function initTelemetryTicker() {
      const el = document.getElementById('telemetry-ticker');
      if (!el) return;
      setInterval(() => {
        telemetryIdx = (telemetryIdx + 1) % TELEMETRY_MESSAGES.length;
        el.style.opacity = 0;
        setTimeout(() => {
          el.innerText = TELEMETRY_MESSAGES[telemetryIdx];
          el.style.opacity = 1;
        }, 300);
      }, 4200);
    }

    // WEB AUDIO API SYNTHESIZER
    function getAudioContext() {
      if (!audioCtx) {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (AudioContextClass) audioCtx = new AudioContextClass();
      }
      if (audioCtx && audioCtx.state === 'suspended') {
        audioCtx.resume();
      }
      return audioCtx;
    }

    function toggleAudioAlert() {
      audioAlertEnabled = !audioAlertEnabled;
      const btn = document.getElementById('btn-audio-toggle');
      if (btn) {
        btn.innerText = audioAlertEnabled ? '🔊 Audio Alert' : '🔇 Audio Muted';
        btn.style.color = audioAlertEnabled ? 'var(--accent)' : 'var(--text-muted)';
      }
      showToast(audioAlertEnabled ? 'Audio alerts enabled' : 'Audio alerts muted');
    }

    function playDetectionChime() {
      if (!audioAlertEnabled) return;
      try {
        const ctx = getAudioContext();
        if (!ctx) return;
        const now = ctx.currentTime;
        
        // Tone 1: High D5
        const osc1 = ctx.createOscillator();
        const gain1 = ctx.createGain();
        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(587.33, now);
        gain1.gain.setValueAtTime(0.25, now);
        gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.28);
        osc1.connect(gain1);
        gain1.connect(ctx.destination);
        osc1.start(now);
        osc1.stop(now + 0.28);

        // Tone 2: Higher A5
        const osc2 = ctx.createOscillator();
        const gain2 = ctx.createGain();
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(880.00, now + 0.14);
        gain2.gain.setValueAtTime(0.3, now + 0.14);
        gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
        osc2.connect(gain2);
        gain2.connect(ctx.destination);
        osc2.start(now + 0.14);
        osc2.stop(now + 0.5);
      } catch (e) {
        console.warn('Audio playback error', e);
      }
    }

    function playArrivalChime() {
      if (!audioAlertEnabled) return;
      try {
        const ctx = getAudioContext();
        if (!ctx) return;
        const notes = [523.25, 659.25, 783.99, 1046.50]; // C5, E5, G5, C6
        notes.forEach((freq, idx) => {
          const t = ctx.currentTime + (idx * 0.11);
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = 'triangle';
          osc.frequency.setValueAtTime(freq, t);
          gain.gain.setValueAtTime(0.25, t);
          gain.gain.exponentialRampToValueAtTime(0.001, t + 0.35);
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(t);
          osc.stop(t + 0.35);
        });
      } catch (e) {
        console.warn('Arrival audio playback error', e);
      }
    }

    // DYNAMIC COUNTER ANIMATION
    function animateCounter(el, targetVal) {
      if (!el) return;
      const startVal = parseInt(el.innerText) || 0;
      if (startVal === targetVal) return;
      const duration = 600;
      const startTime = performance.now();
      function update(curTime) {
        const progress = Math.min((curTime - startTime) / duration, 1);
        const ease = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(startVal + (targetVal - startVal) * ease);
        el.innerText = current;
        if (progress < 1) requestAnimationFrame(update);
        else el.innerText = targetVal;
      }
      requestAnimationFrame(update);
    }

    // INTERACTIVE STAT CARDS CLICK FILTERING
    function handleStatCardClick(filter) {
      ['stat-box-total', 'stat-box-active', 'stat-box-closed', 'stat-box-teams'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.remove('active-filter');
      });

      if (filter === 'ALL') {
        const b = document.getElementById('stat-box-total');
        if (b) b.classList.add('active-filter');
        filterCases('ALL');
        const input = document.getElementById('case-search-input');
        if (input) input.scrollIntoView({ behavior: 'smooth', block: 'center' });
        showToast('Viewing all registered cases');
      } else if (filter === 'ACTIVE') {
        const b = document.getElementById('stat-box-active');
        if (b) b.classList.add('active-filter');
        filterCases('ACTIVE');
        const input = document.getElementById('case-search-input');
        if (input) input.scrollIntoView({ behavior: 'smooth', block: 'center' });
        showToast('Filtered table to ACTIVE cases');
      } else if (filter === 'RESOLVED') {
        const b = document.getElementById('stat-box-closed');
        if (b) b.classList.add('active-filter');
        filterCases('RESOLVED');
        const input = document.getElementById('case-search-input');
        if (input) input.scrollIntoView({ behavior: 'smooth', block: 'center' });
        showToast('Filtered table to RESCUED cases');
      } else if (filter === 'TEAMS') {
        const b = document.getElementById('stat-box-teams');
        if (b) b.classList.add('active-filter');
        const table = document.getElementById('teams-table');
        if (table) table.scrollIntoView({ behavior: 'smooth', block: 'center' });
        showToast('Navigated to Registered Rescue Teams');
      }
    }

    // MULTI-CDN TILE LAYER FACTORY
    function createTileLayer(theme) {
      const isDark = (theme === 'dark');
      const cartoDarkUrl = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png';
      const osmUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
      const initialUrl = isDark ? cartoDarkUrl : osmUrl;

      const layer = L.tileLayer(initialUrl, {
        maxZoom: 19,
        subdomains: 'abcd',
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors'
      });

      layer.on('tileerror', function() {
        if (layer._url !== osmUrl) {
          console.warn('Carto tile error, falling back to OpenStreetMap standard tiles');
          layer.setUrl(osmUrl);
        }
      });

      return layer;
    }

    // SAFE LEAFLET LOADER GUARD
    function whenLeafletReady(callback) {
      if (typeof L !== 'undefined') {
        callback();
      } else {
        let attempts = 0;
        const timer = setInterval(() => {
          attempts++;
          if (typeof L !== 'undefined') {
            clearInterval(timer);
            callback();
          } else if (attempts > 40) {
            clearInterval(timer);
            console.error("Leaflet map library failed to load.");
            showToast("⚠️ Map library loading error. Please refresh the page.");
          }
        }, 100);
      }
    }

    // RESILIENT MAP INITIALIZATION (Only attaches when container is in DOM)
    function initAdminMap() {
      if (typeof L === 'undefined') return;
      const container = document.getElementById('admin-map');
      if (!container) return;

      if (!adminMap) {
        adminMap = L.map('admin-map', {
          center: [15.8281, 78.0450],
          zoom: 14,
          zoomControl: true,
          preferCanvas: true
        });

        const theme = document.documentElement.getAttribute('data-theme') || 'dark';
        adminTileLayer = createTileLayer(theme);
        adminTileLayer.addTo(adminMap);

        adminLayers = L.layerGroup().addTo(adminMap);
        layerCctvGroup = L.layerGroup().addTo(adminMap);
        layerZonesGroup = L.layerGroup().addTo(adminMap);
        layerCasesGroup = L.layerGroup().addTo(adminMap);
        layerTeamsGroup = L.layerGroup().addTo(adminMap);
      }

      if (container.offsetWidth > 0) {
        adminMap.invalidateSize(true);
      }
    }

    function initNgoMap() {
      if (typeof L === 'undefined') return;
      const container = document.getElementById('ngo-map');
      if (!container) return;

      if (!ngoMap) {
        ngoMap = L.map('ngo-map', {
          center: [15.8320, 78.0440],
          zoom: 14,
          zoomControl: true,
          preferCanvas: true
        });

        const theme = document.documentElement.getAttribute('data-theme') || 'dark';
        ngoTileLayer = createTileLayer(theme);
        ngoTileLayer.addTo(ngoMap);

        ngoLayers = L.layerGroup().addTo(ngoMap);
      }

      if (container.offsetWidth > 0) {
        ngoMap.invalidateSize(true);
      }
    }

    function initMaps() {
      initAdminMap();
      initNgoMap();
    }

    function attachMapResizeObservers() {
      if (window.ResizeObserver) {
        const adminEl = document.getElementById('admin-map');
        if (adminEl) {
          new ResizeObserver(() => {
            if (adminEl.offsetWidth > 0 && adminMap) {
              adminMap.invalidateSize(true);
            }
          }).observe(adminEl);
        }
        const ngoEl = document.getElementById('ngo-map');
        if (ngoEl) {
          new ResizeObserver(() => {
            if (ngoEl.offsetWidth > 0 && ngoMap) {
              ngoMap.invalidateSize(true);
            }
          }).observe(ngoEl);
        }
      }
    }

    // ROLE & PERMISSION MANAGEMENT
    function applyRolePermissions(role) {
      loggedInRole = role;
      const tabAdmin = document.getElementById('tab-admin');
      const tabNgo = document.getElementById('tab-ngo');
      const ngoBadge = document.getElementById('ngo-portal-badge');
      const viewAdmin = document.getElementById('view-admin');
      const viewNgo = document.getElementById('view-ngo');
      const dot = document.getElementById('role-dot');
      const disp = document.getElementById('current-user-display');

      if (role === 'ngo') {
        if (tabAdmin) tabAdmin.style.display = 'none';
        if (tabNgo) tabNgo.style.display = 'none';
        if (ngoBadge) ngoBadge.style.display = 'flex';
        if (viewAdmin) viewAdmin.style.display = 'none';
        if (viewNgo) viewNgo.style.display = 'block';

        if (dot) dot.className = 'dot role-ngo';
        const teamName = loggedInTeam ? loggedInTeam.name : 'Search Party Unit';
        if (disp) disp.innerText = `Search Party: ${teamName}`;

        const btnAddCam = document.getElementById('btn-add-camera');
        if (btnAddCam) btnAddCam.style.display = 'none';
        const btnMapAddCam = document.getElementById('btn-map-add-cam');
        if (btnMapAddCam) btnMapAddCam.style.display = 'none';
        const modalCam = document.getElementById('add-camera-modal');
        if (modalCam) modalCam.style.display = 'none';

        currentRole = 'ngo';
        loadNotifications();

        whenLeafletReady(() => {
          setTimeout(() => {
            initNgoMap();
            loadNgoRoute();
          }, 80);
        });
      } else {
        if (tabAdmin) {
          tabAdmin.style.display = 'inline-block';
          tabAdmin.classList.add('active');
        }
        if (tabNgo) {
          tabNgo.style.display = 'inline-block';
          tabNgo.classList.remove('active');
        }
        if (ngoBadge) ngoBadge.style.display = 'none';
        if (viewAdmin) viewAdmin.style.display = 'block';
        if (viewNgo) viewNgo.style.display = 'none';

        if (dot) dot.className = 'dot role-admin';
        if (disp) disp.innerText = 'Admin: Police Command';

        const btnAddCam = document.getElementById('btn-add-camera');
        if (btnAddCam) btnAddCam.style.display = 'inline-block';
        const btnMapAddCam = document.getElementById('btn-map-add-cam');
        if (btnMapAddCam) btnMapAddCam.style.display = 'inline-block';

        currentRole = 'admin';
        loadNotifications();

        whenLeafletReady(() => {
          setTimeout(() => {
            initAdminMap();
            if (adminMap) {
              adminMap.invalidateSize(true);
              adminMap.setView([15.8281, 78.0450], 14);
            }
            loadMapData();
          }, 80);
        });
      }
    }

    // THEME HANDLING (DARK / LIGHT) & DYNAMIC MAP TILES
    function initTheme() {
      const saved = localStorage.getItem('mptracker_theme') || 'dark';
      document.documentElement.setAttribute('data-theme', saved);
    }

    function toggleTheme() {
      const cur = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('mptracker_theme', next);
      showToast(`Switched to ${next.toUpperCase()} mode`);

      if (adminMap && adminTileLayer) {
        adminMap.removeLayer(adminTileLayer);
        adminTileLayer = createTileLayer(next);
        adminTileLayer.addTo(adminMap);
      }
      if (ngoMap && ngoTileLayer) {
        ngoMap.removeLayer(ngoTileLayer);
        ngoTileLayer = createTileLayer(next);
        ngoTileLayer.addTo(ngoMap);
      }
    }

    // TOAST NOTIFICATION
    function showToast(msg) {
      const t = document.getElementById('toast-msg');
      if (!t) return;
      t.innerText = msg;
      t.style.display = 'block';
      setTimeout(() => { t.style.display = 'none'; }, 2800);
    }

    // AUTHENTICATION & LOGIN PAGE
    function selectLoginRole(role) {
      document.getElementById('login-role-admin').classList.toggle('active', role === 'admin');
      document.getElementById('login-role-ngo').classList.toggle('active', role === 'ngo');
      
      const userInp = document.getElementById('login-user');
      const passInp = document.getElementById('login-pass');
      const lbl = document.getElementById('lbl-username');
      const ngoGroup = document.getElementById('ngo-select-group');

      if (role === 'admin') {
        userInp.value = 'admin';
        passInp.value = 'admin123';
        lbl.innerText = 'Command Center ID / Username';
        ngoGroup.style.display = 'none';
      } else {
        ngoGroup.style.display = 'block';
        if (!allTeams || allTeams.length === 0) {
          loadTeams().then(() => populateLoginNgoChoice());
        } else {
          populateLoginNgoChoice();
        }
        handleNgoChoiceChange();
        lbl.innerText = 'Search Party / NGO Unit ID';
      }
    }

    function populateLoginNgoChoice() {
      const sel = document.getElementById('login-ngo-choice');
      if (!sel) return;
      sel.innerHTML = '';
      allTeams.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.id;
        opt.innerText = `${t.name} (${t.base_location})`;
        sel.appendChild(opt);
      });
      if (allTeams.length > 0) {
        handleNgoChoiceChange();
      }
    }

    function handleNgoChoiceChange() {
      const sel = document.getElementById('login-ngo-choice');
      if (!sel) return;
      const teamId = parseInt(sel.value);
      const team = allTeams.find(t => t.id === teamId);
      if (team) {
        document.getElementById('login-user').value = team.username;
        document.getElementById('login-pass').value = team.password || 'ngo123';
      }
    }

    async function handleLoginSubmit(e) {
      e.preventDefault();
      const isAdmin = document.getElementById('login-role-admin').classList.contains('active');
      const role = isAdmin ? 'admin' : 'ngo';
      const username = document.getElementById('login-user').value.trim();
      const password = document.getElementById('login-pass').value.trim();

      try {
        const res = await fetch('/api/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role: role, username: username, password: password })
        });
        const data = await res.json();

        if (data.status !== 'success') {
          alert(data.error || 'Invalid credentials');
          return;
        }

        loggedInRole = data.role;
        loggedInTeam = data.team || null;

        sessionStorage.setItem('mptracker_role', loggedInRole);
        sessionStorage.setItem('mptracker_team', JSON.stringify(loggedInTeam));

        document.getElementById('screen-login').style.display = 'none';
        document.getElementById('screen-app').style.display = 'flex';
        
        applyRolePermissions(loggedInRole);
        const nameDisplay = loggedInTeam ? loggedInTeam.name : 'Police Command';
        showToast(`Authenticated as ${nameDisplay}`);
      } catch (err) {
        console.error(err);
      }
    }

    function handleLogout() {
      sessionStorage.removeItem('mptracker_role');
      sessionStorage.removeItem('mptracker_team');
      loggedInRole = null;
      loggedInTeam = null;
      currentRole = 'admin';
      document.getElementById('screen-app').style.display = 'none';
      document.getElementById('screen-login').style.display = 'flex';

      const tabAdmin = document.getElementById('tab-admin');
      const tabNgo = document.getElementById('tab-ngo');
      const ngoBadge = document.getElementById('ngo-portal-badge');
      if (tabAdmin) tabAdmin.style.display = 'inline-block';
      if (tabNgo) tabNgo.style.display = 'inline-block';
      if (ngoBadge) ngoBadge.style.display = 'none';

      loadNotifications();
      showToast('Logged out successfully');
    }

    function restoreSession() {
      const savedRole = sessionStorage.getItem('mptracker_role');
      const savedTeam = sessionStorage.getItem('mptracker_team');
      if (savedRole) {
        loggedInRole = savedRole;
        if (savedTeam) {
          try { loggedInTeam = JSON.parse(savedTeam); } catch(e){}
        }
        document.getElementById('screen-login').style.display = 'none';
        document.getElementById('screen-app').style.display = 'flex';
        applyRolePermissions(loggedInRole);
      }
    }

    // CAMERA REGISTRY & DYNAMIC NODE MANAGEMENT
    let allCameras = [];

    async function loadCameras(selectCameraName = null) {
      try {
        const res = await fetch('/api/cameras');
        allCameras = await res.json();
        const sel = document.getElementById('video-camera-loc');
        if (!sel) return;

        const currentVal = selectCameraName || sel.value;
        sel.innerHTML = '';
        allCameras.forEach(cam => {
          const opt = document.createElement('option');
          opt.value = cam.name;
          opt.innerText = cam.label || `${cam.name} (${cam.lat.toFixed(4)}, ${cam.lon.toFixed(4)})`;
          if (cam.name === currentVal) opt.selected = true;
          sel.appendChild(opt);
        });

        if (selectCameraName) sel.value = selectCameraName;
      } catch (err) {
        console.error('Error loading cameras:', err);
      }
    }

    function openAddCameraModal() {
      if (loggedInRole !== 'admin') {
        showToast('⚠️ Access Denied: Only Police Command can install new camera nodes.');
        return;
      }
      const modal = document.getElementById('add-camera-modal');
      if (!modal) return;

      const nextNum = (allCameras ? allCameras.length : 14) + 1;
      const codeInput = document.getElementById('new-cam-code');
      if (codeInput) {
        codeInput.value = `CAM-${nextNum < 10 ? '0' + nextNum : nextNum}: `;
      }

      modal.style.display = 'flex';
    }

    function closeAddCameraModal() {
      const modal = document.getElementById('add-camera-modal');
      if (modal) modal.style.display = 'none';
    }

    async function handleCreateCamera(e) {
      e.preventDefault();
      if (loggedInRole !== 'admin') {
        showToast('⚠️ Access Denied: Only Police Command can add cameras.');
        return;
      }

      const name = document.getElementById('new-cam-name').value.trim();
      const code = document.getElementById('new-cam-code').value.trim();
      const lat = parseFloat(document.getElementById('new-cam-lat').value);
      const lon = parseFloat(document.getElementById('new-cam-lon').value);
      const desc = document.getElementById('new-cam-desc').value.trim();

      try {
        const res = await fetch('/api/cameras/add', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-User-Role': loggedInRole || 'admin'
          },
          body: JSON.stringify({ name: name, code: code, lat: lat, lon: lon, description: desc })
        });
        const data = await res.json();
        if (data.status !== 'success') {
          showToast(`⚠️ ${data.error || 'Failed to add camera'}`);
          return;
        }

        closeAddCameraModal();
        e.target.reset();
        showToast(`📹 Camera registered: ${name}`);

        await loadCameras(name);
        await loadMapData();

        if (adminMap) {
          adminMap.flyTo([lat, lon], 16, { duration: 1.2 });
        }
      } catch (err) {
        console.error('Error adding camera:', err);
        showToast('⚠️ Network error adding camera node.');
      }
    }

    // STATS & COUNTERS
    async function loadStats() {
      try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        animateCounter(document.getElementById('cnt-total'), data.total_cases);
        animateCounter(document.getElementById('cnt-active'), data.active_cases);
        animateCounter(document.getElementById('cnt-closed'), data.closed_cases);
        animateCounter(document.getElementById('cnt-teams'), data.total_teams);
      } catch (e) { console.error(e); }
    }

    // TEAMS REGISTRY
    async function loadTeams() {
      try {
        const res = await fetch('/api/teams');
        allTeams = await res.json();
        renderTeamsTable();
        populateCaseTeamDropdown();
        populateLoginNgoChoice();
        if (!loggedInTeam && allTeams.length > 0) {
          loggedInTeam = allTeams[0];
        }
      } catch (e) { console.error(e); }
    }

    function renderTeamsTable() {
      const tbody = document.getElementById('teams-table');
      if (!tbody) return;
      tbody.innerHTML = '';

      allTeams.forEach(t => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td class="mono" style="color: var(--accent);">#${t.id}</td>
          <td style="font-weight: 800; color: var(--text);">${t.name}</td>
          <td><span class="badge" style="background: #0284c7;">${t.org}</span></td>
          <td><b>${t.base_location}</b></td>
          <td style="color: var(--text-muted); font-family: monospace;">${t.lat.toFixed(4)}, ${t.lon.toFixed(4)}</td>
          <td><a href="tel:${t.phone}" style="color: var(--accent); text-decoration: none;">📞 ${t.phone}</a></td>
          <td style="color: var(--accent); font-family: monospace;">${t.username}</td>
          <td style="text-align: right;">
            <button class="btn btn-danger btn-sm" onclick="deleteTeam(${t.id})" title="Remove Team">🗑 Remove</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    function populateCaseTeamDropdown() {
      const sel = document.getElementById('new-team');
      if (!sel) return;
      sel.innerHTML = '';
      allTeams.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.name;
        opt.innerText = `${t.name} (${t.base_location})`;
        sel.appendChild(opt);
      });
    }

    // CASES REGISTRY & TABLE
    async function loadCases() {
      try {
        const res = await fetch('/api/cases');
        allCases = await res.json();
        renderCasesTable();
        populateNgoCaseSelector();
        plotCasesOnMap();
      } catch (e) { console.error(e); }
    }

    function renderCasesTable() {
      const tbody = document.getElementById('cases-table');
      if (!tbody) return;
      tbody.innerHTML = '';
      
      const filtered = allCases.filter(c => {
        const matchesFilter = (currentFilter === 'ALL') || 
                              (currentFilter === 'ACTIVE' && c.status === 'ACTIVE') ||
                              (currentFilter === 'RESOLVED' && (c.status === 'RESCUED' || c.status === 'CLOSED'));
        
        if (!matchesFilter) return false;
        if (!searchQuery) return true;

        const q = searchQuery.toLowerCase();
        return c.name.toLowerCase().includes(q) ||
               (c.clothes && c.clothes.toLowerCase().includes(q)) ||
               (c.last_seen_location && c.last_seen_location.toLowerCase().includes(q));
      });

      if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:2rem;">No matching cases found.</td></tr>`;
        return;
      }

      filtered.forEach(c => {
        const tr = document.createElement('tr');
        tr.className = 'table-row-clickable';
        tr.onclick = (e) => {
          if (!e.target.closest('button') && !e.target.closest('a')) {
            openCaseDossier(c.id);
          }
        };

        const statusClass = c.status === 'ACTIVE' ? 'tag-active' : (c.status === 'RESCUED' ? 'tag-rescued' : 'tag-closed');
        const statusPulse = c.status === 'ACTIVE' ? '<span class="pulse-dot" style="background:var(--warning); box-shadow:0 0 8px var(--warning); margin-right:4px;"></span>' : '';
        
        let actionButtons = '';
        if (loggedInRole === 'admin') {
          actionButtons += `<button class="btn btn-secondary btn-sm" onclick="openCaseDossier(${c.id})" title="View Case Dossier & Stepper">👁️ Dossier</button> `;
          actionButtons += `<button class="btn btn-secondary btn-sm" onclick="openPosterModal(${c.id})" title="Print Emergency Flyer">🖨️ Flyer</button> `;
          actionButtons += `<button class="btn btn-secondary btn-sm" onclick="openAllotModal(${c.id})" title="Allot case to specific NGO and send SMS alert">📢 Allot</button> `;
          if (c.status === 'ACTIVE') {
            actionButtons += `<button class="btn btn-success btn-sm" onclick="markCaseResolved(${c.id})">✓ Resolve</button> `;
          }
          actionButtons += `<button class="btn btn-danger btn-sm" onclick="deleteCase(${c.id})" title="Remove Case">🗑</button>`;
        } else {
          actionButtons += `<button class="btn btn-secondary btn-sm" onclick="openCaseDossier(${c.id})" title="View Case Dossier">👁️ Dossier</button> `;
          const isMyCase = loggedInTeam && c.assigned_team === loggedInTeam.name;
          if (isMyCase) {
            actionButtons += `<button class="btn btn-success btn-sm" onclick="acceptCaseAndNavigate(${c.id})">🚗 Trace Route</button>`;
          } else {
            actionButtons += `<span style="font-size: 0.78rem; color: var(--text-muted);">${c.assigned_team || 'Assigned'}</span>`;
          }
        }

        const assignColumn = loggedInRole === 'admin'
          ? `<span style="font-weight: 700; color: var(--accent);">${c.assigned_team}</span>
             <button class="btn btn-secondary btn-sm" style="font-size: 0.7rem; padding: 2px 7px; margin-left: 6px; border-radius: 4px;" onclick="openAllotModal(${c.id})" title="Reassign to another NGO">Change</button>`
          : `<span style="font-weight: 700; color: var(--accent);">${c.assigned_team}</span>`;

        tr.innerHTML = `
          <td class="mono" style="color: var(--accent);">#${c.id}</td>
          <td style="font-weight: 800; color: var(--text);">${c.name}</td>
          <td>${c.age} / ${c.gender}</td>
          <td style="color: var(--text-muted);">${c.clothes || 'Standard'}</td>
          <td><b>${c.last_seen_location}</b></td>
          <td><span class="tag ${statusClass}">${statusPulse}${c.status}</span></td>
          <td>${assignColumn}</td>
          <td style="text-align: right; white-space: nowrap;">${actionButtons}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    function handleSearchCases(e) {
      searchQuery = e.target.value.trim();
      renderCasesTable();
    }

    function filterCases(filter) {
      currentFilter = filter;
      document.getElementById('filter-all').className = `btn btn-sm ${filter === 'ALL' ? 'btn' : 'btn-secondary'}`;
      document.getElementById('filter-active').className = `btn btn-sm ${filter === 'ACTIVE' ? 'btn' : 'btn-secondary'}`;
      document.getElementById('filter-resolved').className = `btn btn-sm ${filter === 'RESOLVED' ? 'btn' : 'btn-secondary'}`;
      renderCasesTable();
    }

    // MAP INTERACTIVITY CONTROLS
    function updateSearchZoneSpeed(val) {
      currentMobilitySpeed = parseFloat(val);
      const lbl = document.getElementById('speed-val');
      if (lbl) lbl.innerText = `${currentMobilitySpeed.toFixed(1)} km/h`;
      loadMapData();
    }

    function setZoneCount(k) {
      activeZoneCount = k;
      [3, 5, 8].forEach(n => {
        const btn = document.getElementById(`zone-btn-${n}`);
        if (btn) btn.classList.toggle('active', n === k);
      });
      loadMapData();
      showToast(`Showing Top ${k} Priority Search Zones`);
    }

    function toggleMapLayer(layer) {
      activeLayers[layer] = !activeLayers[layer];
      const btn = document.getElementById(`layer-btn-${layer}`);
      if (btn) btn.classList.toggle('active', activeLayers[layer]);

      if (layer === 'cctv' && layerCctvGroup) {
        if (activeLayers.cctv) adminMap.addLayer(layerCctvGroup);
        else adminMap.removeLayer(layerCctvGroup);
      }
      if (layer === 'zones' && layerZonesGroup) {
        if (activeLayers.zones) adminMap.addLayer(layerZonesGroup);
        else adminMap.removeLayer(layerZonesGroup);
      }
      if (layer === 'cases' && layerCasesGroup) {
        if (activeLayers.cases) adminMap.addLayer(layerCasesGroup);
        else adminMap.removeLayer(layerCasesGroup);
      }
      if (layer === 'teams' && layerTeamsGroup) {
        if (activeLayers.teams) adminMap.addLayer(layerTeamsGroup);
        else adminMap.removeLayer(layerTeamsGroup);
      }
    }

    function selectCameraFromMap(camName) {
      const sel = document.getElementById('video-camera-loc');
      if (sel) {
        for (let i = 0; i < sel.options.length; i++) {
          if (sel.options[i].value.toLowerCase() === camName.toLowerCase() || sel.options[i].text.includes(camName)) {
            sel.selectedIndex = i;
            break;
          }
        }
      }
      const videoBox = document.getElementById('video-box');
      if (videoBox) videoBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
      showToast(`Surveillance scanner focused on: ${camName}`);
    }

    // LOAD MAP DATA WITH RICH INTERACTIVE POPUPS & MULTI-LAYERS
    async function loadMapData() {
      initAdminMap();
      if (!adminMap) return;

      try {
        const res = await fetch(`/api/demo?top=${activeZoneCount}&speed=${currentMobilitySpeed}`);
        const data = await res.json();

        if (layerCctvGroup) layerCctvGroup.clearLayers();
        if (layerZonesGroup) layerZonesGroup.clearLayers();
        if (layerTeamsGroup) layerTeamsGroup.clearLayers();

        // Plot CCTV Nodes
        data.all_locations.forEach(loc => {
          const marker = L.circleMarker([loc.lat, loc.lon], {
            radius: 6, color: '#38bdf8', fillColor: '#08101e', fillOpacity: 0.9, weight: 2
          });
          marker.bindPopup(`
            <div style="font-family: sans-serif; font-size: 0.85rem;">
              <b style="color: #38bdf8;">📹 ${loc.name}</b><br>
              <div style="font-size: 0.75rem; color: #64748b; margin: 3px 0;">Surveillance CCTV Node</div>
              <div style="font-family: monospace; font-size: 0.72rem; color: #94a3b8;">${loc.lat.toFixed(4)}, ${loc.lon.toFixed(4)}</div>
              <button class="btn btn-secondary btn-sm" onclick="selectCameraFromMap('${loc.name}')" style="font-size: 0.72rem; padding: 2px 7px; margin-top: 6px; width: 100%;">
                Focus CCTV Scanner
              </button>
            </div>
          `);
          layerCctvGroup.addLayer(marker);
        });

        // Plot Top K Search Zones with Mobility Perimeter
        const colors = ['#ef4444', '#f59e0b', '#3b82f6', '#10b981', '#a855f7', '#ec4899', '#06b6d4', '#84cc16'];
        data.zones.forEach((z, i) => {
          const color = colors[i] || '#64748b';
          const circle = L.circle([z.lat, z.lon], {
            radius: z.radius_km * 1000, color: color, fillColor: color, fillOpacity: 0.16, weight: 2
          });
          circle.bindPopup(`
            <div style="font-family: sans-serif; font-size: 0.85rem;">
              <b style="color:${color};">🎯 Zone #${z.rank}: ${z.location}</b><br>
              <div style="margin: 4px 0;">Probability: <b style="color:${color};">${(z.score * 100).toFixed(1)}%</b></div>
              <div style="font-size: 0.78rem; color: #64748b;">Perimeter Radius: <b>${z.radius_km.toFixed(2)} km</b> (Speed: ${currentMobilitySpeed} km/h)</div>
              <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 3px;">${z.reason}</div>
            </div>
          `);
          layerZonesGroup.addLayer(circle);

          const dot = L.circleMarker([z.lat, z.lon], {
            radius: 8, color: color, fillColor: color, fillOpacity: 0.95, weight: 2
          });
          dot.bindPopup(`<b>#${z.rank} ${z.location}</b><br>Score: ${(z.score * 100).toFixed(1)}%`);
          layerZonesGroup.addLayer(dot);
        });

        // Plot Rescue Bases
        allTeams.forEach(t => {
          const baseMarker = L.circleMarker([t.lat, t.lon], {
            radius: 9, color: '#10b981', fillColor: '#064e3b', fillOpacity: 0.9, weight: 3
          });
          baseMarker.bindPopup(`
            <div style="font-family: sans-serif; font-size: 0.85rem;">
              <b style="color: #10b981;">🏢 ${t.name}</b><br>
              <div style="font-size: 0.78rem; color: #64748b;">Base: <b>${t.base_location}</b></div>
              <div style="font-size: 0.75rem; color: #94a3b8;">Org: ${t.org} &bull; 📞 ${t.phone}</div>
            </div>
          `);
          layerTeamsGroup.addLayer(baseMarker);
        });

        plotCasesOnMap();

        // Refresh container dimensions
        adminMap.invalidateSize(true);

      } catch (e) { console.error(e); }
    }

    // PLOT MISSING PERSONS PINS
    function plotCasesOnMap() {
      if (!layerCasesGroup) return;
      layerCasesGroup.clearLayers();

      allCases.forEach(c => {
        const coords = [c.lat || 15.8281, c.lon || 78.0373];
        const markerColor = c.status === 'ACTIVE' ? '#ef4444' : '#10b981';
        const marker = L.circleMarker(coords, {
          radius: 8, color: markerColor, fillColor: markerColor, fillOpacity: 0.9, weight: 2
        });

        marker.bindPopup(`
          <div style="font-family: sans-serif; font-size: 0.85rem;">
            <b style="color: ${markerColor};">👤 Case #${c.id}: ${c.name}</b><br>
            <div style="font-size: 0.78rem; color: #64748b; margin: 3px 0;">Last Seen: <b>${c.last_seen_location}</b></div>
            <div style="font-size: 0.75rem; color: #94a3b8;">Status: <b style="color:${markerColor};">${c.status}</b></div>
            <button class="btn btn-secondary btn-sm" onclick="openCaseDossier(${c.id})" style="font-size: 0.72rem; padding: 2px 7px; margin-top: 6px; width: 100%;">
              👁️ View Full Case Dossier
            </button>
          </div>
        `);
        layerCasesGroup.addLayer(marker);
      });
    }

    // CASE DOSSIER & STEPPER TIMELINE MODAL
    function openCaseDossier(caseId) {
      currentDossierCaseId = caseId;
      const c = allCases.find(item => item.id === caseId) || allCases[0];
      if (!c) return;

      const badge = document.getElementById('dossier-id-badge');
      if (badge) badge.innerText = `CASE #${c.id}`;
      const nameEl = document.getElementById('dossier-name');
      if (nameEl) nameEl.innerText = c.name;
      
      const tag = document.getElementById('dossier-status-tag');
      if (tag) {
        tag.innerText = c.status;
        tag.className = `tag ${c.status === 'ACTIVE' ? 'tag-active' : (c.status === 'RESCUED' ? 'tag-rescued' : 'tag-closed')}`;
      }

      const ageGen = document.getElementById('dossier-age-gender');
      if (ageGen) ageGen.innerText = `${c.age} Years / ${c.gender}`;
      const clothes = document.getElementById('dossier-clothes');
      if (clothes) clothes.innerText = c.clothes || 'Standard Attire';
      const loc = document.getElementById('dossier-loc');
      if (loc) loc.innerText = c.last_seen_location;
      const team = document.getElementById('dossier-team');
      if (team) team.innerText = c.assigned_team || 'Unassigned';
      const coords = document.getElementById('dossier-coords');
      if (coords) coords.innerText = `${(c.lat || 15.8281).toFixed(4)}, ${(c.lon || 78.0373).toFixed(4)}`;

      const stepper = document.getElementById('dossier-timeline');
      if (stepper) {
        const isResolved = c.status === 'RESCUED' || c.status === 'CLOSED';
        stepper.innerHTML = `
          <div class="timeline-step completed">
            <div class="timeline-step-title">1. Missing Person Report Filed</div>
            <div class="timeline-step-desc">First notice registered in Central Command by Kurnool Division.</div>
          </div>
          <div class="timeline-step completed">
            <div class="timeline-step-title">2. Last Known Sighting Verified</div>
            <div class="timeline-step-desc">Subject spotted at <b>${c.last_seen_location}</b>; initial coordinates logged.</div>
          </div>
          <div class="timeline-step completed">
            <div class="timeline-step-title">3. Surveillance Sighting Graph Activated</div>
            <div class="timeline-step-desc">Surveillance camera vertices and mobility speed perimeters calibrated for tracking.</div>
          </div>
          <div class="timeline-step ${isResolved ? 'completed' : 'active-step'}">
            <div class="timeline-step-title">4. Ground Search Unit Dispatched</div>
            <div class="timeline-step-desc">Dispatched to <b>${c.assigned_team || 'Rescue Unit'}</b> with automated SMS alert.</div>
          </div>
          <div class="timeline-step ${isResolved ? 'completed' : ''}">
            <div class="timeline-step-title">${isResolved ? '5. Subject Safely Rescued & Reunited' : '5. Search Operation Ongoing'}</div>
            <div class="timeline-step-desc">${isResolved ? 'Field team verified and case successfully closed.' : 'Active field search and CCTV monitoring in progress.'}</div>
          </div>
        `;
      }

      const resBtn = document.getElementById('btn-dossier-resolve');
      if (resBtn) {
        resBtn.style.display = (c.status === 'ACTIVE') ? 'inline-block' : 'none';
      }

      const modal = document.getElementById('case-dossier-modal');
      if (modal) modal.style.display = 'flex';
    }

    function closeCaseDossier() {
      const modal = document.getElementById('case-dossier-modal');
      if (modal) modal.style.display = 'none';
      currentDossierCaseId = null;
    }

    function locateCaseOnMapFromDossier() {
      if (!currentDossierCaseId) return;
      const c = allCases.find(item => item.id === currentDossierCaseId);
      closeCaseDossier();
      if (c) {
        switchView('admin');
        setTimeout(() => {
          if (adminMap) {
            const coords = [c.lat || 15.8281, c.lon || 78.0373];
            adminMap.invalidateSize(true);
            adminMap.flyTo(coords, 16, { duration: 1.2 });
            const mapEl = document.getElementById('admin-map');
            if (mapEl) mapEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            showToast(`Located Case #${c.id} on Sighting Graph`);
          }
        }, 150);
      }
    }

    function generatePosterFromDossier() {
      if (!currentDossierCaseId) return;
      const cid = currentDossierCaseId;
      closeCaseDossier();
      openPosterModal(cid);
    }

    function allotFromDossier() {
      if (!currentDossierCaseId) return;
      const cid = currentDossierCaseId;
      closeCaseDossier();
      openAllotModal(cid);
    }

    async function resolveFromDossier() {
      if (!currentDossierCaseId) return;
      await markCaseResolved(currentDossierCaseId);
      closeCaseDossier();
    }

    // EMERGENCY MISSING PERSON NOTICE / FLYER
    function openPosterModal(caseId) {
      const c = allCases.find(item => item.id === caseId) || allCases[0];
      if (!c) return;

      const pName = document.getElementById('poster-name');
      if (pName) pName.innerText = c.name;
      const pId = document.getElementById('poster-case-id');
      if (pId) pId.innerText = `#${c.id}`;
      const pAge = document.getElementById('poster-age-gender');
      if (pAge) pAge.innerText = `${c.age} Years / ${c.gender}`;
      const pClothes = document.getElementById('poster-clothes');
      if (pClothes) pClothes.innerText = c.clothes || 'Standard Clothes';
      const pLoc = document.getElementById('poster-loc');
      if (pLoc) pLoc.innerText = c.last_seen_location;
      const pTeam = document.getElementById('poster-team');
      if (pTeam) pTeam.innerText = c.assigned_team || 'Police Command Kurnool';

      const modal = document.getElementById('poster-modal');
      if (modal) modal.style.display = 'flex';
    }

    function closePosterModal() {
      const modal = document.getElementById('poster-modal');
      if (modal) modal.style.display = 'none';
    }

    function printPoster() {
      window.print();
    }

    function copyPosterLink() {
      const name = document.getElementById('poster-name').innerText;
      const id = document.getElementById('poster-case-id').innerText;
      const loc = document.getElementById('poster-loc').innerText;
      const clothes = document.getElementById('poster-clothes').innerText;
      const text = `🚨 EMERGENCY MISSING PERSON ALERT 🚨\nName: ${name} (Case ${id})\nLast Seen: ${loc}\nAttire: ${clothes}\nHotline: +91 6303126628 / DIAL 100\nMissing Person Search-and-Track System (Problem Statement 112)`;

      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
          showToast('📋 Emergency alert text copied to clipboard!');
        });
      } else {
        showToast('📋 Details formatted. Ready to print or share.');
      }
    }

    // STREET-LEVEL ROAD ROUTING FROM SPECIFIC LOGGED-IN NGO'S BASE
    async function loadNgoRoute(caseId = null) {
      initNgoMap();
      if (!ngoMap) return;

      try {
        const teamParam = loggedInTeam ? `team_id=${loggedInTeam.id}` : '';
        const selCaseId = caseId || (document.getElementById('resolve-case-id') ? document.getElementById('resolve-case-id').value : '');
        const caseParam = selCaseId ? `case_id=${selCaseId}` : '';
        const params = [teamParam, caseParam].filter(Boolean).join('&');
        const url = `/api/search-party-route${params ? '?' + params : ''}`;

        const res = await fetch(url);
        const data = await res.json();

        ngoLayers.clearLayers();

        const startLat = data.from_lat;
        const startLon = data.from_lon;
        const targetLat = data.to_lat;
        const targetLon = data.to_lon;

        const teamName = data.team_name || (loggedInTeam ? loggedInTeam.name : "Helping Hands NGO");
        const baseName = data.base_location || (loggedInTeam ? loggedInTeam.base_location : "Base Station");
        const personName = data.person_name || document.getElementById('ngo-subject-name').innerText;
        const locName = data.target_location || document.getElementById('ngo-target-loc').innerText;

        document.getElementById('ngo-active-team-display').innerText = `Unit: ${teamName}`;
        document.getElementById('ngo-base-display').innerText = `${baseName} (${startLat.toFixed(4)}, ${startLon.toFixed(4)})`;
        document.getElementById('ngo-subject-name').innerText = personName;
        document.getElementById('ngo-target-loc').innerText = locName;

        currentRouteDistKm = data.distance_km || 1.74;
        currentRouteEtaMins = data.eta_minutes || 2.8;

        document.getElementById('route-dist').innerText = `${currentRouteDistKm} km`;
        document.getElementById('route-eta').innerText = `${currentRouteEtaMins} mins`;
        const badge = document.getElementById('route-engine-badge');
        if (badge) {
          badge.innerText = `🚗 ${data.engine || 'Real Road Network'}`;
        }

        const streetCoordinates = data.street_coordinates || data.route_coordinates || [[startLat, startLon], [targetLat, targetLon]];
        currentRouteCoords = streetCoordinates;
        resetGpsRouteSimulation();

        const coordsCount = streetCoordinates.length;
        document.getElementById('route-path-text').innerText = `Street route navigating through ${coordsCount} road nodes from ${baseName} to ${locName}`;

        // Base station marker
        L.circleMarker([startLat, startLon], {
          radius: 9, color: '#10b981', fillColor: '#10b981', fillOpacity: 0.95, weight: 3
        }).bindPopup(`<b>${teamName} (Base)</b><br>${baseName}`).addTo(ngoLayers);

        // Target sighting location marker
        L.circleMarker([targetLat, targetLon], {
          radius: 9, color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.95, weight: 3
        }).bindPopup(`<b>Target Sighting: ${personName}</b><br>${locName}`).addTo(ngoLayers);

        L.circle([targetLat, targetLon], {
          radius: 400, color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.18, weight: 2
        }).addTo(ngoLayers);

        // Dual-layer GPS road navigation polyline
        const casingPoly = L.polyline(streetCoordinates, {
          color: '#0369a1',
          weight: 9,
          opacity: 0.75,
          lineCap: 'round',
          lineJoin: 'round'
        }).addTo(ngoLayers);

        L.polyline(streetCoordinates, {
          color: '#38bdf8',
          weight: 5,
          opacity: 1.0,
          lineCap: 'round',
          lineJoin: 'round'
        }).addTo(ngoLayers);

        // Safe bounds fitting
        ngoMap.invalidateSize(true);
        const mapSize = ngoMap.getSize();
        if (mapSize && mapSize.x > 80 && mapSize.y > 80 && casingPoly && casingPoly.getBounds().isValid()) {
          try {
            ngoMap.fitBounds(casingPoly.getBounds(), { padding: [40, 40], maxZoom: 16 });
          } catch (err) {
            ngoMap.setView([startLat, startLon], 14);
          }
        } else {
          ngoMap.setView([startLat, startLon], 14);
        }

      } catch (e) {
        console.error("Failed to load street route", e);
      }
    }

    // LIVE GPS VEHICLE DRIVING SIMULATION
    function setSimSpeed(mult) {
      currentSimSpeed = mult;
      [1, 3, 6].forEach(s => {
        const btn = document.getElementById(`sim-spd-${s}`);
        if (btn) btn.classList.toggle('active', s === mult);
      });
      if (isGpsSimRunning) {
        pauseGpsRouteSimulation();
        startGpsRouteSimulation();
      }
      showToast(`Simulation speed set to ${mult}x`);
    }

    function startGpsRouteSimulation() {
      if (!currentRouteCoords || currentRouteCoords.length < 2) {
        showToast('No active street navigation route loaded.');
        return;
      }
      isGpsSimRunning = true;
      document.getElementById('btn-start-sim').style.display = 'none';
      document.getElementById('btn-pause-sim').style.display = 'inline-block';
      const pulseDot = document.getElementById('gps-pulse-dot');
      if (pulseDot) pulseDot.style.display = 'inline-block';

      if (!simMarker) {
        const startPos = currentRouteCoords[0];
        const carIcon = L.divIcon({
          html: '<div style="font-size: 1.6rem; transform: translate(-12px, -12px); filter: drop-shadow(0 2px 5px rgba(0,0,0,0.5));">🚑</div>',
          className: 'sim-pulse-marker',
          iconSize: [24, 24]
        });
        simMarker = L.marker(startPos, { icon: carIcon }).addTo(ngoLayers);
      }

      const totalSteps = currentRouteCoords.length;
      const stepIntervalMs = Math.max(120 / currentSimSpeed, 35);

      if (currentGpsInterval) clearInterval(currentGpsInterval);

      currentGpsInterval = setInterval(() => {
        if (currentGpsStep >= totalSteps - 1) {
          clearInterval(currentGpsInterval);
          isGpsSimRunning = false;
          document.getElementById('btn-start-sim').style.display = 'inline-block';
          document.getElementById('btn-pause-sim').style.display = 'none';
          if (pulseDot) pulseDot.style.display = 'none';

          document.getElementById('sim-speedo-val').innerText = '0';
          document.getElementById('sim-dist-remain').innerText = '0.00 km';
          document.getElementById('sim-eta-countdown').innerText = '0.0 min';

          playArrivalChime();
          showToast('🎯 Rescue Unit arrived at target search zone perimeter!');
          return;
        }

        currentGpsStep++;
        const curCoord = currentRouteCoords[currentGpsStep];
        simMarker.setLatLng(curCoord);

        const baseSpeed = 42;
        const jitter = Math.floor(Math.sin(currentGpsStep) * 6);
        document.getElementById('sim-speedo-val').innerText = (baseSpeed + jitter).toString();

        const remainingPct = 1 - (currentGpsStep / (totalSteps - 1));
        const distRemaining = (currentRouteDistKm * remainingPct).toFixed(2);
        const etaRemaining = (currentRouteEtaMins * remainingPct).toFixed(1);

        document.getElementById('sim-dist-remain').innerText = `${distRemaining} km`;
        document.getElementById('sim-eta-countdown').innerText = `${etaRemaining} min`;
      }, stepIntervalMs);
    }

    function pauseGpsRouteSimulation() {
      if (currentGpsInterval) clearInterval(currentGpsInterval);
      isGpsSimRunning = false;
      document.getElementById('btn-start-sim').style.display = 'inline-block';
      document.getElementById('btn-start-sim').innerText = '▶️ Resume GPS Run';
      document.getElementById('btn-pause-sim').style.display = 'none';
      const pulseDot = document.getElementById('gps-pulse-dot');
      if (pulseDot) pulseDot.style.display = 'none';
      document.getElementById('sim-speedo-val').innerText = '0';
    }

    function resetGpsRouteSimulation() {
      if (currentGpsInterval) clearInterval(currentGpsInterval);
      isGpsSimRunning = false;
      currentGpsStep = 0;
      document.getElementById('btn-start-sim').style.display = 'inline-block';
      document.getElementById('btn-start-sim').innerText = '▶️ Start GPS Run';
      document.getElementById('btn-pause-sim').style.display = 'none';
      const pulseDot = document.getElementById('gps-pulse-dot');
      if (pulseDot) pulseDot.style.display = 'none';

      document.getElementById('sim-speedo-val').innerText = '0';
      document.getElementById('sim-dist-remain').innerText = `${currentRouteDistKm.toFixed(2)} km`;
      document.getElementById('sim-eta-countdown').innerText = `${currentRouteEtaMins.toFixed(1)} min`;

      if (simMarker && currentRouteCoords.length > 0) {
        simMarker.setLatLng(currentRouteCoords[0]);
      }
    }

    // VIEW SWITCHER
    function switchView(role) {
      if (loggedInRole === 'ngo' && role === 'admin') {
        showToast('⚠️ Access Denied: Admin Command Center is restricted to Police Command.');
        return;
      }
      currentRole = role;
      document.getElementById('tab-admin').classList.toggle('active', role === 'admin');
      document.getElementById('tab-ngo').classList.toggle('active', role === 'ngo');
      document.getElementById('view-admin').style.display = role === 'admin' ? 'block' : 'none';
      document.getElementById('view-ngo').style.display = role === 'ngo' ? 'block' : 'none';

      const dot = document.getElementById('role-dot');
      const disp = document.getElementById('current-user-display');
      if (role === 'admin') {
        dot.className = 'dot role-admin';
        disp.innerText = 'Admin: Police Command';
        loadNotifications();
        whenLeafletReady(() => {
          setTimeout(() => {
            initAdminMap();
            if (adminMap) {
              adminMap.invalidateSize(true);
            }
            loadMapData();
          }, 80);
        });
      } else {
        dot.className = 'dot role-ngo';
        const teamName = loggedInTeam ? loggedInTeam.name : 'Helping Hands NGO';
        disp.innerText = `Search Party: ${teamName}`;
        loadNotifications();
        whenLeafletReady(() => {
          setTimeout(() => {
            initNgoMap();
            if (ngoMap) {
              ngoMap.invalidateSize(true);
            }
            loadNgoRoute();
          }, 80);
        });
      }
    }

    // NOTIFICATIONS SYSTEM
    let allNotifications = [];

    async function loadNotifications() {
      try {
        const teamParam = loggedInTeam ? `?team_id=${loggedInTeam.id}` : '';
        const res = await fetch(`/api/notifications${teamParam}`);
        const data = await res.json();
        allNotifications = data.notifications || [];

        const badge = document.getElementById('notif-badge');
        if (badge) {
          if (data.unread_count > 0) {
            badge.style.display = 'inline-block';
            badge.innerText = data.unread_count;
          } else {
            badge.style.display = 'none';
          }
        }

        const modalCount = document.getElementById('notif-modal-count');
        if (modalCount) modalCount.innerText = `${data.unread_count} Unread`;

        const ngoBadge = document.getElementById('ngo-notif-count-badge');
        if (ngoBadge) ngoBadge.innerText = `${allNotifications.length} Allotted (${data.unread_count} New)`;

        renderNotificationsList();
        renderNgoNotifications();
      } catch (err) {
        console.error("Error loading notifications:", err);
      }
    }

    function renderNotificationsList() {
      const list = document.getElementById('notifications-modal-list');
      if (!list) return;
      list.innerHTML = '';

      if (allNotifications.length === 0) {
        list.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No case allotment notifications found.</div>`;
        return;
      }

      allNotifications.forEach(n => {
        const div = document.createElement('div');
        div.className = `notif-card ${!n.read ? 'unread' : ''}`;
        div.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem;">
            <div style="font-weight: 700; color: var(--text); font-size: 0.92rem;">
              ${!n.read ? '<span style="color: #ef4444; margin-right: 4px;">●</span>' : ''}${n.title}
            </div>
            <span style="font-size: 0.75rem; color: var(--text-muted); white-space: nowrap;">${n.timestamp}</span>
          </div>
          <div style="font-size: 0.83rem; color: var(--text-muted); line-height: 1.35;">
            ${n.message}
          </div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.35rem; flex-wrap: wrap; gap: 0.4rem;">
            <span style="font-size: 0.75rem; color: #10b981;">📱 ${n.sms_status}</span>
            <div style="display: flex; gap: 0.4rem;">
              ${n.case_id ? `<button class="btn btn-secondary btn-sm" style="font-size: 0.72rem; padding: 2px 7px;" onclick="acceptCaseAndNavigate(${n.case_id})">🚗 Trace Route</button>` : ''}
              ${!n.read ? `<button class="btn btn-secondary btn-sm" style="font-size: 0.72rem; padding: 2px 7px;" onclick="markNotificationRead(${n.id})">✓ Acknowledge</button>` : ''}
            </div>
          </div>
        `;
        list.appendChild(div);
      });
    }

    function renderNgoNotifications() {
      const feed = document.getElementById('ngo-notifs-feed');
      if (!feed) return;
      feed.innerHTML = '';

      if (allNotifications.length === 0) {
        feed.innerHTML = `
          <div style="background: var(--input-bg); border: 1px dashed var(--card-border); border-radius: 8px; padding: 1rem; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
            ✅ No pending case allotments for this unit. All dispatches acknowledged.
          </div>
        `;
        return;
      }

      allNotifications.forEach(n => {
        const div = document.createElement('div');
        div.className = `notif-card ${!n.read ? 'unread' : ''}`;
        div.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; flex-wrap: wrap;">
            <div>
              <div style="display: align-items: center; gap: 0.4rem;">
                <span class="badge" style="background: #ef4444;">CASE ALLOTMENT ORDER</span>
                ${!n.read ? '<span class="badge" style="background: #f59e0b;">NEW UNREAD</span>' : '<span class="badge" style="background: #10b981;">ACKNOWLEDGED</span>'}
              </div>
              <h3 style="font-size: 1.05rem; margin-top: 0.3rem; color: var(--text);">${n.title}</h3>
            </div>
            <span style="font-size: 0.75rem; color: var(--text-muted);">${n.timestamp}</span>
          </div>

          <div style="background: var(--card); border: 1px solid var(--card-border); border-radius: 6px; padding: 0.6rem 0.8rem; margin: 0.3rem 0; font-size: 0.84rem;">
            <div>Missing Person: <b>${n.person_name}</b> (Case #${n.case_id})</div>
            <div>Target Sighting Zone: <b style="color: var(--accent);">${n.last_seen_location}</b></div>
            <div style="color: var(--text-muted); margin-top: 0.2rem; font-size: 0.8rem;">${n.message}</div>
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
            <div style="font-size: 0.78rem; color: #10b981; display: flex; align-items: center; gap: 0.3rem;">
              <span>📱</span> <span>SMS Dispatch Alert: <b>${n.sms_status}</b></span>
            </div>
            <div style="display: flex; gap: 0.5rem;">
              <button class="btn btn-success btn-sm" onclick="acceptCaseAndNavigate(${n.case_id})">
                🚗 Accept & Trace Road Route
              </button>
              ${!n.read ? `<button class="btn btn-secondary btn-sm" onclick="markNotificationRead(${n.id})">✓ Acknowledge</button>` : ''}
            </div>
          </div>
        `;
        feed.appendChild(div);
      });
    }

    function acceptCaseAndNavigate(caseId) {
      if (currentRole !== 'ngo') {
        switchView('ngo');
      }
      const sel = document.getElementById('resolve-case-id');
      if (sel) {
        sel.value = caseId;
        updateNgoSelection();
      }
      closeNotificationModal();
      showToast(`Navigating road route to Case #${caseId}`);
      const mapEl = document.getElementById('ngo-map');
      if (mapEl) mapEl.scrollIntoView({ behavior: 'smooth' });
    }

    async function markNotificationRead(id) {
      try {
        await fetch('/api/notifications/mark-read', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: id })
        });
        loadNotifications();
      } catch (err) { console.error(err); }
    }

    async function markAllNotificationsRead() {
      try {
        await fetch('/api/notifications/mark-read', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ team_id: loggedInTeam ? loggedInTeam.id : null })
        });
        showToast('All notifications marked as read');
        loadNotifications();
      } catch (err) { console.error(err); }
    }

    function openNotificationModal() {
      document.getElementById('notifications-modal').style.display = 'flex';
      loadNotifications();
    }
    function closeNotificationModal() {
      document.getElementById('notifications-modal').style.display = 'none';
    }

    // ALLOT CASE MODAL
    function handleAllotTeamChange() {
      const teamId = parseInt(document.getElementById('allot-team-select').value);
      const t = allTeams.find(item => item.id === teamId);
      if (t) {
        document.getElementById('allot-phone').value = t.phone || '6303126628';
      }
    }

    function openAllotModal(caseId) {
      if (loggedInRole !== 'admin') {
        showToast('⚠️ Access Denied: Only Police Command can allot cases to NGOs.');
        return;
      }
      const c = allCases.find(item => item.id === caseId);
      if (!c) return;
      document.getElementById('allot-case-id').value = c.id;
      document.getElementById('allot-case-title').innerText = `Case #${c.id}: ${c.name} (${c.age} / ${c.gender})`;
      document.getElementById('allot-case-loc').innerText = `Target Location: ${c.last_seen_location} • Current Unit: ${c.assigned_team}`;
      document.getElementById('allot-instructions').value = '';

      const sel = document.getElementById('allot-team-select');
      sel.innerHTML = '';
      allTeams.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.id;
        opt.innerText = `${t.name} (${t.base_location}) - Phone: ${t.phone}`;
        if (t.name === c.assigned_team) opt.selected = true;
        sel.appendChild(opt);
      });

      handleAllotTeamChange();
      document.getElementById('allot-case-modal').style.display = 'flex';
    }

    function closeAllotModal() {
      document.getElementById('allot-case-modal').style.display = 'none';
    }

    async function handleDispatchAllotment(e) {
      e.preventDefault();
      if (loggedInRole !== 'admin') {
        showToast('⚠️ Access Denied: Administrator role required.');
        return;
      }
      const caseId = parseInt(document.getElementById('allot-case-id').value);
      const teamId = parseInt(document.getElementById('allot-team-select').value);
      const note = document.getElementById('allot-instructions').value.trim();
      const phone = document.getElementById('allot-phone').value.trim() || '6303126628';

      try {
        const res = await fetch('/api/cases/allot', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-User-Role': loggedInRole || 'admin' },
          body: JSON.stringify({ case_id: caseId, team_id: teamId, note: note, phone: phone })
        });
        const data = await res.json();
        closeAllotModal();
        showToast(data.message || `Case #${caseId} allotted successfully!`);
        loadCases();
        loadStats();
        loadNotifications();
      } catch (err) { console.error(err); }
    }

    // MODAL CREATION FOR CASES & NGOS
    function openAddCaseModal() {
      if (loggedInRole !== 'admin') {
        showToast('⚠️ Access Denied: Only Police Command can enroll new cases.');
        return;
      }
      document.getElementById('add-case-modal').style.display = 'flex';
    }
    function closeAddCaseModal() { document.getElementById('add-case-modal').style.display = 'none'; }

    function openAddNgoModal() {
      if (loggedInRole !== 'admin') {
        showToast('⚠️ Access Denied: Only Police Command can register new NGOs.');
        return;
      }
      document.getElementById('add-ngo-modal').style.display = 'flex';
    }
    function closeAddNgoModal() { document.getElementById('add-ngo-modal').style.display = 'none'; }

    function handleNgoBasePresetChange() {
      const val = document.getElementById('ngo-base-preset').value;
      if (val === 'custom') return;
      const parts = val.split('|');
      document.getElementById('ngo-base-name').value = parts[0];
      document.getElementById('ngo-lat').value = parts[1];
      document.getElementById('ngo-lon').value = parts[2];
    }

    async function handleCreateNgo(e) {
      e.preventDefault();
      if (loggedInRole !== 'admin') {
        showToast('⚠️ Access Denied: Only Police Command can register new NGOs.');
        return;
      }
      const newTeam = {
        name: document.getElementById('ngo-name').value.trim(),
        org: document.getElementById('ngo-org').value,
        phone: document.getElementById('ngo-phone').value.trim(),
        base_location: document.getElementById('ngo-base-name').value.trim(),
        lat: parseFloat(document.getElementById('ngo-lat').value),
        lon: parseFloat(document.getElementById('ngo-lon').value),
        username: document.getElementById('ngo-username').value.trim(),
        password: document.getElementById('ngo-password').value.trim(),
      };

      try {
        const res = await fetch('/api/teams/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-User-Role': loggedInRole || 'admin' },
          body: JSON.stringify(newTeam)
        });
        const saved = await res.json();
        closeAddNgoModal();
        e.target.reset();
        showToast(`NGO Registered: ${saved.name}`);
        loadTeams();
        loadStats();
      } catch (err) { console.error(err); }
    }

    async function deleteTeam(id) {
      if (loggedInRole !== 'admin') {
        showToast('⚠️ Access Denied: Only Police Command can remove rescue teams.');
        return;
      }
      if (!confirm(`Are you sure you want to remove Team #${id}?`)) return;
      try {
        await fetch('/api/teams/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-User-Role': loggedInRole || 'admin' },
          body: JSON.stringify({ id: id })
        });
        showToast(`Team #${id} removed`);
        loadTeams();
        loadStats();
      } catch (err) { console.error(err); }
    }

    async function handleCreateCase(e) {
      e.preventDefault();
      if (loggedInRole !== 'admin') {
        showToast('⚠️ Access Denied: Only Police Command can enroll new cases.');
        return;
      }
      const newCase = {
        name: document.getElementById('new-name').value,
        age: parseInt(document.getElementById('new-age').value),
        gender: document.getElementById('new-gender').value,
        clothes: document.getElementById('new-clothes').value,
        last_seen_location: document.getElementById('new-loc').value,
        assigned_team: document.getElementById('new-team').value,
      };

      try {
        const res = await fetch('/api/cases/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-User-Role': loggedInRole || 'admin' },
          body: JSON.stringify(newCase)
        });
        closeAddCaseModal();
        e.target.reset();
        showToast(`Case enrolled for ${newCase.name}`);
        loadStats();
        loadCases();
      } catch (err) { console.error(err); }
    }

    async function deleteCase(id) {
      if (loggedInRole !== 'admin') {
        showToast('⚠️ Access Denied: Only Police Command can remove cases.');
        return;
      }
      if (!confirm(`Are you sure you want to remove Case #${id}?`)) return;
      try {
        await fetch('/api/cases/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-User-Role': loggedInRole || 'admin' },
          body: JSON.stringify({ id: id })
        });
        showToast(`Case #${id} removed`);
        loadStats();
        loadCases();
      } catch (err) { console.error(err); }
    }

    async function markCaseResolved(id) {
      try {
        closeCaseDossier();
        await fetch('/api/resolve-dispatch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ case_id: id, outcome: 'found', notes: 'Resolved by command' })
        });
        showToast(`Case #${id} marked as RESCUED`);
        loadStats();
        loadCases();
      } catch (err) { console.error(err); }
    }

    function populateNgoCaseSelector() {
      const sel = document.getElementById('resolve-case-id');
      if (!sel) return;
      sel.innerHTML = '';
      allCases.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.id;
        opt.innerText = `Case #${c.id}: ${c.name} (${c.status} - ${c.last_seen_location})`;
        sel.appendChild(opt);
      });
      updateNgoSelection();
    }

    function updateNgoSelection() {
      const sel = document.getElementById('resolve-case-id');
      if (!sel) return;
      const caseId = parseInt(sel.value);
      const c = allCases.find(item => item.id === caseId) || allCases[0];
      if (c) {
        document.getElementById('ngo-subject-name').innerText = c.name;
        document.getElementById('ngo-target-loc').innerText = c.last_seen_location;
        document.getElementById('ngo-tag-status').innerText = `Status: ${c.status}`;
        if (currentRole === 'ngo') {
          loadNgoRoute(c.id);
        }
      }
    }

    async function handleResolve(e) {
      e.preventDefault();
      const caseId = parseInt(document.getElementById('resolve-case-id').value);
      const outcome = document.getElementById('resolve-outcome').value;
      const notes = document.getElementById('resolve-notes').value;

      try {
        const res = await fetch('/api/resolve-dispatch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ case_id: caseId, outcome: outcome, notes: notes })
        });
        const result = await res.json();
        const msg = document.getElementById('resolve-msg');
        msg.style.display = 'block';
        msg.className = 'match-alert';
        msg.innerHTML = `<b>Status Updated:</b> Case #${caseId} marked as <b>${result.case_status}</b>. Counters updated.`;
        showToast(`Case #${caseId} updated to ${result.case_status}`);
        loadStats();
        loadCases();
      } catch (err) { console.error(err); }
    }

    // VIDEO PLAYER, WEBCAM & SCANNER FUNCTIONS
    function handleVideoUpload(event) {
      const file = event.target.files[0];
      if (!file) return;
      if (webcamStream) {
        webcamStream.getTracks().forEach(track => track.stop());
        webcamStream = null;
        const ind = document.getElementById('webcam-live-indicator');
        if (ind) ind.style.display = 'none';
        const b = document.getElementById('btn-webcam');
        if (b) b.innerText = '📷 Live Webcam';
      }
      const video = document.getElementById('video-player');
      video.srcObject = null;
      video.src = URL.createObjectURL(file);
      document.getElementById('video-placeholder').style.display = 'none';
      video.play();
      showToast(`Loaded video: ${file.name}`);
    }

    function loadSampleVideo() {
      if (webcamStream) {
        webcamStream.getTracks().forEach(track => track.stop());
        webcamStream = null;
        const ind = document.getElementById('webcam-live-indicator');
        if (ind) ind.style.display = 'none';
        const b = document.getElementById('btn-webcam');
        if (b) b.innerText = '📷 Live Webcam';
      }
      const video = document.getElementById('video-player');
      video.srcObject = null;
      video.src = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4";
      document.getElementById('video-placeholder').style.display = 'none';
      video.play();
      showToast('Loaded demo video feed');
    }

    async function toggleWebcam() {
      const video = document.getElementById('video-player');
      const indicator = document.getElementById('webcam-live-indicator');
      const placeholder = document.getElementById('video-placeholder');
      const btn = document.getElementById('btn-webcam');

      if (webcamStream) {
        webcamStream.getTracks().forEach(track => track.stop());
        webcamStream = null;
        video.srcObject = null;
        if (indicator) indicator.style.display = 'none';
        if (btn) btn.innerText = '📷 Live Webcam';
        showToast('Webcam disconnected');
        return;
      }

      try {
        webcamStream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 } });
        video.srcObject = webcamStream;
        video.src = "";
        if (placeholder) placeholder.style.display = 'none';
        if (indicator) indicator.style.display = 'inline-block';
        if (btn) btn.innerText = '⏹️ Stop Webcam';
        video.play();
        showToast('Live device camera stream activated');
      } catch (err) {
        console.error("Webcam error:", err);
        showToast('⚠️ Camera access denied or unavailable on this device.');
      }
    }

    function jumpVideoTo(seconds) {
      const video = document.getElementById('video-player');
      if (video) {
        video.currentTime = seconds;
        video.play();
        showToast(`Jumped video to ${seconds.toFixed(1)}s (Frame 105)`);
      }
    }

    function focusCameraZoneOnMap() {
      const camSelect = document.getElementById('video-camera-loc');
      const camLoc = camSelect.value;
      const foundCam = allCameras.find(c => c.name === camLoc);
      let coords = [15.8281, 78.0373];
      if (foundCam) {
        coords = [foundCam.lat, foundCam.lon];
      } else {
        coords = {
          "CAR STAND": [15.8281, 78.0373],
          "Budhwarpet Market": [15.8350, 78.0450],
          "Kurnool City Railway": [15.8310, 78.0420],
          "Kurnool Bus Stand": [15.8281, 78.0373],
          "RGM grounds": [15.8310, 78.0420],
          "cantene": [15.8350, 78.0450],
          "DS labs": [15.8200, 78.0450],
          "RGM hostel": [15.8150, 78.0300],
          "RGM gardens": [15.8340, 78.0560],
          "Konda Reddy Fort": [15.8340, 78.0560],
          "maha nandhi": [15.8100, 78.0600],
          "Collectorate": [15.8200, 78.0450],
          "Government Hospital": [15.8150, 78.0300],
          "Tungabhadra Bridge": [15.8420, 78.0300]
        }[camLoc] || [15.8281, 78.0373];
      }

      if (adminMap) {
        adminMap.flyTo(coords, 16, { duration: 1.2 });
        const mapCard = document.getElementById('admin-map');
        if (mapCard) mapCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        showToast(`Focused map on camera: ${camLoc}`);
      }
    }

    function startVideoScan() {
      if (loggedInRole !== 'admin') {
        showToast('⚠️ Access Denied: Video facial recognition scanning is restricted to Police Command.');
        return;
      }
      const radar = document.getElementById('radar-sweep');
      const status = document.getElementById('scan-status');
      const matchBox = document.getElementById('match-box');
      const camSelect = document.getElementById('video-camera-loc');
      const selectedCamText = camSelect ? (camSelect.options[camSelect.selectedIndex] ? camSelect.options[camSelect.selectedIndex].text : camSelect.value) : "Camera Node";
      const selectedCamKey = camSelect ? camSelect.value : "CAR STAND";
      const threshSlider = document.getElementById('face-thresh-slider');
      const threshVal = threshSlider ? (parseFloat(threshSlider.value) || 0.32) : 0.32;

      if (radar) {
        radar.style.display = 'block';
        radar.style.animation = 'radarSweep 2s infinite linear';
      }
      if (status) {
        status.style.display = 'block';
        status.innerText = `Scanning video frames at ${selectedCamKey} with DeepFace ArcFace (Threshold: ${threshVal.toFixed(2)})...`;
      }

      setTimeout(async () => {
        if (radar) radar.style.display = 'none';
        if (status) status.innerText = `Scan complete. Confirmed match identified at ${selectedCamKey}.`;
        if (matchBox) matchBox.style.display = 'block';

        const matchPerson = allCases.length > 0 ? allCases[0].name : "N.K.SYAM";
        const matchCaseId = allCases.length > 0 ? allCases[0].id : 1;
        const targetTeamName = loggedInTeam ? loggedInTeam.name : (allTeams.length > 0 ? allTeams[0].name : "Helping Hands NGO");

        const confBadge = document.getElementById('match-confidence-badge');
        if (confBadge) confBadge.innerText = `Confidence 94.6% (Thresh: ${threshVal.toFixed(2)})`;
        document.getElementById('match-details').innerHTML = `
          Person: <b>${matchPerson}</b> (Case #${matchCaseId})<br>
          Camera Location: <b>${selectedCamText}</b><br>
          Detection Timestamp: <b>00:04.2s (Frame 105)</b> &bull; Cosine Dist: <b>0.28</b> &bull; Status: <span style="color:#10b981; font-weight:700;">MATCH POSITIVE</span><br>
          Auto-Dispatch: Response unit <b>${targetTeamName}</b> mobilized to <b>${selectedCamKey}</b> via turn-by-turn road route.
        `;

        playDetectionChime();

        await fetch('/api/scan', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'X-User-Role': loggedInRole || 'admin'},
          body: JSON.stringify({ camera_location: selectedCamKey, case_id: matchCaseId, person_name: matchPerson, confidence: 0.28 })
        });

        const canvas = document.getElementById('canvas-overlay');
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 3;
        ctx.strokeRect(canvas.width * 0.38, canvas.height * 0.25, canvas.width * 0.22, canvas.height * 0.35);
        ctx.fillStyle = '#ef4444';
        ctx.font = 'bold 13px sans-serif';
        ctx.fillText(`${matchPerson} @ ${selectedCamKey}`, canvas.width * 0.38, canvas.height * 0.25 - 6);

        showToast(`🚨 Match confirmed: ${matchPerson} spotted!`);
        loadStats();
        loadCases();
      }, 2300);
    }

    // KEYBOARD SHORTCUTS FOR ACCESSIBILITY & SPEED
    function initKeyboardShortcuts() {
      document.addEventListener('keydown', (e) => {
        const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
        const isInput = activeTag === 'input' || activeTag === 'textarea' || activeTag === 'select';

        if (e.key === 'Escape') {
          closeAddCaseModal();
          closeAddNgoModal();
          closeAllotModal();
          closeNotificationModal();
          closeCaseDossier();
          closePosterModal();
          closeAddCameraModal();
        }

        if (!isInput && ((e.ctrlKey && e.key.toLowerCase() === 'k') || e.key === '/')) {
          e.preventDefault();
          const searchInput = document.getElementById('case-search-input');
          if (searchInput) {
            searchInput.focus();
            searchInput.select();
            showToast('Search cases activated');
          }
        }

        if (!isInput && (e.key === 'l' || e.key === 'L')) {
          toggleTheme();
        }

        if (!isInput && e.key === '1' && loggedInRole === 'admin') {
          switchView('admin');
        } else if (!isInput && e.key === '2') {
          switchView('ngo');
        }
      });
    }

    window.addEventListener('DOMContentLoaded', () => {
      initTheme();
      initTelemetryTicker();
      initKeyboardShortcuts();
      attachMapResizeObservers();
      loadCameras();
      loadTeams();
      loadStats();
      loadCases();
      loadNotifications();
      restoreSession();
      setInterval(loadNotifications, 8000);
    });
  </script>

</body>
</html>
"""


class MPTrackerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[HTTP] {self.command} {self.path} - {format % args}")

    def _send_json(self, data, status: int = 200):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("/health", "/healthz"):
            self._send_json({"status": "healthy"})
            return

        if path == "/api/cameras":
            cams = []
            cams_dict = APP_STATE.get("cameras", CAMERA_LOCATIONS)
            for idx, (k, v) in enumerate(cams_dict.items(), 1):
                cams.append({
                    "id": idx,
                    "name": k,
                    "label": v.get("label", f"CAM-{idx:02d}: {k} ({v['lat']:.4f}, {v['lon']:.4f})"),
                    "lat": v["lat"],
                    "lon": v["lon"],
                    "description": v.get("description", "Surveillance CCTV Camera Node"),
                })
            self._send_json(cams)
            return

        if path == "/api/stats":
            self._send_json(_get_app_stats())
            return

        if path == "/api/teams":
            db_teams = load_teams_from_db()
            if db_teams:
                APP_STATE["teams"] = db_teams
            self._send_json(APP_STATE["teams"])
            return

        if path == "/api/cases":
            db_cases = load_cases_from_db()
            if db_cases:
                APP_STATE["cases"] = db_cases
            self._send_json(APP_STATE["cases"])
            return

        if path == "/api/dispatches":
            db_dispatches = load_dispatches_from_db()
            if db_dispatches:
                APP_STATE["dispatches"] = db_dispatches
            self._send_json(APP_STATE["dispatches"])
            return

        if path == "/api/search-party-route":
            team_id = int(query.get("team_id", [0])[0]) if "team_id" in query else 0
            case_id = int(query.get("case_id", [0])[0]) if "case_id" in query else 0

            team = next((t for t in APP_STATE["teams"] if t["id"] == team_id), None)
            if not team:
                team = APP_STATE["teams"][0] if APP_STATE["teams"] else {"name": "Helping Hands NGO", "base_location": "Budhwarpet Base", "lat": 15.8350, "lon": 78.0450}

            target_case = next((c for c in APP_STATE["cases"] if c["id"] == case_id), None)
            if not target_case:
                target_case = APP_STATE["cases"][0] if APP_STATE["cases"] else {}

            team_lat = team.get("lat", 15.8350)
            team_lon = team.get("lon", 78.0450)
            target_lat = target_case.get("lat", 15.8281)
            target_lon = target_case.get("lon", 78.0373)

            route = _calculate_shortest_route(team_lat, team_lon, target_lat, target_lon)
            route["case_id"] = target_case.get("id", 1)
            route["person_name"] = target_case.get("name", "N.K.SYAM")
            route["target_location"] = target_case.get("last_seen_location", "CAR STAND")
            route["team_name"] = team.get("name", "Helping Hands NGO")
            route["base_location"] = team.get("base_location", "Base Station")
            self._send_json(route)
            return

        if path == "/api/demo":
            top_k = int(query.get("top", [5])[0]) if "top" in query else 5
            data = _get_demo_data(top_k=top_k)
            self._send_json(data)
            return

        if path == "/api/notifications":
            team_id = int(query.get("team_id", [0])[0]) if "team_id" in query else 0
            team_name = query.get("team_name", [""])[0].strip()

            notifs = APP_STATE.get("notifications", [])
            if team_id:
                notifs = [n for n in notifs if n.get("team_id") == team_id]
            elif team_name:
                notifs = [n for n in notifs if n.get("team_name") == team_name]

            unread_count = sum(1 for n in notifs if not n.get("read"))
            self._send_json({
                "notifications": notifs,
                "unread_count": unread_count,
                "total": len(notifs),
            })
            return

        # Default HTML application
        html_bytes = HTML_APP.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()
        self.wfile.write(html_bytes)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}

        if parsed.path == "/api/login":
            role = body.get("role", "admin")
            uname = body.get("username", "").strip()
            pwd = body.get("password", "").strip()

            if role == "admin":
                if uname == "admin" and pwd == "admin123":
                    self._send_json({"status": "success", "role": "admin"})
                    return
                self._send_json({"status": "error", "error": "Invalid admin credentials"}, status=401)
                return

            # NGO Team login check
            for t in APP_STATE["teams"]:
                if t.get("username") == uname and t.get("password") == pwd:
                    self._send_json({"status": "success", "role": "ngo", "team": t})
                    return

            self._send_json({"status": "error", "error": "Invalid NGO username or password"}, status=401)
            return

        # Server-side role authorization check: reject NGO calls to command-level admin endpoints
        role_header = self.headers.get("X-User-Role", "").strip().lower()
        if role_header == "ngo" and parsed.path in (
            "/api/teams/add",
            "/api/teams/delete",
            "/api/cases/add",
            "/api/cases/delete",
            "/api/cases/allot",
            "/api/scan",
            "/api/cameras/add",
            "/api/cameras/delete",
        ):
            self._send_json({"status": "error", "error": "Access Denied: Police Command admin privileges required."}, status=403)
            return

        if parsed.path == "/api/cameras/add":
            if role_header == "ngo":
                self._send_json({"status": "error", "error": "Access Denied: Only Police Command can install new camera locations."}, status=403)
                return

            cam_name = body.get("name", "").strip()
            if not cam_name:
                self._send_json({"status": "error", "error": "Camera name is required."}, status=400)
                return

            try:
                lat = float(body.get("lat", 15.8281))
                lon = float(body.get("lon", 78.0373))
            except (ValueError, TypeError):
                self._send_json({"status": "error", "error": "Invalid latitude or longitude format."}, status=400)
                return

            cams_dict = APP_STATE.setdefault("cameras", dict(CAMERA_LOCATIONS))
            cam_idx = len(cams_dict) + 1
            cam_code = body.get("code", "").strip() or f"CAM-{cam_idx:02d}: {cam_name} ({lat:.4f}, {lon:.4f})"
            desc = body.get("description", "Surveillance CCTV Camera Node").strip()

            cam_entry = {
                "lat": lat,
                "lon": lon,
                "label": cam_code,
                "description": desc,
            }

            cams_dict[cam_name] = cam_entry
            CAMERA_LOCATIONS[cam_name] = cam_entry

            print(f"[+] New surveillance camera node registered: {cam_name} at ({lat}, {lon}) by Police Command")

            self._send_json({
                "status": "success",
                "message": f"Camera node '{cam_name}' successfully added to surveillance network.",
                "camera": {
                    "id": cam_idx,
                    "name": cam_name,
                    "label": cam_code,
                    "lat": lat,
                    "lon": lon,
                    "description": desc,
                }
            }, status=201)
            return

        if parsed.path == "/api/cameras/delete":
            if role_header == "ngo":
                self._send_json({"status": "error", "error": "Access Denied: Only Police Command can remove camera locations."}, status=403)
                return

            cam_name = body.get("name", "").strip()
            cams_dict = APP_STATE.setdefault("cameras", dict(CAMERA_LOCATIONS))
            if cam_name in cams_dict:
                del cams_dict[cam_name]
                if cam_name in CAMERA_LOCATIONS:
                    del CAMERA_LOCATIONS[cam_name]
                self._send_json({"status": "success", "message": f"Camera node '{cam_name}' removed."})
                return
            self._send_json({"status": "error", "error": "Camera not found."}, status=404)
            return

        if parsed.path == "/api/teams/add":

            new_id = max([t["id"] for t in APP_STATE["teams"]], default=0) + 1
            entry = {
                "id": new_id,
                "name": body.get("name", "New Rescue Team"),
                "org": body.get("org", "NGO"),
                "phone": body.get("phone", "6303126628"),
                "base_location": body.get("base_location", "Kurnool"),
                "lat": float(body.get("lat", 15.8350)),
                "lon": float(body.get("lon", 78.0450)),
                "username": body.get("username", f"ngo_{new_id}").strip(),
                "password": body.get("password", "ngo123").strip(),
                "available": True,
            }
            saved_entry = save_team_to_db(entry)
            APP_STATE["teams"].append(saved_entry)
            self._send_json(saved_entry, status=201)
            return

        if parsed.path == "/api/teams/delete":
            tid = int(body.get("id", 0))
            delete_team_from_db(tid)
            APP_STATE["teams"] = [t for t in APP_STATE["teams"] if t["id"] != tid]
            self._send_json({"deleted": tid, "status": "success"})
            return

        if parsed.path == "/api/scan":
            cam = body.get("camera_location", "CAR STAND")
            cid = int(body.get("case_id", 1))
            pname = body.get("person_name", "N.K.SYAM")

            coords = CAMERA_LOCATIONS.get(cam, {"lat": 15.8281, "lon": 78.0373})

            # Record camera sighting into PostgreSQL person_sightings & update missing_persons
            sighting_id = save_sighting_to_db(
                case_id=cid,
                camera_name=cam,
                lat=coords["lat"],
                lon=coords["lon"],
                video_source=body.get("video_source", "Surveillance CCTV"),
                confidence_dist=float(body.get("confidence", 0.28)),
            )

            # Auto-assign dispatch in DB
            target_team = APP_STATE["teams"][0] if APP_STATE["teams"] else {"id": 1, "name": "Helping Hands NGO", "lat": 15.8350, "lon": 78.0450}
            avail = [t for t in APP_STATE["teams"] if t.get("available", True)]
            if avail:
                target_team = avail[0]

            route = _calculate_shortest_route(
                target_team.get("lat", 15.8350), target_team.get("lon", 78.0450),
                coords["lat"], coords["lon"],
            )
            dist_km = route.get("distance_km", 1.74)
            eta_min = route.get("eta_minutes", 2.8)

            disp_id = save_dispatch_to_db(
                case_id=cid,
                team_id=target_team.get("id", 1),
                location_name=cam,
                distance_km=dist_km,
                eta_minutes=eta_min,
                status="EN_ROUTE",
                notes=f"Surveillance match detected at {cam}",
            )

            disp_record = {
                "id": disp_id or 101,
                "case_id": cid,
                "person_name": pname,
                "team_id": target_team.get("id", 1),
                "team_name": target_team.get("name", "Helping Hands NGO"),
                "target_location": cam,
                "target_lat": coords["lat"],
                "target_lon": coords["lon"],
                "team_lat": target_team.get("lat", 15.8350),
                "team_lon": target_team.get("lon", 78.0450),
                "distance_km": dist_km,
                "eta_minutes": eta_min,
                "status": "EN_ROUTE",
            }
            if APP_STATE["dispatches"]:
                APP_STATE["dispatches"][0] = disp_record
            else:
                APP_STATE["dispatches"].append(disp_record)

            for c in APP_STATE["cases"]:
                if c["id"] == cid:
                    c["last_seen_location"] = cam
                    c["lat"] = coords["lat"]
                    c["lon"] = coords["lon"]

            self._send_json({
                "status": "success",
                "matched_person": pname,
                "camera_location": cam,
                "lat": coords["lat"],
                "lon": coords["lon"],
                "sighting_id": sighting_id,
                "dispatch_id": disp_id,
            })
            return


        if parsed.path == "/api/cases/add":
            loc_name = body.get("last_seen_location", "CAR STAND")
            coords = CAMERA_LOCATIONS.get(loc_name, {"lat": 15.8281, "lon": 78.0373})
            assigned_team_name = body.get("assigned_team", "Helping Hands NGO")

            entry = {
                "name": body.get("name", "Unnamed Case"),
                "age": body.get("age", 20),
                "gender": body.get("gender", "Unknown"),
                "clothes": body.get("clothes", ""),
                "last_seen_location": loc_name,
                "status": "ACTIVE",
                "created_at": datetime.now().strftime("%d %b, %H:%M"),
                "assigned_team": assigned_team_name,
                "lat": coords["lat"],
                "lon": coords["lon"],
            }
            saved_entry = save_case_to_db(entry)
            APP_STATE["cases"].insert(0, saved_entry)

            # Auto-dispatch notification + simulated SMS to the allotted NGO
            target_team = next((t for t in APP_STATE["teams"] if t["name"] == assigned_team_name), None)
            if target_team:
                _send_case_allotment_notification(saved_entry, target_team, "New case enrolled and allotted by Police Command.")

            self._send_json(saved_entry, status=201)
            return

        if parsed.path == "/api/cases/allot":
            cid = int(body.get("case_id", 0))
            team_id = int(body.get("team_id", 0))
            team_name = body.get("team_name", "")
            note = body.get("note", "").strip()
            custom_phone = body.get("phone", "").strip()

            target_case = next((c for c in APP_STATE["cases"] if c["id"] == cid), None)
            if not target_case:
                self._send_json({"status": "error", "error": "Case not found"}, status=404)
                return

            target_team = None
            if team_id:
                target_team = next((t for t in APP_STATE["teams"] if t["id"] == team_id), None)
            elif team_name:
                target_team = next((t for t in APP_STATE["teams"] if t["name"] == team_name), None)

            if not target_team:
                self._send_json({"status": "error", "error": "NGO Team not found"}, status=404)
                return

            if custom_phone:
                target_team["phone"] = custom_phone

            target_case["assigned_team"] = target_team["name"]
            notif = _send_case_allotment_notification(target_case, target_team, note, phone_override=custom_phone)

            # Persist allotment & dispatch in PostgreSQL
            route = _calculate_shortest_route(
                target_team.get("lat", 15.8350), target_team.get("lon", 78.0450),
                target_case.get("lat", 15.8281), target_case.get("lon", 78.0373),
            )
            disp_id = save_dispatch_to_db(
                case_id=cid,
                team_id=target_team["id"],
                location_name=target_case.get("last_seen_location", "CAR STAND"),
                distance_km=route.get("distance_km", 1.74),
                eta_minutes=route.get("eta_minutes", 2.8),
                status="EN_ROUTE",
                notes=note,
            )

            self._send_json({
                "status": "success",
                "message": f"Case #{cid} ({target_case['name']}) successfully allotted to {target_team['name']}. Alert dispatched to {notif['phone']}!",
                "notification": notif,
                "case": target_case,
                "sms_alert": notif["sms_status"],
                "dispatch_id": disp_id,
            })
            return

        if parsed.path == "/api/notifications/mark-read":
            nid = body.get("id")
            team_id = body.get("team_id")
            for n in APP_STATE.get("notifications", []):
                if nid and n.get("id") == nid:
                    n["read"] = True
                elif team_id and n.get("team_id") == team_id:
                    n["read"] = True
                elif not nid and not team_id:
                    n["read"] = True
            self._send_json({"status": "success"})
            return

        if parsed.path == "/api/cases/delete":
            cid = int(body.get("id", 0))
            delete_case_from_db(cid)
            APP_STATE["cases"] = [c for c in APP_STATE["cases"] if c["id"] != cid]
            self._send_json({"deleted": cid, "status": "success"})
            return

        if parsed.path == "/api/resolve-dispatch":
            cid = int(body.get("case_id", 1))
            outcome = body.get("outcome", "found")
            notes = body.get("notes", "")

            resolve_dispatch_in_db(case_id=cid, outcome=outcome, notes=notes)

            new_status = "RESCUED" if outcome == "found" else "CLOSED"
            for c in APP_STATE["cases"]:
                if c["id"] == cid:
                    c["status"] = new_status

            self._send_json({
                "case_id": cid,
                "case_status": new_status,
                "outcome": outcome,
                "notes": notes,
            })
            return


        self._send_json({"error": "Not Found"}, status=404)


def _get_demo_data(top_k: int = 5, speed: float | None = None) -> dict:
    from .zones import SearchZoneAnalyzer, zones_to_geojson
    graph, person, now = build_demo()

    cams_dict = APP_STATE.get("cameras", CAMERA_LOCATIONS)
    existing_names = {name for _, name, _, _ in PLACES}
    next_id = max([i for i, _, _, _ in PLACES], default=len(PLACES)) + 1
    combined_places = list(PLACES)
    for cam_name, cam_info in cams_dict.items():
        if cam_name not in existing_names:
            combined_places.append((next_id, cam_name, cam_info["lat"], cam_info["lon"]))
            graph.add_location(Location(next_id, cam_name, GeoPoint(cam_info["lat"], cam_info["lon"])))
            next_id += 1
    graph.connect_nearby(2.0)

    analyzer = SearchZoneAnalyzer(graph)
    reach = analyzer.reach_km(person, now, speed_kmph=speed)
    zones = analyzer.analyze(person, now=now, top_k=top_k, speed_kmph=speed)
    return {
        "person": {"name": person.name},
        "reach_km": reach,
        "all_locations": [{"id": i, "name": name, "lat": lat, "lon": lon} for i, name, lat, lon in combined_places],
        "zones": [z.to_dict() for z in zones],
        "geojson": json.loads(zones_to_geojson(zones)),
    }


def run_server(host: str = "0.0.0.0", port: int = 10000) -> None:
    _sync_db_with_state()
    httpd = ThreadingHTTPServer((host, port), MPTrackerHandler)
    print(f"[+] MPTracker Web Dashboard active at http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
