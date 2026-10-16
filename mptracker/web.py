"""Lightweight web dashboard and HTTP server for Render and browser evaluation."""
from __future__ import annotations

import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .demo import build_demo, PLACES
from .zones import SearchZoneAnalyzer, zones_to_geojson


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Missing Person Search-and-Track System</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --card-border: #334155;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; }
    body { background: var(--bg); color: var(--text); line-height: 1.5; padding-bottom: 2rem; }
    header { background: #0b1120; border-bottom: 1px solid var(--card-border); padding: 1.25rem 2rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; }
    .title-group h1 { font-size: 1.4rem; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 0.5rem; }
    .badge { background: #0284c7; color: #fff; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.6rem; border-radius: 9999px; }
    .reg-badge { background: #334155; color: #cbd5e1; font-size: 0.75rem; padding: 0.25rem 0.6rem; border-radius: 4px; }
    .container { max-width: 1280px; margin: 1.5rem auto; padding: 0 1rem; }
    
    .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
    .stat-card { background: var(--card); border: 1px solid var(--card-border); border-radius: 8px; padding: 1.1rem; }
    .stat-label { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.35rem; }
    .stat-val { font-size: 1.25rem; font-weight: 700; color: #fff; }
    .stat-sub { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem; }

    .main-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
    @media (max-width: 960px) { .main-grid { grid-template-columns: 1fr; } }

    .panel { background: var(--card); border: 1px solid var(--card-border); border-radius: 8px; padding: 1.25rem; display: flex; flex-direction: column; }
    .panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
    .panel-title { font-size: 1.1rem; font-weight: 600; }

    #map { height: 440px; border-radius: 6px; border: 1px solid var(--card-border); z-index: 1; }

    .controls-bar { display: flex; gap: 1rem; align-items: flex-end; margin-bottom: 1rem; flex-wrap: wrap; }
    .control-item { display: flex; flex-direction: column; gap: 0.3rem; }
    .control-item label { font-size: 0.8rem; color: var(--text-muted); }
    .control-item select, .control-item input { background: #0b1120; border: 1px solid var(--card-border); color: #fff; padding: 0.45rem 0.75rem; border-radius: 6px; font-size: 0.9rem; }
    .btn { background: var(--accent); color: #0b1120; font-weight: 600; padding: 0.5rem 1.1rem; border-radius: 6px; border: none; cursor: pointer; transition: background 0.15s ease; font-size: 0.9rem; }
    .btn:hover { background: var(--accent-hover); color: #fff; }

    table { width: 100%; border-collapse: collapse; font-size: 0.875rem; margin-top: 0.5rem; }
    th { text-align: left; padding: 0.65rem 0.5rem; background: #0f172a; color: var(--text-muted); border-bottom: 2px solid var(--card-border); font-weight: 600; }
    td { padding: 0.65rem 0.5rem; border-bottom: 1px solid var(--card-border); }
    tr:hover td { background: rgba(255, 255, 255, 0.03); }
    .rank-pill { display: inline-flex; width: 22px; height: 22px; align-items: center; justify-content: center; border-radius: 50%; font-weight: 700; font-size: 0.75rem; }
    .rank-1 { background: var(--danger); color: #fff; }
    .rank-2 { background: var(--warning); color: #000; }
    .rank-3 { background: #3b82f6; color: #fff; }
    .rank-other { background: #475569; color: #fff; }

    .bar-bg { width: 60px; height: 7px; background: #334155; border-radius: 4px; overflow: hidden; display: inline-block; vertical-align: middle; margin-right: 0.5rem; }
    .bar-fill { height: 100%; background: var(--accent); }

    .api-docs { margin-top: 1.5rem; background: var(--card); border: 1px solid var(--card-border); border-radius: 8px; padding: 1.25rem; font-size: 0.85rem; }
    .api-docs h3 { font-size: 1rem; margin-bottom: 0.5rem; }
    .api-tag { font-family: monospace; background: #0b1120; padding: 0.2rem 0.4rem; border-radius: 4px; color: var(--accent); }
  </style>
</head>
<body>
  <header>
    <div class="title-group">
      <h1>Missing Person Search-and-Track System <span class="badge">Problem Statement 112</span></h1>
      <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.2rem;">
        Graph-Based Last-Seen Network Analysis & Dynamic Search-Zone Prediction
      </div>
    </div>
    <div style="display: flex; gap: 0.5rem; align-items: center;">
      <span class="reg-badge">25091A32M7</span>
      <span class="reg-badge">25091A3222</span>
    </div>
  </header>

  <div class="container">
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Subject</div>
        <div class="stat-val" id="stat-subject">Demo Person (Age 10)</div>
        <div class="stat-sub">Male &bull; Blue shirt, black shorts</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Last Confirmed Sighting</div>
        <div class="stat-val" id="stat-last-loc">Budhwarpet Market</div>
        <div class="stat-sub" id="stat-last-time">90 minutes ago</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Walking Speed Model</div>
        <div class="stat-val" id="stat-speed">3.0 km/h</div>
        <div class="stat-sub">Profile: Child (age &lt; 12)</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Max Reachable Radius</div>
        <div class="stat-val" id="stat-reach">4.50 km</div>
        <div class="stat-sub">Dijkstra bounded perimeter</div>
      </div>
    </div>

    <div class="main-grid">
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">Sighting Network & Search Zone Map</div>
          <span style="font-size: 0.8rem; color: var(--text-muted);">Kurnool Grid (OSM)</span>
        </div>
        <div id="map"></div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">Ranked Search Zones</div>
          <span style="font-size: 0.8rem; color: var(--text-muted);">Decaying Random Walk</span>
        </div>

        <div class="controls-bar">
          <div class="control-item">
            <label for="topK">Top Zones</label>
            <select id="topK">
              <option value="3">Top 3</option>
              <option value="5" selected>Top 5</option>
              <option value="8">Top 8</option>
            </select>
          </div>
          <div class="control-item">
            <label for="speedInput">Speed (km/h)</label>
            <input type="number" id="speedInput" value="3.0" step="0.5" min="1" max="10" style="width: 80px;" />
          </div>
          <button class="btn" onclick="fetchData()">Re-calculate</button>
        </div>

        <div style="overflow-x: auto;">
          <table>
            <thead>
              <tr>
                <th style="width: 36px;">#</th>
                <th>Search Zone / Location</th>
                <th>Probability</th>
                <th>Dist</th>
                <th>Radius</th>
                <th>Reasoning</th>
              </tr>
            </thead>
            <tbody id="zones-table">
              <tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Loading graph...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="api-docs">
      <h3>Active System Endpoints</h3>
      <p style="margin-top: 0.4rem; color: var(--text-muted);">
        <span class="api-tag">GET /health</span> - Container healthcheck for Render &bull; 
        <span class="api-tag">GET /api/demo</span> - JSON output of graph traversal and scores &bull; 
        <span class="api-tag">GET /api/geojson</span> - Raw GeoJSON for GIS / geojson.io
      </p>
    </div>
  </div>

  <script>
    let map = L.map('map').setView([15.828, 78.045], 14);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    let mapLayers = L.layerGroup().addTo(map);

    async function fetchData() {
      const topK = document.getElementById('topK').value;
      const speed = document.getElementById('speedInput').value;
      try {
        const res = await fetch(`/api/demo?top=${topK}&speed=${speed}`);
        const data = await res.json();
        renderData(data);
      } catch (err) {
        console.error("Failed to load demo data", err);
      }
    }

    function renderData(data) {
      mapLayers.clearLayers();

      // Stats
      document.getElementById('stat-subject').innerText = `${data.person.name} (Age ${data.person.age})`;
      document.getElementById('stat-last-loc').innerText = data.person.last_sighting.location;
      document.getElementById('stat-last-time').innerText = `${data.person.last_sighting.mins_ago} minutes ago`;
      document.getElementById('stat-speed').innerText = `${data.speed_kmph} km/h`;
      document.getElementById('stat-reach').innerText = `${data.reach_km.toFixed(2)} km`;

      // Draw Sightings Path (Bus Stand -> City Railway -> Budhwarpet)
      const sightingPoints = data.sightings.map(s => [s.lat, s.lon]);
      if (sightingPoints.length > 1) {
        L.polyline(sightingPoints, { color: '#f59e0b', dashArray: '6, 8', weight: 3, opacity: 0.8 }).addTo(mapLayers);
      }

      // Draw all candidate nodes
      data.all_locations.forEach(loc => {
        L.circleMarker([loc.lat, loc.lon], {
          radius: 5,
          color: '#38bdf8',
          fillColor: '#0b1120',
          fillOpacity: 0.8,
          weight: 2
        }).bindPopup(`<b>${loc.name}</b><br>Camera/Landmark Node`).addTo(mapLayers);
      });

      // Draw Ranked Zones & Circles
      const tbody = document.getElementById('zones-table');
      tbody.innerHTML = '';

      const colors = ['#ef4444', '#f59e0b', '#3b82f6', '#10b981', '#8b5cf6', '#64748b'];

      data.zones.forEach((z, idx) => {
        const color = colors[idx] || '#64748b';
        const rankClass = z.rank === 1 ? 'rank-1' : (z.rank === 2 ? 'rank-2' : (z.rank === 3 ? 'rank-3' : 'rank-other'));

        // Circle perimeter on map
        L.circle([z.lat, z.lon], {
          radius: z.radius_km * 1000,
          color: color,
          fillColor: color,
          fillOpacity: 0.15,
          weight: 2
        }).bindPopup(`<b>Rank #${z.rank}: ${z.location}</b><br>Score: ${(z.score * 100).toFixed(1)}%<br>Radius: ${z.radius_km} km<br>${z.reason}`).addTo(mapLayers);

        // Center marker for zone
        L.circleMarker([z.lat, z.lon], {
          radius: 7,
          color: color,
          fillColor: color,
          fillOpacity: 0.9,
          weight: 2
        }).addTo(mapLayers);

        // Table row
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><span class="rank-pill ${rankClass}">${z.rank}</span></td>
          <td style="font-weight: 600;">${z.location}</td>
          <td>
            <div class="bar-bg"><div class="bar-fill" style="width: ${Math.min(100, (z.score * 100) * 2.5)}%;"></div></div>
            ${(z.score * 100).toFixed(1)}%
          </td>
          <td>${z.distance_km} km</td>
          <td>${z.radius_km} km</td>
          <td style="color: var(--text-muted); font-size: 0.8rem;">${z.reason}</td>
        `;
        tbody.appendChild(tr);
      });

      // Fit bounds to sightings
      if (sightingPoints.length) {
        map.fitBounds(L.latLngBounds(sightingPoints), { padding: [40, 40] });
      }
    }

    fetchData();
  </script>
</body>
</html>
"""


def _get_demo_data(top_k: int = 5, speed: float | None = None) -> dict:
    graph, person, now = build_demo()
    analyzer = SearchZoneAnalyzer(graph)
    reach = analyzer.reach_km(person, now, speed_kmph=speed)
    zones = analyzer.analyze(person, now=now, top_k=top_k, speed_kmph=speed)

    sightings = []
    for s in person.sightings:
        mins_ago = int((now - s.timestamp).total_seconds() // 60)
        sightings.append({
            "location": s.location.name,
            "lat": s.location.point.lat,
            "lon": s.location.point.lon,
            "mins_ago": mins_ago,
            "confidence_distance": s.confidence_distance,
            "source": s.source,
        })

    all_locations = [
        {"id": i, "name": name, "lat": lat, "lon": lon}
        for i, name, lat, lon in PLACES
    ]

    last = person.last_sighting
    last_dict = {
        "location": last.location.name if last else "Unknown",
        "mins_ago": int((now - last.timestamp).total_seconds() // 60) if last else 0,
        "lat": last.location.point.lat if last else 0.0,
        "lon": last.location.point.lon if last else 0.0,
    }

    return {
        "person": {
            "id": person.id,
            "name": person.name,
            "age": person.age,
            "gender": person.gender,
            "clothes": person.clothes,
            "last_sighting": last_dict,
        },
        "speed_kmph": speed if speed is not None else person.speed_kmph,
        "reach_km": reach,
        "sightings": sightings,
        "all_locations": all_locations,
        "zones": [z.to_dict() for z in zones],
        "geojson": json.loads(zones_to_geojson(zones)),
    }


class MPTrackerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Concise logging to stdout for Render
        print(f"[HTTP] {self.command} {self.path} - {format % args}")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("/health", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(b'{"status": "healthy"}')
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

            data = _get_demo_data(top_k=top_k, speed=speed)
            payload = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)
            return

        if path == "/api/geojson":
            data = _get_demo_data(top_k=5)
            payload = json.dumps(data["geojson"], indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/geo+json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)
            return

        # Default to web dashboard
        html_bytes = HTML_TEMPLATE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()
        self.wfile.write(html_bytes)


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
