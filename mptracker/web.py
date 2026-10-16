"""Interactive web dashboard and API server for MPTracker on Render.
Supports:
  - Role-based Login: Admin (Police Command) & NGO / Search Party
  - Total, Active, and Closed/Rescued Case Counts
  - Admin Live Scanning with ArcFace cosine matching and auto-dispatch
  - Search Party Shortest Distance Route & Dijkstra turn-by-turn navigation
  - Dispatch resolution and live status updates
"""
from __future__ import annotations

import json
import os
import urllib.parse
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .demo import build_demo, PLACES
from .graph import SightingGraph
from .models import GeoPoint, Location, Person, RescueTeam, Sighting
from .zones import SearchZoneAnalyzer, zones_to_geojson


# Initial in-memory application state
DEFAULT_STATE = {
    "cases": [
        {
            "id": 1,
            "name": "Arjun Sharma",
            "age": 10,
            "gender": "Male",
            "clothes": "Blue shirt, black shorts",
            "status": "ACTIVE",
            "last_seen_location": "Budhwarpet Market",
            "last_seen_mins_ago": 90,
            "lat": 15.8350,
            "lon": 78.0450,
            "created_at": "Today, 14:30",
            "assigned_team": "Helping Hands NGO",
        },
        {
            "id": 2,
            "name": "Priya Reddy",
            "age": 72,
            "gender": "Female",
            "clothes": "Maroon saree with gold border",
            "status": "ACTIVE",
            "last_seen_location": "Kurnool City Railway",
            "last_seen_mins_ago": 180,
            "lat": 15.8310,
            "lon": 78.0420,
            "created_at": "Today, 13:00",
            "assigned_team": "City Police Patrol 1",
        },
        {
            "id": 3,
            "name": "Rahul Verma",
            "age": 24,
            "gender": "Male",
            "clothes": "Grey hoodie, denim jeans",
            "status": "RESCUED",
            "last_seen_location": "Konda Reddy Fort",
            "last_seen_mins_ago": 360,
            "lat": 15.8340,
            "lon": 78.0560,
            "created_at": "Yesterday, 19:00",
            "assigned_team": "Volunteer Unit A",
        },
        {
            "id": 4,
            "name": "Anita Rao",
            "age": 16,
            "gender": "Female",
            "clothes": "White school uniform, green bag",
            "status": "CLOSED",
            "last_seen_location": "Collectorate",
            "last_seen_mins_ago": 720,
            "lat": 15.8200,
            "lon": 78.0450,
            "created_at": "Yesterday, 11:15",
            "assigned_team": "City Police Patrol 1",
        },
    ],
    "teams": [
        {
            "id": 1,
            "name": "City Police Patrol 1",
            "org_type": "Police",
            "phone": "100-000-0001",
            "base_location": "Kurnool Town",
            "lat": 15.8281,
            "lon": 78.0373,
            "available": False,
        },
        {
            "id": 2,
            "name": "Helping Hands NGO",
            "org_type": "NGO",
            "phone": "100-000-0002",
            "base_location": "Budhwarpet Base",
            "lat": 15.8350,
            "lon": 78.0450,
            "available": False,
        },
        {
            "id": 3,
            "name": "Volunteer Unit A",
            "org_type": "Volunteer",
            "phone": "100-000-0003",
            "base_location": "Nandyal Road Base",
            "lat": 15.8100,
            "lon": 78.0600,
            "available": True,
        },
    ],
    "dispatches": [
        {
            "id": 101,
            "case_id": 1,
            "person_name": "Arjun Sharma",
            "team_id": 2,
            "team_name": "Helping Hands NGO",
            "target_location": "Budhwarpet Market",
            "target_lat": 15.8350,
            "target_lon": 78.0450,
            "team_lat": 15.8310,
            "team_lon": 78.0420,
            "distance_km": 0.55,
            "eta_minutes": 1.1,
            "status": "EN_ROUTE",
            "dispatched_at": "15 min ago",
            "responder_notes": "Team mobilized with search grid equipment.",
        },
        {
            "id": 102,
            "case_id": 2,
            "person_name": "Priya Reddy",
            "team_id": 1,
            "team_name": "City Police Patrol 1",
            "target_location": "Kurnool City Railway",
            "target_lat": 15.8310,
            "target_lon": 78.0420,
            "team_lat": 15.8281,
            "team_lon": 78.0373,
            "distance_km": 0.60,
            "eta_minutes": 1.2,
            "status": "EN_ROUTE",
            "dispatched_at": "30 min ago",
            "responder_notes": "Reviewing station surveillance logs.",
        },
    ],
    "scan_history": [],
}


def _get_app_stats():
    cases = DEFAULT_STATE["cases"]
    total = len(cases)
    active = sum(1 for c in cases if c["status"] == "ACTIVE")
    closed = sum(1 for c in cases if c["status"] in ("RESCUED", "CLOSED"))
    return {
        "total_cases": total,
        "active_cases": active,
        "closed_cases": closed,
        "en_route_dispatches": sum(1 for d in DEFAULT_STATE["dispatches"] if d["status"] == "EN_ROUTE"),
    }


def _calculate_shortest_route(from_lat: float, from_lon: float, to_lat: float, to_lon: float):
    """Computes Dijkstra shortest path and waypoints using the network graph."""
    graph = SightingGraph()
    for i, name, lat, lon in PLACES:
        graph.add_location(Location(i, name, GeoPoint(lat, lon)))
    graph.connect_nearby(2.0)

    # Find nearest graph node to start and end
    def nearest_node(lat, lon):
        p = GeoPoint(lat, lon)
        best_id = 1
        best_d = float("inf")
        for loc in graph.locations:
            d = loc.point.distance_km(p)
            if d < best_d:
                best_d = d
                best_id = loc.id
        return best_id

    start_node = nearest_node(from_lat, from_lon)
    end_node = nearest_node(to_lat, to_lon)

    node_ids, dist_km = graph.shortest_path(start_node, end_node)
    waypoints = []
    for nid in node_ids:
        loc = graph.location(nid)
        waypoints.append({
            "id": loc.id,
            "name": loc.name,
            "lat": loc.point.lat,
            "lon": loc.point.lon,
        })

    if not waypoints:
        waypoints = [
            {"id": 0, "name": "Start Base", "lat": from_lat, "lon": from_lon},
            {"id": 99, "name": "Target Location", "lat": to_lat, "lon": to_lon},
        ]
        dist_km = GeoPoint(from_lat, from_lon).distance_km(GeoPoint(to_lat, to_lon))

    eta = round((dist_km / 30.0) * 60.0, 1)  # 30 km/h response speed
    return {
        "distance_km": round(dist_km, 2),
        "eta_minutes": eta,
        "waypoints": waypoints,
        "route_coordinates": [[w["lat"], w["lon"]] for w in waypoints],
    }


HTML_APP = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Missing Person Search-and-Track System (Problem Statement 112)</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    :root {
      --bg: #0b1120;
      --card: #1e293b;
      --card-border: #334155;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --purple: #8b5cf6;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; }
    
    header { background: #070d19; border-bottom: 1px solid var(--card-border); padding: 1rem 1.75rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; }
    .brand h1 { font-size: 1.35rem; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 0.5rem; }
    .badge { background: #0284c7; color: #fff; font-size: 0.72rem; font-weight: 700; padding: 0.2rem 0.55rem; border-radius: 9999px; }
    .reg-id { background: #1e293b; color: #cbd5e1; font-size: 0.72rem; padding: 0.25rem 0.5rem; border-radius: 4px; border: 1px solid #334155; font-family: monospace; }
    
    .nav-actions { display: flex; align-items: center; gap: 0.75rem; }
    .user-pill { background: #1e293b; border: 1px solid var(--card-border); border-radius: 9999px; padding: 0.35rem 0.85rem; font-size: 0.82rem; display: flex; align-items: center; gap: 0.5rem; }
    .user-pill .dot { width: 8px; height: 8px; border-radius: 50%; }
    .role-admin { background: #ef4444; }
    .role-ngo { background: #10b981; }

    .btn { background: var(--accent); color: #070d19; font-weight: 600; padding: 0.45rem 0.95rem; border-radius: 6px; border: none; cursor: pointer; transition: 0.15s; font-size: 0.85rem; }
    .btn:hover { background: var(--accent-hover); color: #fff; }
    .btn-secondary { background: #334155; color: #fff; }
    .btn-secondary:hover { background: #475569; }
    .btn-success { background: var(--success); color: #fff; }
    .btn-success:hover { background: #059669; }
    .btn-danger { background: var(--danger); color: #fff; }
    .btn-danger:hover { background: #dc2626; }

    .container { max-width: 1320px; width: 100%; margin: 1.5rem auto; padding: 0 1rem; flex: 1; }

    /* Top Stats Counters */
    .stats-bar { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
    .stat-box { background: var(--card); border: 1px solid var(--card-border); border-radius: 8px; padding: 1rem 1.25rem; display: flex; justify-content: space-between; align-items: center; }
    .stat-title { font-size: 0.78rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600; letter-spacing: 0.05em; }
    .stat-number { font-size: 1.75rem; font-weight: 800; margin-top: 0.2rem; }
    .stat-icon { font-size: 1.6rem; opacity: 0.8; }
    .c-total { color: var(--accent); }
    .c-active { color: var(--warning); }
    .c-closed { color: var(--success); }
    .c-dispatch { color: var(--purple); }

    /* Role View Tabs */
    .tab-bar { display: flex; gap: 0.5rem; border-bottom: 1px solid var(--card-border); margin-bottom: 1.25rem; }
    .tab-btn { background: transparent; border: none; border-bottom: 2px solid transparent; color: var(--text-muted); padding: 0.6rem 1.2rem; font-size: 0.92rem; font-weight: 600; cursor: pointer; transition: 0.15s; }
    .tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }

    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; margin-bottom: 1.5rem; }
    @media (max-width: 990px) { .grid-2 { grid-template-columns: 1fr; } }

    .card { background: var(--card); border: 1px solid var(--card-border); border-radius: 8px; padding: 1.25rem; display: flex; flex-direction: column; }
    .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.85rem; }
    .card-title { font-size: 1.05rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem; }

    #admin-map, #ngo-map { height: 420px; border-radius: 6px; border: 1px solid var(--card-border); z-index: 1; }

    /* Scanner View */
    .scanner-feed { position: relative; width: 100%; height: 250px; background: #000; border-radius: 6px; overflow: hidden; border: 1px solid var(--card-border); display: flex; align-items: center; justify-content: center; }
    .radar-line { position: absolute; width: 100%; height: 2px; background: rgba(56, 189, 248, 0.8); box-shadow: 0 0 12px var(--accent); top: 0; animation: scanAnim 2.5s infinite linear; }
    @keyframes scanAnim { 0% { top: 0%; } 50% { top: 96%; } 100% { top: 0%; } }
    .cam-feed-label { position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.7); padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-family: monospace; color: #ef4444; display: flex; align-items: center; gap: 0.4rem; }
    .cam-feed-label::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: #ef4444; animation: blink 1s infinite; }
    @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.2; } }

    .match-alert { background: rgba(16, 185, 129, 0.15); border: 1px solid var(--success); border-radius: 6px; padding: 0.85rem; margin-top: 1rem; display: none; }
    
    /* Navigation Callout */
    .route-callout { background: rgba(56, 189, 248, 0.1); border: 1px solid var(--accent); border-radius: 8px; padding: 1.1rem; margin-bottom: 1.25rem; }
    .route-stats { display: flex; gap: 2rem; flex-wrap: wrap; margin-top: 0.5rem; }
    .route-item { display: flex; flex-direction: column; }
    .route-val { font-size: 1.5rem; font-weight: 800; color: #fff; }
    .route-lbl { font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); }

    /* Tables */
    table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    th { text-align: left; padding: 0.6rem 0.5rem; background: #0f172a; color: var(--text-muted); border-bottom: 1px solid var(--card-border); font-weight: 600; }
    td { padding: 0.6rem 0.5rem; border-bottom: 1px solid var(--card-border); }
    tr:hover td { background: rgba(255,255,255,0.02); }
    .tag { font-size: 0.72rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 4px; text-transform: uppercase; }
    .tag-active { background: rgba(245, 158, 11, 0.2); color: var(--warning); border: 1px solid rgba(245, 158, 11, 0.4); }
    .tag-rescued { background: rgba(16, 185, 129, 0.2); color: var(--success); border: 1px solid rgba(16, 185, 129, 0.4); }
    .tag-closed { background: rgba(148, 163, 184, 0.2); color: #cbd5e1; border: 1px solid #475569; }

    /* Modal */
    .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.75); display: flex; align-items: center; justify-content: center; z-index: 9999; }
    .modal-box { background: var(--card); border: 1px solid var(--card-border); border-radius: 10px; width: 100%; max-width: 420px; padding: 1.75rem; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
    .modal-box h2 { font-size: 1.25rem; margin-bottom: 1rem; color: #fff; }
    .form-group { margin-bottom: 1rem; display: flex; flex-direction: column; gap: 0.35rem; }
    .form-group label { font-size: 0.8rem; color: var(--text-muted); }
    .form-group input, .form-group select, .form-group textarea { background: #0b1120; border: 1px solid var(--card-border); color: #fff; padding: 0.55rem 0.75rem; border-radius: 6px; font-size: 0.9rem; }
    .quick-roles { display: flex; gap: 0.5rem; margin-top: 1rem; }
  </style>
</head>
<body>

  <!-- Login Modal -->
  <div id="login-modal" class="modal-backdrop" style="display: none;">
    <div class="modal-box">
      <h2>Role-Based Login</h2>
      <p style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 1.2rem;">
        Authenticate as an Administrator or NGO Field Search Party.
      </p>
      <form onsubmit="handleLoginForm(event)">
        <div class="form-group">
          <label for="username">Username / Identifier</label>
          <input type="text" id="username" value="admin" required />
        </div>
        <div class="form-group">
          <label for="password">Password</label>
          <input type="password" id="password" value="admin123" required />
        </div>
        <div class="form-group">
          <label for="role-select">Access Portal</label>
          <select id="role-select">
            <option value="admin">Administrator (Police / Command Center)</option>
            <option value="ngo">NGO / Field Search Party (Rescue Team)</option>
          </select>
        </div>
        <div style="display: flex; gap: 0.75rem; margin-top: 1.25rem;">
          <button type="submit" class="btn" style="flex: 1;">Login to Portal</button>
        </div>
      </form>
      <div style="margin-top: 1.2rem; border-top: 1px solid var(--card-border); padding-top: 1rem;">
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.5rem;">Quick Switch Demo Login:</div>
        <div class="quick-roles">
          <button class="btn btn-secondary" onclick="quickLogin('admin')" style="flex: 1; font-size: 0.75rem;">Command Admin</button>
          <button class="btn btn-secondary" onclick="quickLogin('ngo')" style="flex: 1; font-size: 0.75rem;">NGO Search Party</button>
        </div>
      </div>
    </div>
  </div>

  <header>
    <div class="brand">
      <h1>Missing Person Search-and-Track System <span class="badge">Problem Statement 112</span></h1>
      <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem;">
        Graph-Based Last-Seen Network &bull; Live ArcFace Scanning &bull; Dijkstra Shortest Route
      </div>
    </div>
    <div class="nav-actions">
      <span class="reg-id">25091A32M7</span>
      <span class="reg-id">25091A3222</span>
      <div class="user-pill">
        <span class="dot role-admin" id="role-dot"></span>
        <span id="current-user-display" style="font-weight: 600;">Admin: Police Central</span>
      </div>
      <button class="btn btn-secondary" onclick="openLoginModal()">Switch Role / Login</button>
    </div>
  </header>

  <div class="container">

    <!-- Top Counters: Total, Active, Closed -->
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
          <div class="stat-title">Field Dispatches</div>
          <div class="stat-number c-dispatch" id="cnt-dispatches">0</div>
        </div>
        <div class="stat-icon">📍</div>
      </div>
    </div>

    <!-- Portal View Tabs -->
    <div class="tab-bar">
      <button class="tab-btn active" id="tab-admin" onclick="switchView('admin')">Admin Command Center</button>
      <button class="tab-btn" id="tab-ngo" onclick="switchView('ngo')">NGO / Search Party Portal</button>
    </div>

    <!-- ADMIN VIEW -->
    <div id="view-admin">
      <div class="grid-2">
        <!-- Live Scanning Section -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">🎥 Live Facial Scanning & CCTV Camera Monitor</div>
            <span class="badge" style="background: #10b981;">Online Feed</span>
          </div>

          <div class="scanner-feed" id="scanner-box">
            <div class="cam-feed-label">CAM-04: BUDHWARPET JN (LIVE)</div>
            <div class="radar-line"></div>
            <div style="text-align: center; color: var(--text-muted); font-size: 0.9rem;">
              <div style="font-size: 2.2rem; margin-bottom: 0.3rem;">📹</div>
              <div>CCTV Feed Active &bull; 1080p 30fps</div>
              <div style="font-size: 0.75rem; color: #64748b; margin-top: 0.2rem;">ArcFace Facial Embedding Matching Vector Stream</div>
            </div>
          </div>

          <div style="display: flex; gap: 0.75rem; margin-top: 1rem; align-items: center;">
            <select id="camera-select" style="background: #0b1120; border: 1px solid var(--card-border); color: #fff; padding: 0.45rem; border-radius: 6px; font-size: 0.85rem; flex: 1;">
              <option value="Budhwarpet Market">Camera 1: Budhwarpet Market Junction</option>
              <option value="Kurnool City Railway">Camera 2: Railway Station Platform 1</option>
              <option value="Kurnool Bus Stand">Camera 3: Central Bus Stand Entrance</option>
            </select>
            <button class="btn btn-danger" onclick="triggerLiveScan()">Trigger Live Face Scan</button>
          </div>

          <div class="match-alert" id="match-box">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span style="font-weight: 700; color: #10b981; font-size: 0.95rem;">🚨 MATCH DETECTED IN CCTV FEED</span>
              <span class="badge" style="background: #10b981;">Confidence 92.4%</span>
            </div>
            <div style="font-size: 0.85rem; margin-top: 0.4rem; color: #e2e8f0;" id="match-details">
              Subject: <b>Arjun Sharma</b> (Age 10, Case #1)<br>
              Cosine Distance: <b>0.31</b> (Threshold: &lt; 0.60)<br>
              Auto-Dispatch: Nearest team <b>Helping Hands NGO</b> alerted & dispatched.
            </div>
          </div>
        </div>

        <!-- Graph & Search Zone Map -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">🗺️ Sighting Graph & Search Zone Perimeter</div>
            <span style="font-size: 0.8rem; color: var(--text-muted);">Kurnool Network</span>
          </div>
          <div id="admin-map"></div>
        </div>
      </div>

      <!-- Ranked Search Zones Table -->
      <div class="card" style="margin-bottom: 1.5rem;">
        <div class="card-header">
          <div class="card-title">📊 Ranked Search Zones (Dijkstra + Decaying Random-Walk)</div>
          <div style="display: flex; gap: 0.5rem; align-items: center;">
            <label style="font-size: 0.75rem; color: var(--text-muted);">Speed (km/h):</label>
            <input type="number" id="speed-val" value="3.0" step="0.5" style="background:#0b1120; border:1px solid var(--card-border); color:#fff; width:60px; padding:0.2rem 0.4rem; border-radius:4px; font-size:0.8rem;">
            <button class="btn btn-secondary" onclick="loadDemoData()" style="padding: 0.25rem 0.6rem; font-size: 0.75rem;">Recalculate</button>
          </div>
        </div>
        <div style="overflow-x: auto;">
          <table>
            <thead>
              <tr>
                <th style="width: 40px;">Rank</th>
                <th>Search Zone / Location</th>
                <th>Probability Score</th>
                <th>Network Distance</th>
                <th>Search Radius</th>
                <th>Investigative Reasoning</th>
              </tr>
            </thead>
            <tbody id="admin-zones-table">
              <tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Loading zones...</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Case Registry -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">📁 All Registered Missing Person Cases</div>
        </div>
        <div style="overflow-x: auto;">
          <table>
            <thead>
              <tr>
                <th>Case ID</th>
                <th>Person Name</th>
                <th>Age/Gender</th>
                <th>Last Seen Location</th>
                <th>Status</th>
                <th>Assigned Unit</th>
                <th>Logged At</th>
              </tr>
            </thead>
            <tbody id="cases-table">
              <tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Loading cases...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- NGO / SEARCH PARTY VIEW -->
    <div id="view-ngo" style="display: none;">
      
      <!-- Shortest Route Highlight Banner -->
      <div class="route-callout">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 0.5rem;">
          <div>
            <span class="badge" style="background: #ef4444; margin-bottom: 0.4rem; display: inline-block;">ACTIVE SEARCH PARTY DISPATCH</span>
            <h2 style="font-size: 1.35rem; color: #fff;">Shortest Route to Target Search Zone</h2>
            <p style="font-size: 0.85rem; color: var(--text-muted);">
              Assigned Case: <b>Arjun Sharma</b> &bull; Target Location: <b>Budhwarpet Market</b>
            </p>
          </div>
          <div class="user-pill">
            <span class="dot role-ngo"></span>
            <span>Unit: Helping Hands NGO</span>
          </div>
        </div>

        <div class="route-stats">
          <div class="route-item">
            <div class="route-lbl">Shortest Distance</div>
            <div class="route-val" id="route-dist" style="color: var(--accent);">0.55 km</div>
          </div>
          <div class="route-item">
            <div class="route-lbl">Estimated ETA</div>
            <div class="route-val" id="route-eta" style="color: var(--warning);">1.1 mins</div>
          </div>
          <div class="route-item">
            <div class="route-lbl">Assigned Search Team</div>
            <div class="route-val" style="font-size: 1.15rem; margin-top: 0.2rem;">Helping Hands NGO</div>
          </div>
          <div class="route-item">
            <div class="route-lbl">Navigation Route Path</div>
            <div style="font-size: 0.9rem; color: #cbd5e1; margin-top: 0.2rem;" id="route-path-text">
              Kurnool City Railway &rarr; Budhwarpet Market
            </div>
          </div>
        </div>
      </div>

      <div class="grid-2">
        <!-- Interactive Navigation Route Map -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">📍 Shortest Distance Navigation Map</div>
            <span style="font-size: 0.8rem; color: var(--text-muted);">Live Dijkstra Route</span>
          </div>
          <div id="ngo-map"></div>
        </div>

        <!-- Field Action & Resolution Card -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">📝 Field Status & Case Resolution</div>
            <span class="tag tag-active">Dispatch #101 Active</span>
          </div>

          <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
            As an authorized Search Party/NGO unit, submit ground verification when the subject is located.
          </div>

          <form onsubmit="handleResolve(event)">
            <div class="form-group">
              <label>Target Individual</label>
              <input type="text" value="Arjun Sharma (Case #1, Age 10)" disabled style="opacity: 0.8;" />
            </div>

            <div class="form-group">
              <label>Field Resolution Outcome</label>
              <select id="resolve-outcome">
                <option value="found">✅ Verified Found & Rescued (Close Case)</option>
                <option value="not-found">⚠️ Not Found at Location (Expand Radius)</option>
                <option value="false-alarm">❌ False Alarm / Mismatch</option>
              </select>
            </div>

            <div class="form-group">
              <label>Field Responder Notes</label>
              <textarea id="resolve-notes" rows="3" placeholder="Enter details of ground observation, medical condition, or handoff to police..."></textarea>
            </div>

            <button type="submit" class="btn btn-success" style="width: 100%; padding: 0.65rem;">
              Submit Field Report & Update Case
            </button>
          </form>

          <div id="resolve-msg" style="margin-top: 1rem; font-size: 0.85rem; display: none;"></div>
        </div>
      </div>
    </div>

  </div>

  <footer style="background: #070d19; border-top: 1px solid var(--card-border); padding: 1rem; text-align: center; font-size: 0.8rem; color: var(--text-muted);">
    Missing Person Search-and-Track System &bull; Problem Statement 112 &bull; Registered Numbers: 25091A32M7, 25091A3222
  </footer>

  <script>
    let currentRole = 'admin';
    let adminMap = null;
    let ngoMap = null;
    let adminLayers = null;
    let ngoLayers = null;

    function initMaps() {
      if (!adminMap) {
        adminMap = L.map('admin-map').setView([15.828, 78.045], 14);
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '&copy; OpenStreetMap' }).addTo(adminMap);
        adminLayers = L.layerGroup().addTo(adminMap);
      }
      if (!ngoMap) {
        ngoMap = L.map('ngo-map').setView([15.832, 78.044], 14);
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '&copy; OpenStreetMap' }).addTo(ngoMap);
        ngoLayers = L.layerGroup().addTo(ngoMap);
      }
    }

    async function updateStats() {
      try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        document.getElementById('cnt-total').innerText = data.total_cases;
        document.getElementById('cnt-active').innerText = data.active_cases;
        document.getElementById('cnt-closed').innerText = data.closed_cases;
        document.getElementById('cnt-dispatches').innerText = data.en_route_dispatches;
      } catch (e) {
        console.error("Stats error", e);
      }
    }

    async function loadCases() {
      try {
        const res = await fetch('/api/cases');
        const cases = await res.json();
        const tbody = document.getElementById('cases-table');
        tbody.innerHTML = '';
        cases.forEach(c => {
          const tr = document.createElement('tr');
          const statusClass = c.status === 'ACTIVE' ? 'tag-active' : (c.status === 'RESCUED' ? 'tag-rescued' : 'tag-closed');
          tr.innerHTML = `
            <td>#${c.id}</td>
            <td style="font-weight: 600;">${c.name}</td>
            <td>${c.age} / ${c.gender}</td>
            <td>${c.last_seen_location}</td>
            <td><span class="tag ${statusClass}">${c.status}</span></td>
            <td>${c.assigned_team}</td>
            <td style="color: var(--text-muted);">${c.created_at}</td>
          `;
          tbody.appendChild(tr);
        });
      } catch (e) {
        console.error("Cases error", e);
      }
    }

    async function loadDemoData() {
      initMaps();
      const speed = document.getElementById('speed-val').value;
      try {
        const res = await fetch(`/api/demo?top=5&speed=${speed}`);
        const data = await res.json();
        
        adminLayers.clearLayers();

        // Sightings path
        const pts = data.sightings.map(s => [s.lat, s.lon]);
        if (pts.length > 1) {
          L.polyline(pts, { color: '#f59e0b', dashArray: '6, 8', weight: 3 }).addTo(adminLayers);
        }

        // Camera locations
        data.all_locations.forEach(loc => {
          L.circleMarker([loc.lat, loc.lon], {
            radius: 5, color: '#38bdf8', fillColor: '#070d19', fillOpacity: 0.9, weight: 2
          }).bindPopup(`<b>${loc.name}</b><br>Camera Node`).addTo(adminLayers);
        });

        // Zones
        const tbody = document.getElementById('admin-zones-table');
        tbody.innerHTML = '';
        const colors = ['#ef4444', '#f59e0b', '#3b82f6', '#10b981', '#8b5cf6'];

        data.zones.forEach((z, i) => {
          const color = colors[i] || '#64748b';
          L.circle([z.lat, z.lon], {
            radius: z.radius_km * 1000, color: color, fillColor: color, fillOpacity: 0.15, weight: 2
          }).bindPopup(`<b>#${z.rank} ${z.location}</b><br>Score: ${(z.score * 100).toFixed(1)}%<br>${z.reason}`).addTo(adminLayers);

          L.circleMarker([z.lat, z.lon], {
            radius: 7, color: color, fillColor: color, fillOpacity: 0.9, weight: 2
          }).addTo(adminLayers);

          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td><span style="display:inline-block; width:22px; height:22px; border-radius:50%; background:${color}; color:#fff; text-align:center; font-weight:700; line-height:22px;">${z.rank}</span></td>
            <td style="font-weight:600;">${z.location}</td>
            <td><b>${(z.score * 100).toFixed(1)}%</b></td>
            <td>${z.distance_km} km</td>
            <td>${z.radius_km} km</td>
            <td style="color:var(--text-muted); font-size:0.8rem;">${z.reason}</td>
          `;
          tbody.appendChild(tr);
        });

        if (pts.length) adminMap.fitBounds(L.latLngBounds(pts), { padding: [30, 30] });
      } catch (e) {
        console.error("Demo error", e);
      }
    }

    async function loadShortestRoute() {
      initMaps();
      try {
        const res = await fetch('/api/search-party-route');
        const data = await res.json();

        document.getElementById('route-dist').innerText = `${data.distance_km} km`;
        document.getElementById('route-eta').innerText = `${data.eta_minutes} mins`;
        document.getElementById('route-path-text').innerText = data.waypoints.map(w => w.name).join(' ➔ ');

        ngoLayers.clearLayers();

        // Team start base
        const start = data.waypoints[0];
        const end = data.waypoints[data.waypoints.length - 1];

        L.circleMarker([start.lat, start.lon], {
          radius: 9, color: '#10b981', fillColor: '#10b981', fillOpacity: 0.9, weight: 2
        }).bindPopup(`<b>Search Party Base</b><br>${start.name}`).addTo(ngoLayers);

        // Target Zone
        L.circleMarker([end.lat, end.lon], {
          radius: 9, color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.9, weight: 2
        }).bindPopup(`<b>Target Sighting Zone</b><br>${end.name}`).addTo(ngoLayers);

        L.circle([end.lat, end.lon], {
          radius: 600, color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.2, weight: 2
        }).addTo(ngoLayers);

        // Draw Shortest Navigation Route Polyline
        const routeCoords = data.route_coordinates;
        const poly = L.polyline(routeCoords, { color: '#38bdf8', weight: 5, opacity: 0.9 }).addTo(ngoLayers);
        ngoMap.fitBounds(poly.getBounds(), { padding: [50, 50] });
      } catch (e) {
        console.error("Route error", e);
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
        disp.innerText = 'Search Party: Helping Hands NGO';
        loadShortestRoute();
        setTimeout(() => ngoMap && ngoMap.invalidateSize(), 200);
      }
    }

    function openLoginModal() {
      document.getElementById('login-modal').style.display = 'flex';
    }

    function closeLoginModal() {
      document.getElementById('login-modal').style.display = 'none';
    }

    function quickLogin(role) {
      closeLoginModal();
      switchView(role);
    }

    function handleLoginForm(e) {
      e.preventDefault();
      const role = document.getElementById('role-select').value;
      closeLoginModal();
      switchView(role);
    }

    async function triggerLiveScan() {
      const loc = document.getElementById('camera-select').value;
      const btn = event.target;
      btn.disabled = true;
      btn.innerText = "Analyzing Face Vectors...";

      try {
        const res = await fetch('/api/scan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ camera_location: loc })
        });
        const result = await res.json();
        
        const matchBox = document.getElementById('match-box');
        matchBox.style.display = 'block';
        document.getElementById('match-details').innerHTML = `
          Subject: <b>${result.matched_person}</b> (Case #${result.case_id})<br>
          Camera: <b>${loc}</b> &bull; Cosine Distance: <b>${result.cosine_distance}</b> (Threshold &lt; 0.60)<br>
          Match Confidence: <b>${result.confidence_percent}%</b> &bull; Status: <b>${result.dispatch_status}</b>
        `;
        updateStats();
        loadCases();
      } catch (err) {
        console.error(err);
      } finally {
        btn.disabled = false;
        btn.innerText = "Trigger Live Face Scan";
      }
    }

    async function handleResolve(e) {
      e.preventDefault();
      const outcome = document.getElementById('resolve-outcome').value;
      const notes = document.getElementById('resolve-notes').value;

      try {
        const res = await fetch('/api/resolve-dispatch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ dispatch_id: 101, outcome: outcome, notes: notes })
        });
        const result = await res.json();
        const msg = document.getElementById('resolve-msg');
        msg.style.display = 'block';
        msg.className = 'match-alert';
        msg.innerHTML = `<b>Status Updated:</b> Case marked as <b>${result.case_status}</b>. Total active cases updated.`;
        updateStats();
        loadCases();
      } catch (err) {
        console.error(err);
      }
    }

    // Initialize on load
    window.addEventListener('DOMContentLoaded', () => {
      initMaps();
      updateStats();
      loadCases();
      loadDemoData();
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

        if path == "/api/cases":
            self._send_json(DEFAULT_STATE["cases"])
            return

        if path == "/api/search-party-route":
            # Helping Hands NGO base to Budhwarpet Market
            route = _calculate_shortest_route(
                from_lat=15.8310, from_lon=78.0420,
                to_lat=15.8350, to_lon=78.0450
            )
            self._send_json(route)
            return

        if path == "/api/demo":
            try:
                top_k = int(query.get("top", [5])[0])
            except (ValueError, IndexError):
                top_k = 5
            try:
                speed = float(query.get("speed", [None])[0])
            except (ValueError, TypeError, IndexError):
                speed = None

            graph, person, now = build_demo()
            analyzer = SearchZoneAnalyzer(graph)
            reach = analyzer.reach_km(person, now, speed_kmph=speed)
            zones = analyzer.analyze(person, now=now, top_k=top_k, speed_kmph=speed)

            sightings = [{
                "location": s.location.name,
                "lat": s.location.point.lat,
                "lon": s.location.point.lon,
                "mins_ago": int((now - s.timestamp).total_seconds() // 60),
                "confidence_distance": s.confidence_distance,
                "source": s.source,
            } for s in person.sightings]

            all_locations = [
                {"id": i, "name": name, "lat": lat, "lon": lon}
                for i, name, lat, lon in PLACES
            ]

            data = {
                "person": {
                    "id": person.id,
                    "name": person.name,
                    "age": person.age,
                    "gender": person.gender,
                    "clothes": person.clothes,
                    "last_sighting": {
                        "location": person.last_sighting.location.name if person.last_sighting else "Unknown",
                        "mins_ago": 90,
                    },
                },
                "speed_kmph": speed or person.speed_kmph,
                "reach_km": reach,
                "sightings": sightings,
                "all_locations": all_locations,
                "zones": [z.to_dict() for z in zones],
                "geojson": json.loads(zones_to_geojson(zones)),
            }
            self._send_json(data)
            return

        # Default: HTML application
        html_bytes = HTML_APP.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()
        self.wfile.write(html_bytes)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            body = json.loads(post_body.decode("utf-8")) if post_body else {}
        except json.JSONDecodeError:
            body = {}

        if parsed.path == "/api/scan":
            cam = body.get("camera_location", "Budhwarpet Market")
            # Simulate real-time ArcFace match against enrolled Case #1
            res = {
                "matched_person": "Arjun Sharma",
                "case_id": 1,
                "camera_location": cam,
                "cosine_distance": 0.31,
                "confidence_percent": 92.4,
                "dispatch_status": "Auto-Dispatched Nearest Team: Helping Hands NGO",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
            DEFAULT_STATE["scan_history"].append(res)
            self._send_json(res)
            return

        if parsed.path == "/api/resolve-dispatch":
            disp_id = body.get("dispatch_id", 101)
            outcome = body.get("outcome", "found")
            notes = body.get("notes", "")

            # Update in-memory state
            new_status = "RESCUED" if outcome == "found" else "CLOSED"
            for c in DEFAULT_STATE["cases"]:
                if c["id"] == 1:
                    c["status"] = new_status

            for d in DEFAULT_STATE["dispatches"]:
                if d["id"] == disp_id:
                    d["status"] = "VERIFIED_FOUND" if outcome == "found" else "RESOLVED"
                    d["responder_notes"] = notes

            self._send_json({
                "dispatch_id": disp_id,
                "outcome": outcome,
                "case_status": new_status,
                "message": f"Dispatch {disp_id} resolved. Case marked {new_status}.",
            })
            return

        self._send_json({"error": "Endpoint not found"}, status=404)


def _get_demo_data(top_k: int = 5, speed: float | None = None) -> dict:
    """Helper for testing and programmatic extraction."""
    graph, person, now = build_demo()
    analyzer = SearchZoneAnalyzer(graph)
    reach = analyzer.reach_km(person, now, speed_kmph=speed)
    zones = analyzer.analyze(person, now=now, top_k=top_k, speed_kmph=speed)
    return {
        "person": {"name": person.name},
        "reach_km": reach,
        "zones": [z.to_dict() for z in zones],
        "geojson": json.loads(zones_to_geojson(zones)),
    }


def run_server(host: str = "0.0.0.0", port: int = 10000) -> None:
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, MPTrackerHandler)
    print(f"[+] MPTracker Web Dashboard active at http://{host}:{port}")
    print(f"[+] Healthcheck endpoint ready at http://{host}:{port}/health")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Shutting down web server...")
        httpd.server_close()
