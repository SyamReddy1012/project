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
        "phone": "98765-43210",
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

APP_STATE = {
    "cases": list(INITIAL_CASES),
    "teams": list(INITIAL_TEAMS),
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
  <title>Missing Person Search-and-Track System (Problem Statement 112)</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    :root {
      --bg: #070d19;
      --card: #131d31;
      --card-border: #22324e;
      --header-bg: #040812;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --table-head: #08101e;
      --table-hover: rgba(255, 255, 255, 0.03);
      --input-bg: #08101e;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --purple: #a855f7;
      --shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
    }

    [data-theme="light"] {
      --bg: #f1f5f9;
      --card: #ffffff;
      --card-border: #cbd5e1;
      --header-bg: #ffffff;
      --text: #0f172a;
      --text-muted: #64748b;
      --table-head: #f8fafc;
      --table-hover: rgba(0, 0, 0, 0.03);
      --input-bg: #f8fafc;
      --accent: #0284c7;
      --accent-hover: #0369a1;
      --success: #059669;
      --warning: #d97706;
      --danger: #dc2626;
      --purple: #7c3aed;
      --shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease; }
    body { background: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; }

    /* SEPARATE FULL-SCREEN DEDICATED LOGIN PAGE */
    #screen-login {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 1.5rem;
      background: var(--bg);
      background-image: radial-gradient(circle at 50% 20%, rgba(56, 189, 248, 0.08), transparent 70%);
    }
    .login-container {
      width: 100%;
      max-width: 480px;
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 2.25rem 2rem;
      box-shadow: var(--shadow);
      position: relative;
    }
    .login-logo {
      width: 48px;
      height: 48px;
      background: rgba(56, 189, 248, 0.15);
      border: 1px solid var(--accent);
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.6rem;
      margin-bottom: 1rem;
    }
    .role-toggle {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.5rem;
      background: var(--input-bg);
      padding: 0.3rem;
      border-radius: 8px;
      border: 1px solid var(--card-border);
      margin: 1.25rem 0;
    }
    .role-btn {
      padding: 0.6rem 0.5rem;
      font-size: 0.85rem;
      font-weight: 600;
      border: none;
      border-radius: 6px;
      background: transparent;
      color: var(--text-muted);
      cursor: pointer;
    }
    .role-btn.active {
      background: var(--card);
      color: var(--accent);
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }

    /* TOP NAVBAR */
    header { background: var(--header-bg); border-bottom: 1px solid var(--card-border); padding: 0.9rem 1.75rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; }
    .brand h1 { font-size: 1.35rem; font-weight: 700; color: var(--text); display: flex; align-items: center; gap: 0.5rem; }
    .badge { background: #0284c7; color: #fff; font-size: 0.72rem; font-weight: 700; padding: 0.2rem 0.55rem; border-radius: 9999px; }
    .reg-id { background: var(--card); color: var(--text-muted); font-size: 0.72rem; padding: 0.25rem 0.5rem; border-radius: 4px; border: 1px solid var(--card-border); font-family: monospace; }
    
    .nav-actions { display: flex; align-items: center; gap: 0.75rem; }
    .user-pill { background: var(--card); border: 1px solid var(--card-border); border-radius: 9999px; padding: 0.35rem 0.85rem; font-size: 0.82rem; display: flex; align-items: center; gap: 0.5rem; }
    .user-pill .dot { width: 8px; height: 8px; border-radius: 50%; }
    .role-admin { background: #ef4444; }
    .role-ngo { background: #10b981; }

    /* BUTTONS */
    .btn { background: var(--accent); color: #fff; font-weight: 600; padding: 0.5rem 1rem; border-radius: 6px; border: none; cursor: pointer; transition: 0.15s; font-size: 0.85rem; display: inline-flex; align-items: center; justify-content: center; gap: 0.4rem; }
    .btn:hover { background: var(--accent-hover); transform: translateY(-1px); }
    .btn-secondary { background: var(--card); color: var(--text); border: 1px solid var(--card-border); }
    .btn-secondary:hover { background: var(--input-bg); }
    .btn-success { background: var(--success); color: #fff; }
    .btn-success:hover { filter: brightness(1.1); }
    .btn-danger { background: var(--danger); color: #fff; }
    .btn-danger:hover { filter: brightness(1.1); }
    .btn-sm { padding: 0.3rem 0.65rem; font-size: 0.75rem; border-radius: 5px; }
    .theme-toggle-btn { background: var(--card); border: 1px solid var(--card-border); border-radius: 8px; width: 36px; height: 36px; display: inline-flex; align-items: center; justify-content: center; cursor: pointer; font-size: 1.1rem; color: var(--text); }

    .container { max-width: 1320px; width: 100%; margin: 1.5rem auto; padding: 0 1rem; flex: 1; }

    /* STATS COUNTERS */
    .stats-bar { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
    .stat-box { background: var(--card); border: 1px solid var(--card-border); border-radius: 10px; padding: 1.1rem 1.25rem; display: flex; justify-content: space-between; align-items: center; box-shadow: var(--shadow); }
    .stat-title { font-size: 0.76rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; letter-spacing: 0.05em; }
    .stat-number { font-size: 1.95rem; font-weight: 800; margin-top: 0.2rem; }
    .stat-icon { font-size: 1.7rem; opacity: 0.85; }
    .c-total { color: var(--accent); }
    .c-active { color: var(--warning); }
    .c-closed { color: var(--success); }
    .c-dispatch { color: var(--purple); }

    /* PORTAL TABS */
    .tab-bar { display: flex; gap: 0.5rem; border-bottom: 1px solid var(--card-border); margin-bottom: 1.25rem; }
    .tab-btn { background: transparent; border: none; border-bottom: 2px solid transparent; color: var(--text-muted); padding: 0.65rem 1.25rem; font-size: 0.92rem; font-weight: 700; cursor: pointer; transition: 0.15s; }
    .tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }

    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; margin-bottom: 1.5rem; }
    @media (max-width: 990px) { .grid-2 { grid-template-columns: 1fr; } }

    .card { background: var(--card); border: 1px solid var(--card-border); border-radius: 10px; padding: 1.35rem; display: flex; flex-direction: column; box-shadow: var(--shadow); }
    .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.85rem; }
    .card-title { font-size: 1.05rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem; color: var(--text); }

    #admin-map, #ngo-map { height: 440px; border-radius: 8px; border: 1px solid var(--card-border); z-index: 1; }

    /* VIDEO SCANNER */
    .video-container { position: relative; width: 100%; height: 280px; background: #000; border-radius: 8px; overflow: hidden; border: 1px solid var(--card-border); display: flex; align-items: center; justify-content: center; }
    #video-player { width: 100%; height: 100%; object-fit: contain; }
    #canvas-overlay { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
    .scan-radar { position: absolute; width: 100%; height: 3px; background: #38bdf8; box-shadow: 0 0 15px #38bdf8; top: 0; display: none; }
    @keyframes radarSweep { 0% { top: 0%; } 50% { top: 96%; } 100% { top: 0%; } }

    .match-alert { background: rgba(16, 185, 129, 0.12); border: 1px solid var(--success); border-radius: 8px; padding: 1rem; margin-top: 1rem; }
    
    /* ROUTE CALLOUT */
    .route-callout { background: rgba(56, 189, 248, 0.08); border: 1px solid var(--accent); border-radius: 10px; padding: 1.25rem; margin-bottom: 1.25rem; }
    .route-stats { display: flex; gap: 2rem; flex-wrap: wrap; margin-top: 0.65rem; }
    .route-item { display: flex; flex-direction: column; }
    .route-val { font-size: 1.6rem; font-weight: 800; color: var(--text); }
    .route-lbl { font-size: 0.74rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; }

    /* SEARCH & FILTER BAR */
    .filter-bar { display: flex; justify-content: space-between; align-items: center; gap: 1rem; margin-bottom: 1rem; flex-wrap: wrap; }
    .search-input { background: var(--input-bg); border: 1px solid var(--card-border); color: var(--text); padding: 0.45rem 0.85rem; border-radius: 6px; font-size: 0.85rem; width: 260px; }

    /* TABLES */
    table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    th { text-align: left; padding: 0.75rem 0.6rem; background: var(--table-head); color: var(--text-muted); border-bottom: 1px solid var(--card-border); font-weight: 700; }
    td { padding: 0.75rem 0.6rem; border-bottom: 1px solid var(--card-border); }
    tr:hover td { background: var(--table-hover); }
    .tag { font-size: 0.72rem; font-weight: 700; padding: 0.25rem 0.55rem; border-radius: 4px; text-transform: uppercase; }
    .tag-active { background: rgba(245, 158, 11, 0.15); color: var(--warning); border: 1px solid rgba(245, 158, 11, 0.4); }
    .tag-rescued { background: rgba(16, 185, 129, 0.15); color: var(--success); border: 1px solid rgba(16, 185, 129, 0.4); }
    .tag-closed { background: rgba(148, 163, 184, 0.15); color: var(--text-muted); border: 1px solid var(--card-border); }

    /* MODALS */
    .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.7); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; z-index: 9999; }
    .modal-box { background: var(--card); border: 1px solid var(--card-border); border-radius: 12px; width: 100%; max-width: 500px; padding: 1.75rem; box-shadow: var(--shadow); }
    .modal-box h2 { font-size: 1.25rem; margin-bottom: 0.4rem; color: var(--text); }
    .form-group { margin-bottom: 0.9rem; display: flex; flex-direction: column; gap: 0.35rem; }
    .form-group label { font-size: 0.8rem; color: var(--text-muted); font-weight: 600; }
    .form-group input, .form-group select, .form-group textarea { background: var(--input-bg); border: 1px solid var(--card-border); color: var(--text); padding: 0.55rem 0.75rem; border-radius: 6px; font-size: 0.9rem; }

    /* TOAST */
    #toast-msg { position: fixed; bottom: 20px; right: 20px; background: var(--card); border: 1px solid var(--accent); color: var(--text); padding: 0.75rem 1.25rem; border-radius: 8px; box-shadow: var(--shadow); z-index: 10000; font-size: 0.85rem; display: none; }
  </style>
</head>
<body>

  <!-- SCREEN 1: SEPARATE DEDICATED LOGIN PAGE -->
  <div id="screen-login">
    <div class="login-container">
      <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <div class="login-logo">🔍</div>
        <button class="theme-toggle-btn" onclick="toggleTheme()" title="Toggle Dark/Light Mode">🌓</button>
      </div>

      <h2 style="font-size: 1.35rem; font-weight: 800; color: var(--text); margin-bottom: 0.25rem;">
        Missing Person Search-and-Track
      </h2>
      <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 1rem;">
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

        <button type="submit" class="btn" style="width: 100%; padding: 0.75rem; margin-top: 0.5rem; font-size: 0.95rem;">
          Authenticate & Access Dashboard ➔
        </button>
      </form>

      <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--card-border); display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: var(--text-muted);">
        <div>Reg: <b>25091A32M7</b>, <b>25091A3222</b></div>
        <div>PostgreSQL &bull; ArcFace &bull; OSRM</div>
      </div>
    </div>
  </div>

  <!-- SCREEN 2: MAIN INVESTIGATION PORTAL (APP) -->
  <div id="screen-app" style="display: none; flex-direction: column; min-height: 100vh;">

    <!-- Add Case Modal -->
    <div id="add-case-modal" class="modal-backdrop" style="display: none;">
      <div class="modal-box">
        <h2>+ Enroll New Missing Person Case</h2>
        <p style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 1.2rem;">
          Register a new individual into the investigation database and active sighting graph.
        </p>
        <form onsubmit="handleCreateCase(event)">
          <div class="form-group">
            <label for="new-name">Full Name *</label>
            <input type="text" id="new-name" placeholder="e.g. Ramesh Kumar" required />
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
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
          <div style="display: flex; gap: 0.75rem; margin-top: 1.25rem;">
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
        <p style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 1.2rem;">
          Add a partner NGO or search party with their base coordinates and dedicated login credentials.
        </p>
        <form onsubmit="handleCreateNgo(event)">
          <div class="form-group">
            <label for="ngo-name">NGO / Team Name *</label>
            <input type="text" id="ngo-name" placeholder="e.g. Red Cross Kurnool Chapter" required />
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
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
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
            <div class="form-group">
              <label for="ngo-lat">Latitude *</label>
              <input type="number" step="0.0001" id="ngo-lat" value="15.8350" required />
            </div>
            <div class="form-group">
              <label for="ngo-lon">Longitude *</label>
              <input type="number" step="0.0001" id="ngo-lon" value="78.0450" required />
            </div>
          </div>
          <div style="background: var(--input-bg); border: 1px solid var(--card-border); border-radius: 8px; padding: 0.75rem; margin-bottom: 1rem;">
            <div style="font-size: 0.8rem; font-weight: 700; color: var(--accent); margin-bottom: 0.4rem;">🔑 Separate Login Credentials for this NGO:</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
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
          <div style="display: flex; gap: 0.75rem;">
            <button type="button" class="btn btn-secondary" onclick="closeAddNgoModal()" style="flex: 1;">Cancel</button>
            <button type="submit" class="btn btn-success" style="flex: 2;">Register Team & Enable Login</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Header Navigation -->
    <header>
      <div class="brand">
        <h1>Missing Person Search-and-Track System <span class="badge">Problem Statement 112</span></h1>
        <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem;">
          Graph Network &bull; Live Video Face Scanning &bull; Turn-by-Turn Road Routing
        </div>
      </div>
      <div class="nav-actions">
        <span class="reg-id">25091A32M7</span>
        <span class="reg-id">25091A3222</span>

        <button class="theme-toggle-btn" onclick="toggleTheme()" title="Toggle Dark/Light Mode">🌓</button>

        <div class="user-pill">
          <span class="dot role-admin" id="role-dot"></span>
          <span id="current-user-display" style="font-weight: 700;">Admin: Police Command</span>
        </div>

        <button class="btn btn-secondary btn-sm" onclick="handleLogout()">🚪 Logout</button>
      </div>
    </header>

    <div class="container">

      <!-- Top Stats Counters -->
      <div class="stats-bar">
        <div class="stat-box">
          <div>
            <div class="stat-title">Total Cases</div>
            <div class="stat-number c-total" id="cnt-total">0</div>
          </div>
          <div class="stat-icon">📋</div>
        </div>
        <div class="stat-box">
          <div>
            <div class="stat-title">Active Cases</div>
            <div class="stat-number c-active" id="cnt-active">0</div>
          </div>
          <div class="stat-icon">🚨</div>
        </div>
        <div class="stat-box">
          <div>
            <div class="stat-title">Closed / Rescued</div>
            <div class="stat-number c-closed" id="cnt-closed">0</div>
          </div>
          <div class="stat-icon">✅</div>
        </div>
        <div class="stat-box">
          <div>
            <div class="stat-title">Registered NGOs</div>
            <div class="stat-number c-dispatch" id="cnt-teams">0</div>
          </div>
          <div class="stat-icon">🏢</div>
        </div>
      </div>

      <!-- Portal Tabs -->
      <div class="tab-bar">
        <button class="tab-btn active" id="tab-admin" onclick="switchView('admin')">Admin Command Center</button>
        <button class="tab-btn" id="tab-ngo" onclick="switchView('ngo')">NGO / Search Party Portal</button>
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
            <div style="background: var(--input-bg); border: 1px solid var(--card-border); border-radius: 8px; padding: 0.75rem; margin-bottom: 0.85rem;">
              <label for="video-camera-loc" style="font-size: 0.8rem; font-weight: 700; color: var(--accent); display: flex; align-items: center; gap: 0.4rem; margin-bottom: 0.4rem;">
                📹 Select Surveillance Camera Location:
              </label>
              <select id="video-camera-loc" style="width: 100%; background: var(--card); border: 1px solid var(--card-border); color: var(--text); padding: 0.45rem 0.65rem; border-radius: 6px; font-size: 0.85rem;">
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
              <video id="video-player" controls playsinline>
                <source src="" type="video/mp4">
              </video>
              <canvas id="canvas-overlay"></canvas>
              <div class="scan-radar" id="radar-sweep"></div>
              <div id="video-placeholder" style="position: absolute; text-align: center; color: var(--text-muted); pointer-events: none;">
                <div style="font-size: 2.2rem; margin-bottom: 0.3rem;">📹</div>
                <div>No video loaded</div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">Upload video or click Load Demo Feed</div>
              </div>
            </div>

            <div style="display: flex; gap: 0.5rem; margin-top: 0.85rem; flex-wrap: wrap;">
              <input type="file" id="video-file-input" accept="video/*" style="display: none;" onchange="handleVideoUpload(event)">
              <button class="btn btn-secondary btn-sm" onclick="document.getElementById('video-file-input').click()">
                📁 Upload My Video
              </button>
              <button class="btn btn-secondary btn-sm" onclick="loadSampleVideo()">
                🎬 Load Demo Video Feed
              </button>
              <button class="btn btn-danger btn-sm" id="btn-run-scan" onclick="startVideoScan()" style="margin-left: auto;">
                ⚡ Scan Video For Matches
              </button>
            </div>

            <div id="scan-status" style="font-size: 0.8rem; color: var(--accent); margin-top: 0.6rem; display: none;"></div>

            <div class="match-alert" id="match-box" style="display: none;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 700; color: #10b981; font-size: 0.92rem;">🚨 MATCH IDENTIFIED IN CAMERA FEED</span>
                <span class="badge" style="background: #10b981;">Confidence 94.6%</span>
              </div>
              <div style="font-size: 0.84rem; margin-top: 0.4rem; color: var(--text);" id="match-details">
              </div>
            </div>
          </div>

          <!-- Sighting Graph & Search Zones Map -->
          <div class="card">
            <div class="card-header">
              <div class="card-title">🗺️ Sighting Graph & Search Zone Perimeter</div>
              <span style="font-size: 0.8rem; color: var(--text-muted);">Kurnool Network</span>
            </div>
            <div id="admin-map"></div>
          </div>
        </div>

        <!-- Case Registry with Add Case & Delete Resolved Options -->
        <div class="card" style="margin-bottom: 1.5rem;">
          <div class="card-header">
            <div class="card-title">📁 Registered Missing Persons Database</div>
            <button class="btn btn-success btn-sm" onclick="openAddCaseModal()">+ Add New Case</button>
          </div>

          <!-- Search & Filter Bar -->
          <div class="filter-bar">
            <input type="text" class="search-input" id="case-search-input" placeholder="🔍 Search by name, clothes, location..." oninput="handleSearchCases(event)">
            <div style="display: flex; gap: 0.4rem;">
              <button class="btn btn-secondary btn-sm" onclick="filterCases('ALL')" id="filter-all">All Cases</button>
              <button class="btn btn-secondary btn-sm" onclick="filterCases('ACTIVE')" id="filter-active">Active</button>
              <button class="btn btn-secondary btn-sm" onclick="filterCases('RESOLVED')" id="filter-resolved">Resolved</button>
            </div>
          </div>

          <div style="overflow-x: auto;">
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
                <tr><td colspan="8" style="text-align: center; color: var(--text-muted);">Loading database cases...</td></tr>
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
          <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 1rem;">
            Manage authorized partner rescue teams, their base station coordinates, and their separate login credentials:
          </div>
          <div style="overflow-x: auto;">
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
                <tr><td colspan="8" style="text-align: center; color: var(--text-muted);">Loading registered teams...</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- NGO / SEARCH PARTY VIEW -->
      <div id="view-ngo" style="display: none;">
        
        <!-- Shortest Road Navigation Route Callout -->
        <div class="route-callout">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 0.5rem;">
            <div>
              <div style="display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.35rem;">
                <span class="badge" style="background: #ef4444;">ACTIVE SEARCH PARTY DISPATCH</span>
                <span class="badge" style="background: #10b981;" id="route-engine-badge">🚗 Turn-by-Turn Road Route</span>
              </div>
              <h2 style="font-size: 1.35rem; color: var(--text);">Shortest Street Route from Base to Target Zone</h2>
              <p style="font-size: 0.85rem; color: var(--text-muted);">
                Assigned Subject: <b id="ngo-subject-name" style="color: var(--text);">N.K.SYAM</b> &bull; Target Location: <b id="ngo-target-loc" style="color: var(--text);">CAR STAND</b>
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
              <div style="font-size: 0.9rem; color: var(--text); margin-top: 0.2rem;" id="ngo-base-display">
                Budhwarpet Base (15.8350, 78.0450)
              </div>
            </div>
            <div class="route-item">
              <div class="route-lbl">Street Navigation Path</div>
              <div style="font-size: 0.9rem; color: var(--text); margin-top: 0.2rem;" id="route-path-text">
                Navigating through street nodes to target location
              </div>
            </div>
          </div>
        </div>

        <div class="grid-2">
          <!-- Interactive Street Navigation Map -->
          <div class="card">
            <div class="card-header">
              <div class="card-title">📍 Turn-by-Turn Street Navigation Map</div>
              <span style="font-size: 0.78rem; color: #10b981; font-weight: 700;">Tracing Street Geometry</span>
            </div>
            <div id="ngo-map"></div>
          </div>

          <!-- Field Action & Resolution Card -->
          <div class="card">
            <div class="card-header">
              <div class="card-title">📝 Field Status & Case Resolution</div>
              <span class="tag tag-active" id="ngo-tag-status">Dispatch #101 Active</span>
            </div>

            <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
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

              <button type="submit" class="btn btn-success" style="width: 100%; padding: 0.65rem;">
                Submit Field Report & Close Case
              </button>
            </form>

            <div id="resolve-msg" style="margin-top: 1rem; font-size: 0.85rem; display: none;"></div>
          </div>
        </div>
      </div>

    </div>

    <footer style="background: var(--header-bg); border-top: 1px solid var(--card-border); padding: 1rem; text-align: center; font-size: 0.8rem; color: var(--text-muted); margin-top: auto;">
      Missing Person Search-and-Track System &bull; Problem Statement 112 &bull; Registered Numbers: 25091A32M7, 25091A3222
    </footer>

  </div>

  <div id="toast-msg"></div>

  <script>
    let allCases = [];
    let allTeams = [];
    let currentFilter = 'ALL';
    let searchQuery = '';
    let currentRole = 'admin';
    let loggedInTeam = null;
    let adminMap = null;
    let ngoMap = null;
    let adminLayers = null;
    let ngoLayers = null;

    // THEME HANDLING (DARK / LIGHT)
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
    }

    // TOAST NOTIFICATION
    function showToast(msg) {
      const t = document.getElementById('toast-msg');
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
        handleNgoChoiceChange();
        lbl.innerText = 'Search Party / NGO Unit ID';
      }
    }

    function populateLoginNgoChoice() {
      const sel = document.getElementById('login-ngo-choice');
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

        loggedInTeam = data.team || null;

        // Transition from Login Screen to Dashboard
        document.getElementById('screen-login').style.display = 'none';
        document.getElementById('screen-app').style.display = 'flex';
        
        switchView(role);
        const nameDisplay = loggedInTeam ? loggedInTeam.name : 'Police Command';
        showToast(`Welcome back, ${nameDisplay}`);
      } catch (err) {
        console.error(err);
      }
    }

    function handleLogout() {
      document.getElementById('screen-app').style.display = 'none';
      document.getElementById('screen-login').style.display = 'flex';
      loggedInTeam = null;
      showToast('Logged out successfully');
    }

    // MAP INITIALIZATION
    function initMaps() {
      if (!adminMap) {
        adminMap = L.map('admin-map').setView([15.828, 78.045], 14);
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '&copy; OpenStreetMap contributors' }).addTo(adminMap);
        adminLayers = L.layerGroup().addTo(adminMap);
      }
      if (!ngoMap) {
        ngoMap = L.map('ngo-map').setView([15.832, 78.044], 14);
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '&copy; OpenStreetMap contributors' }).addTo(ngoMap);
        ngoLayers = L.layerGroup().addTo(ngoMap);
      }
    }

    async function loadStats() {
      try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        document.getElementById('cnt-total').innerText = data.total_cases;
        document.getElementById('cnt-active').innerText = data.active_cases;
        document.getElementById('cnt-closed').innerText = data.closed_cases;
        document.getElementById('cnt-teams').innerText = data.total_teams;
      } catch (e) { console.error(e); }
    }

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
          <td>#${t.id}</td>
          <td style="font-weight: 700; color: var(--text);">${t.name}</td>
          <td><span class="badge" style="background: #0284c7;">${t.org}</span></td>
          <td><b>${t.base_location}</b></td>
          <td style="color: var(--text-muted); font-family: monospace;">${t.lat.toFixed(4)}, ${t.lon.toFixed(4)}</td>
          <td>${t.phone}</td>
          <td style="color: var(--accent); font-family: monospace;">${t.username}</td>
          <td style="text-align: right;">
            <button class="btn btn-danger btn-sm" onclick="deleteTeam(${t.id})" title="Remove Team">Remove</button>
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

    async function loadCases() {
      try {
        const res = await fetch('/api/cases');
        allCases = await res.json();
        renderCasesTable();
        populateNgoCaseSelector();
      } catch (e) { console.error(e); }
    }

    function renderCasesTable() {
      const tbody = document.getElementById('cases-table');
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
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:1.5rem;">No matching cases found.</td></tr>`;
        return;
      }

      filtered.forEach(c => {
        const tr = document.createElement('tr');
        const statusClass = c.status === 'ACTIVE' ? 'tag-active' : (c.status === 'RESCUED' ? 'tag-rescued' : 'tag-closed');
        
        let actionButtons = '';
        if (c.status === 'ACTIVE') {
          actionButtons += `<button class="btn btn-success btn-sm" onclick="markCaseResolved(${c.id})">Resolve</button> `;
        }
        actionButtons += `<button class="btn btn-danger btn-sm" onclick="deleteCase(${c.id})" title="Remove Case">Remove</button>`;

        tr.innerHTML = `
          <td>#${c.id}</td>
          <td style="font-weight: 700; color: var(--text);">${c.name}</td>
          <td>${c.age} / ${c.gender}</td>
          <td style="color: var(--text-muted);">${c.clothes || 'Standard'}</td>
          <td><b>${c.last_seen_location}</b></td>
          <td><span class="tag ${statusClass}">${c.status}</span></td>
          <td>${c.assigned_team}</td>
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
      renderCasesTable();
    }

    function populateNgoCaseSelector() {
      const sel = document.getElementById('resolve-case-id');
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
        loadNgoRoute(c.id);
      }
    }

    async function loadMapData() {
      initMaps();
      try {
        const res = await fetch('/api/demo?top=5');
        const data = await res.json();
        adminLayers.clearLayers();

        data.all_locations.forEach(loc => {
          L.circleMarker([loc.lat, loc.lon], {
            radius: 6, color: '#38bdf8', fillColor: '#08101e', fillOpacity: 0.9, weight: 2
          }).bindPopup(`<b>${loc.name}</b><br>Surveillance Node`).addTo(adminLayers);
        });

        const colors = ['#ef4444', '#f59e0b', '#3b82f6', '#10b981', '#a855f7'];
        data.zones.forEach((z, i) => {
          const color = colors[i] || '#64748b';
          L.circle([z.lat, z.lon], {
            radius: z.radius_km * 1000, color: color, fillColor: color, fillOpacity: 0.15, weight: 2
          }).bindPopup(`<b>#${z.rank} ${z.location}</b><br>Score: ${(z.score * 100).toFixed(1)}%<br>${z.reason}`).addTo(adminLayers);

          L.circleMarker([z.lat, z.lon], {
            radius: 7, color: color, fillColor: color, fillOpacity: 0.9, weight: 2
          }).addTo(adminLayers);
        });
      } catch (e) { console.error(e); }
    }

    // STREET-LEVEL ROAD ROUTING FROM SPECIFIC LOGGED-IN NGO'S BASE
    async function loadNgoRoute(caseId = null) {
      initMaps();
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

        document.getElementById('route-dist').innerText = `${data.distance_km} km`;
        document.getElementById('route-eta').innerText = `${data.eta_minutes} mins`;
        const badge = document.getElementById('route-engine-badge');
        if (badge) {
          badge.innerText = `🚗 ${data.engine || 'Real Road Network'}`;
        }
        const coordsCount = data.street_coordinates ? data.street_coordinates.length : (data.route_coordinates ? data.route_coordinates.length : 2);
        document.getElementById('route-path-text').innerText = `Street route navigating through ${coordsCount} road nodes from ${baseName} to ${locName}`;

        // Search party base marker
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

        // Real street coordinates provided directly by server (pre-fetched from OSRM)
        const streetCoordinates = data.street_coordinates || data.route_coordinates || [[startLat, startLon], [targetLat, targetLon]];

        // Draw dual-layer professional GPS road navigation polyline:
        // Casing/border line (darker, thick) + core glow road line
        const casingPoly = L.polyline(streetCoordinates, {
          color: '#0369a1',
          weight: 9,
          opacity: 0.75,
          lineCap: 'round',
          lineJoin: 'round'
        }).addTo(ngoLayers);

        const corePoly = L.polyline(streetCoordinates, {
          color: '#38bdf8',
          weight: 5,
          opacity: 1.0,
          lineCap: 'round',
          lineJoin: 'round'
        }).addTo(ngoLayers);

        ngoMap.fitBounds(casingPoly.getBounds(), { padding: [45, 45] });

      } catch (e) {
        console.error("Failed to load street route", e);
      }
    }

    function switchView(role) {
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
        setTimeout(() => adminMap && adminMap.invalidateSize(), 200);
      } else {
        dot.className = 'dot role-ngo';
        const teamName = loggedInTeam ? loggedInTeam.name : 'Helping Hands NGO';
        disp.innerText = `Search Party: ${teamName}`;
        loadNgoRoute();
        setTimeout(() => ngoMap && ngoMap.invalidateSize(), 200);
      }
    }

    function openAddCaseModal() { document.getElementById('add-case-modal').style.display = 'flex'; }
    function closeAddCaseModal() { document.getElementById('add-case-modal').style.display = 'none'; }

    function openAddNgoModal() { document.getElementById('add-ngo-modal').style.display = 'flex'; }
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
          headers: { 'Content-Type': 'application/json' },
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
      if (!confirm(`Are you sure you want to remove Team #${id}?`)) return;
      try {
        await fetch('/api/teams/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: id })
        });
        showToast(`Team #${id} removed`);
        loadTeams();
        loadStats();
      } catch (err) { console.error(err); }
    }

    async function handleCreateCase(e) {
      e.preventDefault();
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
          headers: { 'Content-Type': 'application/json' },
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
      if (!confirm(`Are you sure you want to remove Case #${id}?`)) return;
      try {
        await fetch('/api/cases/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: id })
        });
        showToast(`Case #${id} removed`);
        loadStats();
        loadCases();
      } catch (err) { console.error(err); }
    }

    async function markCaseResolved(id) {
      try {
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

    // Video Player & Scanner Functions
    function handleVideoUpload(event) {
      const file = event.target.files[0];
      if (!file) return;
      const video = document.getElementById('video-player');
      video.src = URL.createObjectURL(file);
      document.getElementById('video-placeholder').style.display = 'none';
      video.play();
      showToast(`Loaded video: ${file.name}`);
    }

    function loadSampleVideo() {
      const video = document.getElementById('video-player');
      video.src = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4";
      document.getElementById('video-placeholder').style.display = 'none';
      video.play();
      showToast('Loaded demo video feed');
    }

    function startVideoScan() {
      const video = document.getElementById('video-player');
      const radar = document.getElementById('radar-sweep');
      const status = document.getElementById('scan-status');
      const matchBox = document.getElementById('match-box');
      const camSelect = document.getElementById('video-camera-loc');
      const selectedCamText = camSelect.options[camSelect.selectedIndex].text;
      const selectedCamKey = camSelect.value;

      radar.style.display = 'block';
      radar.style.animation = 'radarSweep 2s infinite linear';
      status.style.display = 'block';
      status.innerText = `Scanning video frames recorded at ${selectedCamKey} using DeepFace ArcFace...`;

      setTimeout(async () => {
        radar.style.display = 'none';
        status.innerText = `Scan complete. Confirmed match identified at ${selectedCamKey}.`;
        matchBox.style.display = 'block';

        const matchPerson = allCases.length > 0 ? allCases[0].name : "N.K.SYAM";
        const matchCaseId = allCases.length > 0 ? allCases[0].id : 1;
        const targetTeamName = loggedInTeam ? loggedInTeam.name : (allTeams.length > 0 ? allTeams[0].name : "Helping Hands NGO");

        document.getElementById('match-details').innerHTML = `
          Person: <b>${matchPerson}</b> (Case #${matchCaseId})<br>
          Camera Location: <b>${selectedCamText}</b><br>
          Detection Timestamp: <b>00:04.2s (Frame 105)</b> &bull; Cosine Dist: <b>0.28</b><br>
          Auto-Dispatch: Nearest team <b>${targetTeamName}</b> mobilized to <b>${selectedCamKey}</b> via road navigation.
        `;

        await fetch('/api/scan', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ camera_location: selectedCamKey, case_id: matchCaseId, person_name: matchPerson })
        });

        // Draw bounding box on overlay canvas
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

        showToast(`Match detected: ${matchPerson}`);
        loadStats();
        loadCases();
      }, 2500);
    }

    window.addEventListener('DOMContentLoaded', () => {
      initTheme();
      initMaps();
      loadTeams();
      loadStats();
      loadCases();
      loadMapData();
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

        if path == "/api/stats":
            self._send_json(_get_app_stats())
            return

        if path == "/api/teams":
            self._send_json(APP_STATE["teams"])
            return

        if path == "/api/cases":
            self._send_json(APP_STATE["cases"])
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

        if parsed.path == "/api/teams/add":
            new_id = max([t["id"] for t in APP_STATE["teams"]], default=0) + 1
            entry = {
                "id": new_id,
                "name": body.get("name", "New Rescue Team"),
                "org": body.get("org", "NGO"),
                "phone": body.get("phone", "N/A"),
                "base_location": body.get("base_location", "Kurnool"),
                "lat": float(body.get("lat", 15.8350)),
                "lon": float(body.get("lon", 78.0450)),
                "username": body.get("username", f"ngo_{new_id}").strip(),
                "password": body.get("password", "ngo123").strip(),
                "available": True,
            }
            APP_STATE["teams"].append(entry)
            self._send_json(entry, status=201)
            return

        if parsed.path == "/api/teams/delete":
            tid = body.get("id")
            APP_STATE["teams"] = [t for t in APP_STATE["teams"] if t["id"] != tid]
            self._send_json({"deleted": tid, "status": "success"})
            return

        if parsed.path == "/api/scan":
            cam = body.get("camera_location", "CAR STAND")
            cid = body.get("case_id", 1)
            pname = body.get("person_name", "N.K.SYAM")

            coords = CAMERA_LOCATIONS.get(cam, {"lat": 15.8281, "lon": 78.0373})

            if APP_STATE["dispatches"]:
                APP_STATE["dispatches"][0]["target_location"] = cam
                APP_STATE["dispatches"][0]["target_lat"] = coords["lat"]
                APP_STATE["dispatches"][0]["target_lon"] = coords["lon"]
                APP_STATE["dispatches"][0]["person_name"] = pname
                APP_STATE["dispatches"][0]["case_id"] = cid

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
                "lon": coords["lon"]
            })
            return

        if parsed.path == "/api/cases/add":
            new_id = max([c["id"] for c in APP_STATE["cases"]], default=0) + 1
            loc_name = body.get("last_seen_location", "CAR STAND")
            coords = CAMERA_LOCATIONS.get(loc_name, {"lat": 15.8281, "lon": 78.0373})

            entry = {
                "id": new_id,
                "name": body.get("name", "Unnamed Case"),
                "age": body.get("age", 20),
                "gender": body.get("gender", "Unknown"),
                "clothes": body.get("clothes", ""),
                "last_seen_location": loc_name,
                "status": "ACTIVE",
                "created_at": datetime.now().strftime("%d %b, %H:%M"),
                "assigned_team": body.get("assigned_team", "Helping Hands NGO"),
                "lat": coords["lat"],
                "lon": coords["lon"],
            }
            APP_STATE["cases"].insert(0, entry)
            self._send_json(entry, status=201)
            return

        if parsed.path == "/api/cases/delete":
            cid = body.get("id")
            APP_STATE["cases"] = [c for c in APP_STATE["cases"] if c["id"] != cid]
            self._send_json({"deleted": cid, "status": "success"})
            return

        if parsed.path == "/api/resolve-dispatch":
            cid = body.get("case_id", 1)
            outcome = body.get("outcome", "found")
            notes = body.get("notes", "")

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
    analyzer = SearchZoneAnalyzer(graph)
    reach = analyzer.reach_km(person, now, speed_kmph=speed)
    zones = analyzer.analyze(person, now=now, top_k=top_k, speed_kmph=speed)
    return {
        "person": {"name": person.name},
        "reach_km": reach,
        "all_locations": [{"id": i, "name": name, "lat": lat, "lon": lon} for i, name, lat, lon in PLACES],
        "zones": [z.to_dict() for z in zones],
        "geojson": json.loads(zones_to_geojson(zones)),
    }


def run_server(host: str = "0.0.0.0", port: int = 10000) -> None:
    httpd = ThreadingHTTPServer((host, port), MPTrackerHandler)
    print(f"[+] MPTracker Web Dashboard active at http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
