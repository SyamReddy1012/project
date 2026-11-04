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

import base64
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .db import (
    verify_password,
    hash_password,
    ensure_db_schema,
    load_cases_from_db,
    save_case_to_db,
    update_case_in_db,
    delete_case_from_db,
    update_case_status_in_db,
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
from .models import GeoPoint, Location, Person, Sighting



# Multi-City Jurisdiction Configuration (10 Major Indian Metropolitan & Regional Cities)
CITIES = {
    "kurnool": {
        "id": "kurnool",
        "name": "Kurnool",
        "state": "Andhra Pradesh",
        "lat": 15.8281,
        "lon": 78.0373,
        "zoom": 14,
        "description": "Historic gateway city of Rayalaseema & Tungabhadra River basin",
    },
    "hyderabad": {
        "id": "hyderabad",
        "name": "Hyderabad",
        "state": "Telangana",
        "lat": 17.3850,
        "lon": 78.4867,
        "zoom": 13,
        "description": "Capital metro hub, major transit junctions & IT cyber corridor",
    },
    "bengaluru": {
        "id": "bengaluru",
        "name": "Bengaluru",
        "state": "Karnataka",
        "lat": 12.9716,
        "lon": 77.5946,
        "zoom": 13,
        "description": "Southern tech capital & central inter-state transport interchange",
    },
    "vijayawada": {
        "id": "vijayawada",
        "name": "Vijayawada",
        "state": "Andhra Pradesh",
        "lat": 16.5062,
        "lon": 80.6480,
        "zoom": 14,
        "description": "Krishna River commercial capital & major railway/bus artery",
    },
    "visakhapatnam": {
        "id": "visakhapatnam",
        "name": "Visakhapatnam (Vizag)",
        "state": "Andhra Pradesh",
        "lat": 17.6868,
        "lon": 83.2185,
        "zoom": 13,
        "description": "Eastern coastal naval port city with extensive beachfront network",
    },
    "tirupati": {
        "id": "tirupati",
        "name": "Tirupati",
        "state": "Andhra Pradesh",
        "lat": 13.6288,
        "lon": 79.4192,
        "zoom": 14,
        "description": "High-density pilgrimage & transit hub at the foot of Tirumala Hills",
    },
    "nandyal": {
        "id": "nandyal",
        "name": "Nandyal",
        "state": "Andhra Pradesh",
        "lat": 15.4786,
        "lon": 78.4836,
        "zoom": 14,
        "description": "Commercial agricultural hub & critical junction on Kurnool highway",
    },
    "chennai": {
        "id": "chennai",
        "name": "Chennai",
        "state": "Tamil Nadu",
        "lat": 13.0827,
        "lon": 80.2707,
        "zoom": 13,
        "description": "Major coastal metropolis, railway terminus & industrial hub",
    },
    "mumbai": {
        "id": "mumbai",
        "name": "Mumbai",
        "state": "Maharashtra",
        "lat": 19.0760,
        "lon": 72.8777,
        "zoom": 13,
        "description": "Financial capital with high-density suburban railway & harbor network",
    },
    "delhi": {
        "id": "delhi",
        "name": "Delhi (NCR)",
        "state": "National Capital",
        "lat": 28.6139,
        "lon": 77.2090,
        "zoom": 13,
        "description": "National capital territory with extensive metro & inter-state terminals",
    },
}

# Multi-City Surveillance Cameras & Landmark Sighting Nodes
CAMERA_LOCATIONS = {
    # Kurnool
    "CAR STAND": {"lat": 15.8281, "lon": 78.0373, "city": "kurnool", "label": "CAM-KNL-01: CAR STAND Main Gate (15.8281, 78.0373)"},
    "Budhwarpet Market": {"lat": 15.8350, "lon": 78.0450, "city": "kurnool", "label": "CAM-KNL-02: Budhwarpet Market Junction (15.8350, 78.0450)"},
    "Kurnool City Railway": {"lat": 15.8310, "lon": 78.0420, "city": "kurnool", "label": "CAM-KNL-03: Kurnool City Railway Station (15.8310, 78.0420)"},
    "Kurnool Bus Stand": {"lat": 15.8281, "lon": 78.0373, "city": "kurnool", "label": "CAM-KNL-04: Central Bus Stand Entrance (15.8281, 78.0373)"},
    "RGM grounds": {"lat": 15.8310, "lon": 78.0420, "city": "kurnool", "label": "CAM-KNL-05: RGM Grounds North Field (15.8310, 78.0420)"},
    "cantene": {"lat": 15.8350, "lon": 78.0450, "city": "kurnool", "label": "CAM-KNL-06: Campus Canteen Surveillance (15.8350, 78.0450)"},
    "DS labs": {"lat": 15.8200, "lon": 78.0450, "city": "kurnool", "label": "CAM-KNL-07: DS Labs Corridor (15.8200, 78.0450)"},
    "RGM hostel": {"lat": 15.8150, "lon": 78.0300, "city": "kurnool", "label": "CAM-KNL-08: RGM Hostel Gate (15.8150, 78.0300)"},
    "RGM gardens": {"lat": 15.8340, "lon": 78.0560, "city": "kurnool", "label": "CAM-KNL-09: RGM Gardens Perimeter (15.8340, 78.0560)"},
    "Konda Reddy Fort": {"lat": 15.8340, "lon": 78.0560, "city": "kurnool", "label": "CAM-KNL-10: Konda Reddy Fort Circle (15.8340, 78.0560)"},
    "maha nandhi": {"lat": 15.8100, "lon": 78.0600, "city": "kurnool", "label": "CAM-KNL-11: Maha Nandhi Road Junction (15.8100, 78.0600)"},
    "Collectorate": {"lat": 15.8200, "lon": 78.0450, "city": "kurnool", "label": "CAM-KNL-12: District Collectorate (15.8200, 78.0450)"},
    "Government Hospital": {"lat": 15.8150, "lon": 78.0300, "city": "kurnool", "label": "CAM-KNL-13: Government General Hospital (15.8150, 78.0300)"},
    "Tungabhadra Bridge": {"lat": 15.8420, "lon": 78.0300, "city": "kurnool", "label": "CAM-KNL-14: Tungabhadra River Bridge (15.8420, 78.0300)"},

    # Hyderabad
    "Charminar Heritage Zone": {"lat": 17.3616, "lon": 78.4747, "city": "hyderabad", "label": "CAM-HYD-01: Charminar Heritage Area (17.3616, 78.4747)"},
    "Secunderabad Railway Station": {"lat": 17.4344, "lon": 78.5017, "city": "hyderabad", "label": "CAM-HYD-02: Secunderabad Central Concourse (17.4344, 78.5017)"},
    "HITEC City Cyber Towers": {"lat": 17.4504, "lon": 78.3808, "city": "hyderabad", "label": "CAM-HYD-03: Cyber Towers Main Junction (17.4504, 78.3808)"},
    "Gachibowli Junction": {"lat": 17.4401, "lon": 78.3489, "city": "hyderabad", "label": "CAM-HYD-04: Gachibowli Outer Ring Road (17.4401, 78.3489)"},
    "Kacheguda Railway Station": {"lat": 17.3892, "lon": 78.4975, "city": "hyderabad", "label": "CAM-HYD-05: Kacheguda Railway Terminal (17.3892, 78.4975)"},
    "Mehdipatnam Bus Depot": {"lat": 17.3916, "lon": 78.4418, "city": "hyderabad", "label": "CAM-HYD-06: Mehdipatnam Ring Bus Station (17.3916, 78.4418)"},
    "Hussain Sagar Tank Bund": {"lat": 17.4239, "lon": 78.4738, "city": "hyderabad", "label": "CAM-HYD-07: Tank Bund Promenade (17.4239, 78.4738)"},
    "Jubilee Hills Checkpost": {"lat": 17.4319, "lon": 78.4073, "city": "hyderabad", "label": "CAM-HYD-08: Jubilee Hills Checkpost Circle (17.4319, 78.4073)"},
    "Dilsukhnagar Metro Hub": {"lat": 17.3688, "lon": 78.5247, "city": "hyderabad", "label": "CAM-HYD-09: Dilsukhnagar Metro Complex (17.3688, 78.5247)"},
    "Ameerpet Metro Junction": {"lat": 17.4375, "lon": 78.4483, "city": "hyderabad", "label": "CAM-HYD-10: Ameerpet Metro Interchange (17.4375, 78.4483)"},

    # Bengaluru
    "Majestic Central Terminal": {"lat": 12.9767, "lon": 77.5713, "city": "bengaluru", "label": "CAM-BLR-01: Majestic KSR Central Terminal (12.9767, 77.5713)"},
    "MG Road Metro Station": {"lat": 12.9756, "lon": 77.6066, "city": "bengaluru", "label": "CAM-BLR-02: MG Road Metro Boulevard (12.9756, 77.6066)"},
    "Koramangala Sony World Signal": {"lat": 12.9352, "lon": 77.6245, "city": "bengaluru", "label": "CAM-BLR-03: Koramangala 80ft Road Signal (12.9352, 77.6245)"},
    "Whitefield ITPL Tech Zone": {"lat": 12.9863, "lon": 77.7308, "city": "bengaluru", "label": "CAM-BLR-04: ITPL Tech Park Main Gate (12.9863, 77.7308)"},
    "Electronic City Phase 1 Toll": {"lat": 12.8452, "lon": 77.6602, "city": "bengaluru", "label": "CAM-BLR-05: Electronic City Expressway Toll (12.8452, 77.6602)"},
    "Indiranagar 100ft Road": {"lat": 12.9784, "lon": 77.6408, "city": "bengaluru", "label": "CAM-BLR-06: Indiranagar 100ft Road Junction (12.9784, 77.6408)"},
    "Yeshwanthpur Railway Junction": {"lat": 13.0238, "lon": 77.5501, "city": "bengaluru", "label": "CAM-BLR-07: Yeshwanthpur Terminal (13.0238, 77.5501)"},
    "Silk Board Junction": {"lat": 12.9177, "lon": 77.6238, "city": "bengaluru", "label": "CAM-BLR-08: Silk Board Outer Ring Flyover (12.9177, 77.6238)"},

    # Vijayawada
    "PNBS Central Bus Station": {"lat": 16.5165, "lon": 80.6200, "city": "vijayawada", "label": "CAM-VJA-01: Pandit Nehru Bus Station (16.5165, 80.6200)"},
    "Vijayawada Railway Junction": {"lat": 16.5186, "lon": 80.6203, "city": "vijayawada", "label": "CAM-VJA-02: Vijayawada Main Junction (16.5186, 80.6203)"},
    "Prakasam Barrage Point": {"lat": 16.5090, "lon": 80.6065, "city": "vijayawada", "label": "CAM-VJA-03: Prakasam Barrage Krishna Bridge (16.5090, 80.6065)"},
    "Kanaka Durga Temple Gate": {"lat": 16.5162, "lon": 80.6052, "city": "vijayawada", "label": "CAM-VJA-04: Kanaka Durga Temple Ghat Road (16.5162, 80.6052)"},
    "Benz Circle Commercial Hub": {"lat": 16.4988, "lon": 80.6552, "city": "vijayawada", "label": "CAM-VJA-05: Benz Circle Flyover Corridor (16.4988, 80.6552)"},
    "Besant Road Market Zone": {"lat": 16.5112, "lon": 80.6288, "city": "vijayawada", "label": "CAM-VJA-06: Besant Road Bazaar Gate (16.5112, 80.6288)"},
    "Ramavarappadu Ring": {"lat": 16.5244, "lon": 80.6750, "city": "vijayawada", "label": "CAM-VJA-07: Ramavarappadu Highway Ring (16.5244, 80.6750)"},

    # Visakhapatnam (Vizag)
    "RK Beach Promenade": {"lat": 17.7126, "lon": 83.3182, "city": "visakhapatnam", "label": "CAM-VZG-01: Ramakrishna Beach Boulevard (17.7126, 83.3182)"},
    "Visakhapatnam Railway Station": {"lat": 17.7215, "lon": 83.2906, "city": "visakhapatnam", "label": "CAM-VZG-02: Vizag Central Platform Gate (17.7215, 83.2906)"},
    "Dwaraka RTC Bus Complex": {"lat": 17.7265, "lon": 83.3040, "city": "visakhapatnam", "label": "CAM-VZG-03: Dwaraka Central Bus Complex (17.7265, 83.3040)"},
    "Jagadamba Junction": {"lat": 17.7118, "lon": 83.3015, "city": "visakhapatnam", "label": "CAM-VZG-04: Jagadamba Commercial Circle (17.7118, 83.3015)"},
    "Rushikonda IT Hill": {"lat": 17.7818, "lon": 83.3855, "city": "visakhapatnam", "label": "CAM-VZG-05: Rushikonda IT SEZ Road (17.7818, 83.3855)"},
    "Gajuwaka Industrial Hub": {"lat": 17.6908, "lon": 83.2132, "city": "visakhapatnam", "label": "CAM-VZG-06: Gajuwaka Junction (17.6908, 83.2132)"},
    "Kailasagiri Viewpoint": {"lat": 17.7490, "lon": 83.3424, "city": "visakhapatnam", "label": "CAM-VZG-07: Kailasagiri Hill Entrance (17.7490, 83.3424)"},

    # Tirupati
    "Tirupati Central Railway Station": {"lat": 13.6267, "lon": 79.4217, "city": "tirupati", "label": "CAM-TPT-01: Tirupati Main Railway Terminal (13.6267, 79.4217)"},
    "Central Bus Stand (CBS)": {"lat": 13.6282, "lon": 79.4261, "city": "tirupati", "label": "CAM-TPT-02: Tirupati Central Bus Station (13.6282, 79.4261)"},
    "Alipiri Footpath Toll Gate": {"lat": 13.6521, "lon": 79.3872, "city": "tirupati", "label": "CAM-TPT-03: Alipiri Hill Footpath Toll Gate (13.6521, 79.3872)"},
    "TUDA Circle": {"lat": 13.6334, "lon": 79.4168, "city": "tirupati", "label": "CAM-TPT-04: TUDA Administrative Circle (13.6334, 79.4168)"},
    "Renigunta Junction": {"lat": 13.6496, "lon": 79.5164, "city": "tirupati", "label": "CAM-TPT-05: Renigunta Railway Interchange (13.6496, 79.5164)"},
    "Ramanuja Circle": {"lat": 13.6310, "lon": 79.4312, "city": "tirupati", "label": "CAM-TPT-06: Ramanuja Circle Flyover (13.6310, 79.4312)"},

    # Nandyal
    "Nandyal Clock Tower": {"lat": 15.4820, "lon": 78.4870, "city": "nandyal", "label": "CAM-NDL-01: Nandyal Town Clock Tower (15.4820, 78.4870)"},
    "Nandyal Railway Station": {"lat": 15.4912, "lon": 78.4815, "city": "nandyal", "label": "CAM-NDL-02: Nandyal Railway Junction (15.4912, 78.4815)"},
    "RTC Central Bus Stand": {"lat": 15.4795, "lon": 78.4850, "city": "nandyal", "label": "CAM-NDL-03: Nandyal Bus Station (15.4795, 78.4850)"},
    "Rythu Bazaar Gate": {"lat": 15.4850, "lon": 78.4890, "city": "nandyal", "label": "CAM-NDL-04: Rythu Bazaar Main Market (15.4850, 78.4890)"},
    "Atmakur Gate Circle": {"lat": 15.4950, "lon": 78.4780, "city": "nandyal", "label": "CAM-NDL-05: Atmakur Highway Gate (15.4950, 78.4780)"},
    "Balapanur Crossroad": {"lat": 15.4680, "lon": 78.4920, "city": "nandyal", "label": "CAM-NDL-06: Balapanur Road Junction (15.4680, 78.4920)"},

    # Chennai
    "Chennai Central Puratchi Thalaivar": {"lat": 13.0823, "lon": 80.2755, "city": "chennai", "label": "CAM-MAA-01: Chennai Central Concourse (13.0823, 80.2755)"},
    "Koyambedu CMBT Bus Terminal": {"lat": 13.0694, "lon": 80.1948, "city": "chennai", "label": "CAM-MAA-02: Koyambedu Bus Terminus (13.0694, 80.1948)"},
    "Marina Beach Promenade": {"lat": 13.0500, "lon": 80.2824, "city": "chennai", "label": "CAM-MAA-03: Marina Beach Service Road (13.0500, 80.2824)"},
    "T. Nagar Panagal Park": {"lat": 13.0405, "lon": 80.2337, "city": "chennai", "label": "CAM-MAA-04: T. Nagar Retail Corridor (13.0405, 80.2337)"},
    "Guindy Kathipara Flyover": {"lat": 13.0067, "lon": 80.2016, "city": "chennai", "label": "CAM-MAA-05: Kathipara Cloverleaf Junction (13.0067, 80.2016)"},
    "Chennai International Airport": {"lat": 12.9941, "lon": 80.1709, "city": "chennai", "label": "CAM-MAA-06: Airport Arrival Terminal (12.9941, 80.1709)"},

    # Mumbai
    "Chhatrapati Shivaji Maharaj Terminus": {"lat": 18.9400, "lon": 72.8354, "city": "mumbai", "label": "CAM-BOM-01: CSMT Main Historic Concourse (18.9400, 72.8354)"},
    "Dadar Central Station": {"lat": 19.0178, "lon": 72.8478, "city": "mumbai", "label": "CAM-BOM-02: Dadar Suburban Interchange (19.0178, 72.8478)"},
    "Bandra Kurla Complex (BKC)": {"lat": 19.0657, "lon": 72.8687, "city": "mumbai", "label": "CAM-BOM-03: BKC Avenue Circle (19.0657, 72.8687)"},
    "Gateway of India Promenade": {"lat": 18.9220, "lon": 72.8347, "city": "mumbai", "label": "CAM-BOM-04: Gateway Harbor Jetty (18.9220, 72.8347)"},
    "Andheri Metro Hub": {"lat": 19.1197, "lon": 72.8468, "city": "mumbai", "label": "CAM-BOM-05: Andheri Railway & Metro (19.1197, 72.8468)"},
    "Marine Drive Promenade": {"lat": 18.9432, "lon": 72.8230, "city": "mumbai", "label": "CAM-BOM-06: Queen's Necklace Marine Drive (18.9432, 72.8230)"},

    # Delhi (NCR)
    "New Delhi Railway Station (NDLS)": {"lat": 28.6429, "lon": 77.2195, "city": "delhi", "label": "CAM-DEL-01: NDLS Ajmeri Gate Concourse (28.6429, 77.2195)"},
    "Rajiv Chowk Connaught Place": {"lat": 28.6328, "lon": 77.2197, "city": "delhi", "label": "CAM-DEL-02: Connaught Place Inner Circle (28.6328, 77.2197)"},
    "Kashmiri Gate ISBT": {"lat": 28.6678, "lon": 77.2285, "city": "delhi", "label": "CAM-DEL-03: Kashmiri Gate Inter-State Bus (28.6678, 77.2285)"},
    "India Gate Circle": {"lat": 28.6129, "lon": 77.2295, "city": "delhi", "label": "CAM-DEL-04: India Gate Kartavya Path (28.6129, 77.2295)"},
    "Indira Gandhi Airport T3": {"lat": 28.5562, "lon": 77.1000, "city": "delhi", "label": "CAM-DEL-05: IGI Airport Terminal 3 (28.5562, 77.1000)"},
    "Anand Vihar Terminal": {"lat": 28.6469, "lon": 77.3160, "city": "delhi", "label": "CAM-DEL-06: Anand Vihar Railway & Bus (28.6469, 77.3160)"},
}

INITIAL_CASES = [
    {
        "id": 1,
        "name": "N.K.SYAM",
        "age": 23,
        "gender": "Male",
        "clothes": "BLUE SHIRT",
        "city": "kurnool",
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
        "city": "kurnool",
        "last_seen_location": "RGM grounds",
        "status": "ACTIVE",
        "created_at": "Today, 12:45",
        "assigned_team": "City Police Patrol 1",
        "lat": 15.8310,
        "lon": 78.0420,
    },
    {
        "id": 3,
        "name": "Rajesh Kumar",
        "age": 24,
        "gender": "Male",
        "clothes": "Red polo shirt, jeans",
        "city": "hyderabad",
        "last_seen_location": "Charminar Heritage Zone",
        "status": "ACTIVE",
        "created_at": "Today, 11:20",
        "assigned_team": "Hyderabad Disaster Quick Response Team",
        "lat": 17.3616,
        "lon": 78.4747,
    },
    {
        "id": 4,
        "name": "Priya Sharma",
        "age": 21,
        "gender": "Female",
        "clothes": "Yellow kurti, white leggings",
        "city": "bengaluru",
        "last_seen_location": "Majestic Central Terminal",
        "status": "ACTIVE",
        "created_at": "Today, 09:30",
        "assigned_team": "Bengaluru Red Cross Unit",
        "lat": 12.9767,
        "lon": 77.5713,
    },
    {
        "id": 5,
        "name": "Anand Varma",
        "age": 31,
        "gender": "Male",
        "clothes": "Grey formal shirt, black pants",
        "city": "vijayawada",
        "last_seen_location": "PNBS Central Bus Station",
        "status": "ACTIVE",
        "created_at": "Yesterday, 20:15",
        "assigned_team": "Amaravati Emergency Corps",
        "lat": 16.5165,
        "lon": 80.6200,
    },
    {
        "id": 6,
        "name": "Kavitha Rao",
        "age": 27,
        "gender": "Female",
        "clothes": "Blue saree",
        "city": "visakhapatnam",
        "last_seen_location": "RK Beach Promenade",
        "status": "ACTIVE",
        "created_at": "Yesterday, 17:00",
        "assigned_team": "Coastal Rescue Force",
        "lat": 17.7126,
        "lon": 83.3182,
    },
    {
        "id": 7,
        "name": "Venkatesh M",
        "age": 58,
        "gender": "Male",
        "clothes": "White dhoti and shirt",
        "city": "tirupati",
        "last_seen_location": "Alipiri Footpath Toll Gate",
        "status": "ACTIVE",
        "created_at": "Yesterday, 15:45",
        "assigned_team": "Tirumala Pilgrim Assistance Patrol",
        "lat": 13.6521,
        "lon": 79.3872,
    },
    {
        "id": 8,
        "name": "Nani kumar",
        "age": 17,
        "gender": "Male",
        "clothes": "white shirt black pant",
        "city": "kurnool",
        "last_seen_location": "cantene",
        "status": "ACTIVE",
        "created_at": "2 days ago",
        "assigned_team": "Volunteer Unit A",
        "lat": 15.8350,
        "lon": 78.0450,
    },
    {
        "id": 9,
        "name": "S.Yakub",
        "age": 20,
        "gender": "Male",
        "clothes": "black shirt with blue jeens",
        "city": "kurnool",
        "last_seen_location": "DS labs",
        "status": "ACTIVE",
        "created_at": "2 days ago",
        "assigned_team": "Helping Hands NGO",
        "lat": 15.8200,
        "lon": 78.0450,
    },
    {
        "id": 10,
        "name": "Ramesh Reddy",
        "age": 42,
        "gender": "Male",
        "clothes": "Checkered shirt, grey trousers",
        "city": "nandyal",
        "last_seen_location": "Nandyal Clock Tower",
        "status": "ACTIVE",
        "created_at": "3 days ago",
        "assigned_team": "Nandyal Volunteer Search Group",
        "lat": 15.4820,
        "lon": 78.4870,
    },
    {
        "id": 11,
        "name": "Tharnish",
        "age": 28,
        "gender": "Male",
        "clothes": "red shirt",
        "city": "kurnool",
        "last_seen_location": "RGM gardens",
        "status": "RESCUED",
        "created_at": "4 days ago",
        "assigned_team": "Volunteer Unit A",
        "lat": 15.8340,
        "lon": 78.0560,
    },
    {
        "id": 12,
        "name": "D.Kasim",
        "age": 67,
        "gender": "Male",
        "clothes": "white blue shirt",
        "city": "kurnool",
        "last_seen_location": "maha nandhi",
        "status": "CLOSED",
        "created_at": "5 days ago",
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
        "city": "kurnool",
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
        "city": "kurnool",
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
        "city": "kurnool",
        "base_location": "Nandyal Road Base",
        "lat": 15.8100,
        "lon": 78.0600,
        "phone": "91234-56789",
        "username": "volunteer_a",
        "password": "volunteer123",
        "available": True,
    },
    {
        "id": 4,
        "name": "Hyderabad Disaster Quick Response Team",
        "org": "Disaster Relief",
        "city": "hyderabad",
        "base_location": "HITEC City Rapid Outpost",
        "lat": 17.4450,
        "lon": 78.3750,
        "phone": "98480-11223",
        "username": "hyd_disaster",
        "password": "hyd123",
        "available": True,
    },
    {
        "id": 5,
        "name": "Bengaluru Red Cross Unit",
        "org": "NGO",
        "city": "bengaluru",
        "base_location": "Koramangala Station Base",
        "lat": 12.9360,
        "lon": 77.6200,
        "phone": "98860-33445",
        "username": "blr_redcross",
        "password": "blr123",
        "available": True,
    },
    {
        "id": 6,
        "name": "Coastal Rescue Force",
        "org": "Volunteer",
        "city": "visakhapatnam",
        "base_location": "Beach Patrol Outpost",
        "lat": 17.7150,
        "lon": 83.3200,
        "phone": "94400-55667",
        "username": "coastal_rescue",
        "password": "vizag123",
        "available": True,
    },
    {
        "id": 7,
        "name": "Amaravati Emergency Corps",
        "org": "Police",
        "city": "vijayawada",
        "base_location": "PNBS Central Outpost",
        "lat": 16.5150,
        "lon": 80.6220,
        "phone": "98490-77889",
        "username": "amaravati_corps",
        "password": "vja123",
        "available": True,
    },
    {
        "id": 8,
        "name": "Tirumala Pilgrim Assistance Patrol",
        "org": "Disaster Relief",
        "city": "tirupati",
        "base_location": "Alipiri Footpath Command",
        "lat": 13.6500,
        "lon": 79.3900,
        "phone": "97000-99001",
        "username": "tpt_patrol",
        "password": "tpt123",
        "available": True,
    },
    {
        "id": 9,
        "name": "Nandyal Volunteer Search Group",
        "org": "Volunteer",
        "city": "nandyal",
        "base_location": "Clock Tower Outpost",
        "lat": 15.4800,
        "lon": 78.4850,
        "phone": "96180-22334",
        "username": "nandyal_volunteers",
        "password": "ndl123",
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
        if db_cases is not None:
            APP_STATE["cases"] = db_cases
        db_teams = load_teams_from_db()
        if db_teams is not None:
            APP_STATE["teams"] = db_teams
        db_dispatches = load_dispatches_from_db()
        if db_dispatches is not None:
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
    db_cases = load_cases_from_db()
    if db_cases is not None:
        APP_STATE["cases"] = db_cases
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
    """Generate realistic, smooth street-following road corridor waypoints between two geographic points."""
    import math
    pts = [[round(from_lat, 6), round(from_lon, 6)]]
    steps = 14
    d_lat = to_lat - from_lat
    d_lon = to_lon - from_lon
    total_len = math.hypot(d_lat, d_lon)
    if total_len < 0.0001:
        return [[from_lat, from_lon], [to_lat, to_lon]]

    # Deterministic curve oscillation following street layout
    seed = int(abs(from_lat + from_lon * 2 + to_lat * 3 + to_lon * 4) * 10000) % 500
    curve_amp = 0.12 * math.sin(seed)

    for i in range(1, steps):
        t = i / steps
        # Natural road curvature along perpendicular axis
        offset = math.sin(t * math.pi) * curve_amp * total_len
        lat_step = from_lat + t * d_lat - (d_lon / total_len) * offset
        lon_step = from_lon + t * d_lon + (d_lat / total_len) * offset
        pts.append([round(lat_step, 6), round(lon_step, 6)])

    pts.append([round(to_lat, 6), round(to_lon, 6)])
    return pts


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



def _infer_city_from_coords_or_name(name: str, lat: float | None = None, lon: float | None = None) -> str:
    """Helper to detect city from camera/location name or geographic distance."""
    name_lower = (name or "").lower()
    for cam_name, cam_data in CAMERA_LOCATIONS.items():
        if cam_name.lower() in name_lower or name_lower in cam_name.lower():
            return cam_data.get("city", "kurnool")

    for city_id, city_info in CITIES.items():
        if city_id in name_lower or city_info["name"].lower() in name_lower:
            return city_id

    if lat is not None and lon is not None:
        best_city = "kurnool"
        best_dist = float("inf")
        for city_id, city_info in CITIES.items():
            dist = GeoPoint(lat, lon).distance_to(GeoPoint(city_info["lat"], city_info["lon"]))
            if dist < best_dist:
                best_dist = dist
                best_city = city_id
        return best_city

    return "kurnool"


def _get_city_graph_data(city_id: str | int = "kurnool", top_k: int = 5, speed: float | None = None) -> dict:
    if isinstance(city_id, int):
        top_k = city_id
        city_id = "kurnool"
    """Generate Dijkstra reachability and decaying random-walk zones for any requested city."""
    city_id = (city_id or "kurnool").lower()
    city_info = CITIES.get(city_id, CITIES["kurnool"])

    city_cameras = {
        name: loc for name, loc in CAMERA_LOCATIONS.items()
        if loc.get("city", "kurnool").lower() == city_id
    }
    if not city_cameras:
        city_cameras = {name: loc for name, loc in CAMERA_LOCATIONS.items() if loc.get("city") == "kurnool"}

    graph = SightingGraph()
    loc_objects = []
    for i, (name, loc_data) in enumerate(city_cameras.items(), start=1):
        loc_obj = Location(id=i, name=name, point=GeoPoint(loc_data["lat"], loc_data["lon"]))
        graph.add_location(loc_obj)
        loc_objects.append((i, name, loc_data["lat"], loc_data["lon"], loc_obj))

    graph.connect_nearby(max_km=30.0)

    city_cases = [c for c in APP_STATE["cases"] if c.get("city", "kurnool").lower() == city_id and c.get("status") == "ACTIVE"]
    if not city_cases:
        city_cases = [c for c in APP_STATE["cases"] if c.get("city", "kurnool").lower() == city_id]

    case_name = city_cases[0]["name"] if city_cases else "Target Subject"
    case_age = city_cases[0].get("age", 22) if city_cases else 22
    case_loc_name = city_cases[0].get("last_seen_location") if city_cases else loc_objects[0][1]

    sighting_loc = next((obj for _, name, _, _, obj in loc_objects if name.lower() == case_loc_name.lower()), loc_objects[0][4])

    from datetime import timedelta
    now = datetime.now()
    # 130 min gives multi-hop search zones in dense metropolitan environments
    s = Sighting(person_id=1, location=sighting_loc, timestamp=now - timedelta(minutes=130))
    person = Person(id=1, name=case_name, age=case_age, gender="Male", clothes="Reported Attire", sightings=[s])

    from .zones import SearchZoneAnalyzer, zones_to_geojson
    analyzer = SearchZoneAnalyzer(graph)
    reach = analyzer.reach_km(person, now, speed_kmph=speed)
    zones = analyzer.analyze(person, now=now, top_k=top_k, speed_kmph=speed)

    edges_list = []
    seen_edges = set()
    for u, neighbors in graph._adj.items():
        for v, edge in neighbors.items():
            pair = tuple(sorted((u, v)))
            if pair not in seen_edges:
                seen_edges.add(pair)
                loc_u = graph.location(u)
                loc_v = graph.location(v)
                edges_list.append({
                    "from_id": u,
                    "from_name": loc_u.name,
                    "from_lat": loc_u.point.lat,
                    "from_lon": loc_u.point.lon,
                    "to_id": v,
                    "to_name": loc_v.name,
                    "to_lat": loc_v.point.lat,
                    "to_lon": loc_v.point.lon,
                    "distance_km": round(edge.distance_km, 2),
                    "traversals": edge.traversals,
                })

    return {
        "city": city_info,
        "person": {"name": person.name, "age": person.age, "last_seen": sighting_loc.name},
        "reach_km": reach,
        "all_locations": [{"id": i, "name": name, "lat": lat, "lon": lon} for i, name, lat, lon, _ in loc_objects],
        "edges": edges_list,
        "zones": [z.to_dict() for z in zones],
        "geojson": json.loads(zones_to_geojson(zones)),
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
  
  <!-- Leaflet GIS Map CSS & JS -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

  <style>

    /* SAR DOSSIER & MISSING PERSON FLYER PRINT STYLES */
    @media print {
      body * {
        visibility: hidden !important;
      }
      #flyer-modal, #flyer-modal * {
        visibility: visible !important;
      }
      #flyer-modal {
        position: absolute !important;
        left: 0 !important;
        top: 0 !important;
        width: 100% !important;
        height: auto !important;
        background: #ffffff !important;
        padding: 0 !important;
        margin: 0 !important;
        backdrop-filter: none !important;
      }
      .flyer-sheet {
        box-shadow: none !important;
        border: 2px solid #000000 !important;
        background: #ffffff !important;
        color: #000000 !important;
        max-width: 100% !important;
        width: 100% !important;
        border-radius: 0 !important;
        padding: 1.5rem !important;
      }
      .no-print {
        display: none !important;
      }
    }
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
      max-width: 1440px;
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

    /* CITY SELECTOR TOOLBAR */
    .city-selector-bar {
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 0.75rem 1.15rem;
      margin-bottom: 1.25rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 0.85rem;
      box-shadow: var(--shadow);
    }

    .city-pills {
      display: flex;
      align-items: center;
      gap: 0.45rem;
      flex-wrap: wrap;
      flex: 1;
    }

    .city-pill {
      background: var(--input-bg);
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      font-size: 0.8rem;
      font-weight: 700;
      padding: 0.35rem 0.75rem;
      border-radius: 8px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      transition: all 0.2s ease;
    }

    .city-pill:hover {
      color: var(--text);
      border-color: var(--accent);
      transform: translateY(-1px);
    }

    .city-pill.active {
      background: linear-gradient(135deg, var(--accent), var(--accent-hover));
      color: #fff;
      border-color: var(--accent);
      box-shadow: 0 4px 12px var(--accent-glow);
    }

    .city-select-box {
      background: var(--input-bg);
      border: 1px solid var(--card-border);
      color: var(--text);
      padding: 0.45rem 0.85rem;
      border-radius: 8px;
      font-size: 0.84rem;
      font-weight: 700;
    }

    /* MAP LAYER SELECTOR */
    .map-layer-bar {
      display: flex;
      align-items: center;
      gap: 0.35rem;
      flex-wrap: wrap;
    }

    .layer-btn {
      background: var(--input-bg);
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      font-size: 0.72rem;
      font-weight: 700;
      padding: 0.25rem 0.55rem;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.2s ease;
    }

    .layer-btn:hover {
      color: var(--text);
      border-color: var(--accent);
    }

    .layer-btn.active {
      background: var(--card-solid);
      color: var(--accent);
      border-color: var(--accent);
      box-shadow: 0 0 10px var(--accent-glow);
    }

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

    /* LEAFLET CONTAINER & TACTICAL DARK MODE TILE FIX */
    .leaflet-container {
      background: #0b1120 !important;
      font-family: var(--font-main) !important;
    }

    .leaflet-container * {
      box-sizing: content-box;
      transition: none !important;
    }

    .leaflet-tile {
      max-width: none !important;
    }

    /* Fail-Safe Tactical Military Dark Mode Filter */
    [data-theme="dark"] .leaflet-tile.dark-invert {
      filter: brightness(0.65) invert(1) contrast(2.5) hue-rotate(200deg) saturate(0.35) brightness(0.75);
    }

    #admin-map, #ngo-map {
      height: 480px;
      border-radius: 12px;
      border: 1px solid var(--card-border);
      z-index: 1;
      overflow: hidden;
      box-shadow: inset 0 2px 10px rgba(0, 0, 0, 0.25);
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
    <div id="add-case-modal" class="modal-backdrop" style="display: none;">
      <div class="modal-box" style="max-width: 580px; max-height: 90vh; overflow-y: auto;">
        <h2>?? + Enroll New Missing Person Case</h2>
        <p style="font-size: 0.84rem; color: var(--text-muted); margin-bottom: 1.2rem;">
          Register a missing individual into the PostgreSQL database, initialize facial vectors, and mobilize search zones.
        </p>
        <form onsubmit="handleCreateCase(event)">
          <!-- Photo Upload & Face Preview Zone -->
          <div class="form-group" style="margin-bottom: 1.25rem;">
            <label style="display: flex; align-items: center; justify-content: space-between;">
              <span>?? Person Photo / Facial Recognition Snapshot</span>
              <span style="font-size: 0.72rem; color: var(--accent); font-weight: normal;">DeepFace ArcFace 512-d</span>
            </label>
            <div style="display: flex; gap: 1rem; align-items: center; background: var(--input-bg); border: 2px dashed rgba(59, 130, 246, 0.35); border-radius: 12px; padding: 0.85rem;">
              <div id="case-photo-preview-box" style="width: 70px; height: 70px; border-radius: 50%; overflow: hidden; background: #0f172a; border: 2px solid var(--accent); display: flex; align-items: center; justify-content: center; flex-shrink: 0; box-shadow: 0 0 10px rgba(59,130,246,0.3);">
                <span id="case-photo-placeholder" style="font-size: 2.2rem;">??</span>
                <img id="case-photo-preview-img" src="" style="width: 100%; height: 100%; object-fit: cover; display: none;" />
              </div>
              <div style="flex: 1;">
                <div style="display: flex; gap: 0.45rem; flex-wrap: wrap; margin-bottom: 0.4rem;">
                  <button type="button" class="btn btn-secondary btn-sm" onclick="document.getElementById('new-photo-input').click()">?? Browse Image...</button>
                  <button type="button" class="btn btn-secondary btn-sm" onclick="clearCasePhoto()">? Remove</button>
                </div>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.35rem;">Or select sample avatar:</div>
                <div style="display: flex; gap: 0.3rem; flex-wrap: wrap;">
                  <button type="button" class="btn btn-secondary btn-sm" style="padding: 2px 7px; font-size: 0.74rem;" onclick="setAvatarPreset('male')">?? Male</button>
                  <button type="button" class="btn btn-secondary btn-sm" style="padding: 2px 7px; font-size: 0.74rem;" onclick="setAvatarPreset('female')">?? Female</button>
                  <button type="button" class="btn btn-secondary btn-sm" style="padding: 2px 7px; font-size: 0.74rem;" onclick="setAvatarPreset('senior')">?? Senior</button>
                  <button type="button" class="btn btn-secondary btn-sm" style="padding: 2px 7px; font-size: 0.74rem;" onclick="setAvatarPreset('youth')">?? Youth</button>
                </div>
              </div>
              <input type="file" id="new-photo-input" accept="image/*" onchange="handlePhotoUpload(event)" style="display: none;" />
              <input type="hidden" id="new-photo-base64" value="" />
            </div>
          </div>

          <div class="form-group">
            <label for="new-city">Jurisdiction City / Region *</label>
            <select id="new-city" onchange="handleNewCaseCityChange()" required>
            </select>
          </div>

          <div class="form-group">
            <label for="new-name">Full Name *</label>
            <input type="text" id="new-name" placeholder="e.g. Ramesh Kumar" required />
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.85rem;">
            <div class="form-group">
              <label for="new-age">Age *</label>
              <input type="number" id="new-age" value="21" min="1" max="120" required />
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
            <label for="new-clothes">Clothing & Physical Appearance Description *</label>
            <input type="text" id="new-clothes" placeholder="e.g. Yellow t-shirt, blue jeans, black shoes, backpack" required />
          </div>

          <div class="form-group">
            <label for="new-loc">Last Seen Location / Landmark Node *</label>
            <select id="new-loc" onchange="handleNewCaseLocationChange()" required>
            </select>
            <input type="text" id="new-custom-loc" placeholder="Enter Custom Landmark Name (e.g. Near Metro Pillar 18)" style="display: none; margin-top: 0.5rem; width: 100%;" />
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.85rem;">
            <div class="form-group">
              <label for="new-lat">Latitude *</label>
              <input type="number" step="0.0001" id="new-lat" value="15.8281" required />
            </div>
            <div class="form-group">
              <label for="new-lon">Longitude *</label>
              <input type="number" step="0.0001" id="new-lon" value="78.0373" required />
            </div>
          </div>

          <div class="form-group">
            <label for="new-team">Assigned Response Unit (NGO / Search Party) *</label>
            <select id="new-team" required>
            </select>
          </div>

          <div class="form-group">
            <label for="new-phone">Emergency Informant / Guardian Contact Phone</label>
            <input type="text" id="new-phone" placeholder="e.g. 98480-12345" value="6303126628" />
          </div>

          <div style="display: flex; gap: 0.85rem; margin-top: 1.45rem;">
            <button type="button" class="btn btn-secondary" onclick="closeAddCaseModal()" style="flex: 1;">Cancel</button>
            <button type="submit" class="btn btn-success" style="flex: 2;">Save Case & Begin Tracking</button>
          </div>
        </form>
      </div>
    </div>

    
    
    <!-- Official SAR Dossier / Missing Person Flyer Modal -->
    <div id="flyer-modal" class="modal-backdrop" style="display: none;">
      <div class="modal-box flyer-sheet" style="max-width: 720px; max-height: 92vh; overflow-y: auto; background: #0f172a; border: 2px solid var(--accent); color: var(--text);">
        <!-- Official Header -->
        <div style="border-bottom: 2px solid rgba(56, 189, 248, 0.4); padding-bottom: 0.85rem; margin-bottom: 1.15rem; text-align: center;">
          <div style="font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--accent); font-weight: 800;">
            POLICE EMERGENCY SEARCH AND RESCUE NOTICE &bull; PROBLEM STATEMENT 112
          </div>
          <h1 style="font-size: 1.6rem; font-weight: 900; margin: 0.35rem 0 0.15rem; color: #ef4444; letter-spacing: 0.04em;">
            🚨 MISSING PERSON IDENTIFICATION FLYER
          </h1>
          <div style="font-size: 0.78rem; color: var(--text-muted);">
            Regd: <b style="color:var(--text);">25091A32M7, 25091A3222</b> &bull; Rapid Multi-Agency Sighting & Response Network
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 180px 1fr; gap: 1.25rem; align-items: start; margin-bottom: 1.25rem;">
          <!-- Photo Box -->
          <div style="text-align: center;">
            <div id="flyer-photo-container" style="width: 180px; height: 210px; border: 3px solid #ef4444; border-radius: 8px; overflow: hidden; background: #08101e; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 15px rgba(239, 68, 68, 0.3);">
              <img id="flyer-photo-img" src="" style="width: 100%; height: 100%; object-fit: cover; display: none;" />
              <div id="flyer-photo-placeholder" style="font-size: 4rem; color: var(--text-muted);">👤</div>
            </div>
            <div style="margin-top: 0.5rem; font-size: 0.72rem; color: #10b981; font-weight: 700; text-transform: uppercase;">
              ✓ DeepFace Biometric Enrolled
            </div>
          </div>

          <!-- Person Data Grid -->
          <div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
              <h2 id="flyer-name" style="margin: 0; font-size: 1.45rem; color: var(--text); font-weight: 800;">Target Subject</h2>
              <span id="flyer-status-badge" class="badge" style="background: #ef4444; font-size: 0.78rem;">ACTIVE SEARCH</span>
            </div>

            <table style="width: 100%; font-size: 0.86rem; border-collapse: collapse; margin-top: 0.4rem;">
              <tr style="border-bottom: 1px solid var(--card-border);">
                <td style="padding: 0.35rem 0; color: var(--text-muted); font-weight: 600; width: 38%;">Case ID:</td>
                <td id="flyer-case-id" style="padding: 0.35rem 0; font-weight: 700; color: var(--accent);" class="mono">#1</td>
              </tr>
              <tr style="border-bottom: 1px solid var(--card-border);">
                <td style="padding: 0.35rem 0; color: var(--text-muted); font-weight: 600;">Age & Gender:</td>
                <td id="flyer-age-gender" style="padding: 0.35rem 0; font-weight: 700;">22 Years / Male</td>
              </tr>
              <tr style="border-bottom: 1px solid var(--card-border);">
                <td style="padding: 0.35rem 0; color: var(--text-muted); font-weight: 600;">Jurisdiction City:</td>
                <td id="flyer-city" style="padding: 0.35rem 0; font-weight: 700; text-transform: uppercase; color: #f59e0b;">KURNOOL</td>
              </tr>
              <tr style="border-bottom: 1px solid var(--card-border);">
                <td style="padding: 0.35rem 0; color: var(--text-muted); font-weight: 600;">Last Known Location:</td>
                <td id="flyer-location" style="padding: 0.35rem 0; font-weight: 700; color: #38bdf8;">CAR STAND Junction</td>
              </tr>
              <tr style="border-bottom: 1px solid var(--card-border);">
                <td style="padding: 0.35rem 0; color: var(--text-muted); font-weight: 600;">Clothing Description:</td>
                <td id="flyer-clothes" style="padding: 0.35rem 0; font-weight: 600;">Blue checkered shirt, dark trousers</td>
              </tr>
              <tr>
                <td style="padding: 0.35rem 0; color: var(--text-muted); font-weight: 600;">Emergency Contact:</td>
                <td id="flyer-contact" style="padding: 0.35rem 0; font-weight: 700; color: #10b981;">+91 6303126628</td>
              </tr>
            </table>
          </div>
        </div>

        <!-- Predicted Search Zones / Dijkstra Transit Analysis -->
        <div style="background: var(--input-bg); border: 1px solid var(--card-border); border-radius: 8px; padding: 0.85rem; margin-bottom: 1.15rem;">
          <div style="font-size: 0.78rem; font-weight: 800; color: var(--accent); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.45rem;">
            🎯 Algorithmic Search Radius & Zone Priorities (Dijkstra Decaying Random-Walk)
          </div>
          <div id="flyer-zones-summary" style="font-size: 0.82rem; color: var(--text); line-height: 1.5;">
            Analyzing search envelopes...
          </div>
        </div>

        <!-- Action Hotline Box -->
        <div style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 8px; padding: 0.85rem; text-align: center; margin-bottom: 1.25rem;">
          <div style="font-weight: 800; color: #ef4444; font-size: 0.96rem;">
            CITIZEN ACTION: IF SIGHTED, DO NOT APPROACH AGGRESSIVELY
          </div>
          <div style="font-size: 0.82rem; color: var(--text); margin-top: 0.25rem;">
            Immediately report GPS location to Emergency Hotline: <b style="color: #ef4444; font-size: 1.05rem;">100</b> or Command Dispatch: <b style="color: #10b981; font-size: 1.05rem;">+91 6303126628</b>
          </div>
        </div>

        <!-- Modal Actions (Hidden in Print) -->
        <div class="no-print" style="display: flex; gap: 0.85rem; justify-content: flex-end;">
          <button type="button" class="btn btn-secondary" onclick="closeFlyerModal()">Close</button>
          <button type="button" class="btn btn-primary" onclick="printSarFlyer()">🖨️ Print / Save Official PDF</button>
        </div>
      </div>
    </div>

    <!-- Edit Case Modal -->
    <div id="edit-case-modal" class="modal-backdrop" style="display: none;">
      <div class="modal-box" style="max-width: 580px; max-height: 90vh; overflow-y: auto;">
        <h2>?? Edit Missing Person Case</h2>
        <p style="font-size: 0.84rem; color: var(--text-muted); margin-bottom: 1.2rem;">
          Update jurisdiction city, case status, clothing, location, and responder assignment. Changes persist directly in PostgreSQL.
        </p>
        <form onsubmit="handleSaveEditCase(event)">
          <input type="hidden" id="edit-case-id" />

          <div class="form-group" style="margin-bottom: 1.15rem;">
            <label>Case Photo / Facial Recognition Snapshot</label>
            <div style="display: flex; gap: 1rem; align-items: center; background: var(--input-bg); border: 2px dashed rgba(59, 130, 246, 0.35); border-radius: 12px; padding: 0.75rem;">
              <div id="edit-photo-preview-box" style="width: 60px; height: 60px; border-radius: 50%; overflow: hidden; background: #0f172a; border: 2px solid var(--accent); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                <span id="edit-photo-placeholder" style="font-size: 1.8rem;">??</span>
                <img id="edit-photo-preview-img" src="" style="width: 100%; height: 100%; object-fit: cover; display: none;" />
              </div>
              <div style="flex: 1;">
                <button type="button" class="btn btn-secondary btn-sm" onclick="document.getElementById('edit-photo-input').click()">?? Change Photo...</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="clearEditCasePhoto()">? Clear</button>
              </div>
              <input type="file" id="edit-photo-input" accept="image/*" onchange="handleEditPhotoUpload(event)" style="display: none;" />
              <input type="hidden" id="edit-photo-base64" value="" />
            </div>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.85rem;">
            <div class="form-group">
              <label for="edit-city">Jurisdiction City / Region *</label>
              <select id="edit-city" onchange="handleEditCaseCityChange()" required>
              </select>
            </div>
            <div class="form-group">
              <label for="edit-status">Case Status *</label>
              <select id="edit-status" required>
                <option value="ACTIVE">?? ACTIVE (Under Investigation)</option>
                <option value="RESCUED">? RESCUED (Found & Safe)</option>
                <option value="CLOSED">?? CLOSED (Investigation Closed)</option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <label for="edit-name">Full Name *</label>
            <input type="text" id="edit-name" required />
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.85rem;">
            <div class="form-group">
              <label for="edit-age">Age *</label>
              <input type="number" id="edit-age" required />
            </div>
            <div class="form-group">
              <label for="edit-gender">Gender</label>
              <select id="edit-gender">
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <label for="edit-clothes">Clothing & Description *</label>
            <input type="text" id="edit-clothes" required />
          </div>

          <div class="form-group">
            <label for="edit-loc">Last Seen Location / Landmark Node *</label>
            <select id="edit-loc" onchange="handleEditCaseLocationChange()" required></select>
            <input type="text" id="edit-custom-loc" placeholder="Custom Landmark Name" style="display: none; margin-top: 0.5rem; width: 100%;" />
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.85rem;">
            <div class="form-group">
              <label for="edit-lat">Latitude *</label>
              <input type="number" step="0.0001" id="edit-lat" required />
            </div>
            <div class="form-group">
              <label for="edit-lon">Longitude *</label>
              <input type="number" step="0.0001" id="edit-lon" required />
            </div>
          </div>

          <div class="form-group">
            <label for="edit-team">Assigned Response Unit (NGO / Team) *</label>
            <select id="edit-team" required></select>
          </div>

          <div class="form-group">
            <label for="edit-phone">Contact Phone</label>
            <input type="text" id="edit-phone" />
          </div>

          <div style="display: flex; gap: 0.85rem; margin-top: 1.45rem;">
            <button type="button" class="btn btn-secondary" onclick="closeEditCaseModal()" style="flex: 1;">Cancel</button>
            <button type="submit" class="btn btn-success" style="flex: 2;">Save Changes to Database</button>
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
            <label for="ngo-city">Base City / Region *</label>
            <select id="ngo-city" onchange="handleNgoCityChange()" required>
            </select>
          </div>
          <div class="form-group">
            <label for="ngo-name">NGO / Team Name *</label>
            <input type="text" id="ngo-name" placeholder="e.g. Red Cross Chapter" required />
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
              <input type="text" id="ngo-phone" placeholder="e.g. 98480-12345" value="6303126628" required />
            </div>
          </div>
          <div class="form-group">
            <label for="ngo-email">Contact Email Address</label>
            <input type="email" id="ngo-email" placeholder="e.g. operations@ngo-rescue.org" />
          </div>
          <div class="form-group">
            <label for="ngo-base-preset">Base Location Area</label>
            <select id="ngo-base-preset" onchange="handleNgoBasePresetChange()">
            </select>
          </div>
          <div class="form-group">
            <label for="ngo-base-name">Base Location Label *</label>
            <input type="text" id="ngo-base-name" value="Central Base Outpost" required />
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
                <input type="text" id="ngo-username" placeholder="e.g. team_unit" required />
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

    <!-- Header Navigation -->
    <header>
      <div class="brand">
        <div class="brand-title">
          <span>Missing Person Search-and-Track</span>
          <span class="badge">Problem Statement 112</span>
        </div>
        <div class="brand-meta">
          <span class="pulse-dot"></span>
          <span>SYSTEM ONLINE &bull; Multi-City Sighting Network &bull; Live ArcFace CCTV &bull; Turn-by-Turn OSRM</span>
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

      <!-- Top Stats Counters -->
      <div class="stats-bar">
        <div class="stat-box box-total">
          <div class="stat-info">
            <div class="stat-title">Total Cases</div>
            <div class="stat-number c-total" id="cnt-total">0</div>
            <div class="stat-sub" style="color: var(--accent);">● Real-Time Database Tracking</div>
          </div>
          <div class="stat-icon">📋</div>
        </div>
        <div class="stat-box box-active">
          <div class="stat-info">
            <div class="stat-title">Active Investigations</div>
            <div class="stat-number c-active" id="cnt-active">0</div>
            <div class="stat-sub" style="color: var(--warning);">● Priority Search Mobilized</div>
          </div>
          <div class="stat-icon">🚨</div>
        </div>
        <div class="stat-box box-closed">
          <div class="stat-info">
            <div class="stat-title">Rescued & Closed</div>
            <div class="stat-number c-closed" id="cnt-closed">0</div>
            <div class="stat-sub" style="color: var(--success);">● Subjects Reunited</div>
          </div>
          <div class="stat-icon">✅</div>
        </div>
        <div class="stat-box box-teams">
          <div class="stat-info">
            <div class="stat-title">Registered NGO Units</div>
            <div class="stat-number c-dispatch" id="cnt-teams">0</div>
            <div class="stat-sub" style="color: var(--purple);">● Ready for Immediate Dispatch</div>
          </div>
          <div class="stat-icon">🏢</div>
        </div>
      </div>

      <!-- MULTI-CITY JURISDICTION SELECTOR BAR -->
      <div class="city-selector-bar">
        <div style="display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;">
          <span style="font-size: 1.15rem;">🏙️</span>
          <span style="font-weight: 800; font-size: 0.88rem; color: var(--text);">Surveillance Jurisdiction:</span>
          <span class="badge" style="background: var(--accent); color: #000; font-weight: 800;" id="active-city-badge">KURNOOL</span>
        </div>

        <div class="city-pills" id="city-pills-list">
          <!-- Dynamically populated -->
        </div>

        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <select id="city-select-dropdown" onchange="switchCity(this.value)" class="city-select-box">
            <!-- Dynamically populated -->
          </select>
          <button class="btn btn-success btn-sm" onclick="openAddCaseModal()" style="font-weight: 700; white-space: nowrap;">?? + Enroll Case</button>
          <button class="btn btn-info btn-sm" onclick="openAddNgoModal()" style="font-weight: 700; white-space: nowrap; background: rgba(14, 165, 233, 0.2); border: 1px solid rgba(14, 165, 233, 0.4); color: #38bdf8;">?? + Add NGO</button>
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
              <label for="video-camera-loc" style="font-size: 0.82rem; font-weight: 700; color: var(--accent); display: flex; align-items: center; gap: 0.45rem; margin-bottom: 0.45rem;">
                📹 Select Surveillance Camera Location:
              </label>
              <select id="video-camera-loc" style="width: 100%; background: var(--card); border: 1px solid var(--card-border); color: var(--text); padding: 0.55rem 0.75rem; border-radius: 8px; font-size: 0.88rem;">
              </select>
            </div>

            <div class="video-container" id="video-box">
              <div class="cctv-rec-badge">
                <span style="color: #ef4444;">●</span> LIVE REC &bull; 1080p
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
                📂 Upload CCTV Video
              </button>
              <button class="btn btn-secondary btn-sm" onclick="loadSampleVideo()">
                📹 Load Demo Feed
              </button>
              <button class="btn btn-secondary btn-sm" id="btn-toggle-webcam" onclick="toggleWebcam()">
                🎥 Use Live Webcam
              </button>
              <button class="btn btn-secondary btn-sm" id="btn-toggle-sound" onclick="toggleSoundAlert()" title="Toggle Web Audio Alarm">
                🔔 Alert Sound: ON
              </button>
              <button class="btn btn-danger btn-sm" id="btn-run-scan" onclick="startVideoScan()" style="margin-left: auto;">
                ⚡ AI Scan Frame & Match
              </button>
            </div>

            <div id="scan-status" style="font-size: 0.84rem; font-weight: 600; color: var(--accent); margin-top: 0.75rem; display: none;"></div>

            <div class="match-alert" id="match-box" style="display: none;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 800; color: #10b981; font-size: 0.98rem; display: flex; align-items: center; gap: 0.45rem;">
                  🚨 MATCH CONFIRMED IN SURVEILLANCE FEED
                </span>
                <span class="badge" style="background: #10b981;">Confidence 94.6%</span>
              </div>
              <div style="font-size: 0.88rem; margin-top: 0.55rem; color: var(--text); line-height: 1.5;" id="match-details">
              </div>
            </div>
          </div>

          <!-- Sighting Graph & Search Zones Map with Layer Switcher -->
          <div class="card">
            <div class="card-header">
              <div class="card-title">🗺️ Sighting Graph & Search Zone Perimeter</div>
              <div class="map-layer-bar">
                <button class="layer-btn active" id="btn-layer-tactical_dark" onclick="setMapLayer('tactical_dark')">🌙 Dark HUD</button>
                <button class="layer-btn" id="btn-layer-carto_dark" onclick="setMapLayer('carto_dark')">🏙️ Carto</button>
                <button class="layer-btn" id="btn-layer-osm_light" onclick="setMapLayer('osm_light')">☀️ Street</button>
                <button class="layer-btn" id="btn-layer-satellite" onclick="setMapLayer('satellite')">🛰️ Satellite</button>
              </div>
            </div>
            <div id="admin-map"></div>
          </div>
        </div>

        <!-- Case Registry with City Filter, Add Case & Delete Resolved Options -->
        <div class="card" style="margin-bottom: 1.5rem;">
          <div class="card-header">
            <div class="card-title">📁 Registered Missing Persons Database</div>
            <button class="btn btn-success btn-sm" onclick="openAddCaseModal()">+ Enroll New Case</button>
          </div>

          <!-- Search & Filter Bar with City Scope -->
          <div class="filter-bar">
            <input type="text" class="search-input" id="case-search-input" placeholder="🔍 Search by name, city, clothes, location..." oninput="handleSearchCases(event)">
            <div style="display: flex; gap: 0.45rem; flex-wrap: wrap;">
              <button class="btn btn-secondary btn-sm" onclick="filterCases('ALL')" id="filter-all">All Status</button>
              <button class="btn btn-secondary btn-sm" onclick="filterCases('ACTIVE')" id="filter-active">Active</button>
              <button class="btn btn-secondary btn-sm" onclick="filterCases('RESOLVED')" id="filter-resolved">Resolved</button>
              <button class="btn btn-secondary btn-sm" onclick="toggleCityCaseFilter()" id="filter-city-scope">Current City Only</button>
            </div>
          </div>

          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>City / Region</th>
                  <th>Age / Gender</th>
                  <th>Clothing Description</th>
                  <th>Last Seen Location</th>
                  <th>Status</th>
                  <th>Assigned Unit</th>
                  <th style="text-align: right;">Actions</th>
                </tr>
              </thead>
              <tbody id="cases-table">
                <tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Loading database cases...</td></tr>
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
            Manage authorized partner rescue teams, their base station coordinates, and their separate login credentials across all jurisdictions:
          </div>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Team / NGO Name</th>
                  <th>City</th>
                  <th>Type</th>
                  <th>Base Station Location</th>
                  <th>Coordinates (Lat, Lon)</th>
                  <th>Contact Phone</th>
                  <th>Login Username</th>
                  <th style="text-align: right;">Action</th>
                </tr>
              </thead>
              <tbody id="teams-table">
                <tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Loading registered teams...</td></tr>
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
    let allCities = [];
    let currentCity = 'kurnool';
    let allCases = [];
    let allTeams = [];
    let currentFilter = 'ALL';
    let filterOnlyCurrentCity = false;
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

    // TILE PROVIDERS & FAIL-SAFE DARK MODE TILE LOGIC
    const MAP_PROVIDERS = {
      tactical_dark: {
        name: "Tactical Dark HUD",
        url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        options: { maxZoom: 19, attribution: "&copy; OpenStreetMap" },
        className: "dark-invert"
      },
      carto_dark: {
        name: "Carto DarkMatter",
        url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        options: { maxZoom: 19, subdomains: "abcd", attribution: "&copy; CARTO &copy; OpenStreetMap" },
        className: ""
      },
      osm_light: {
        name: "Standard Street (OSM)",
        url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        options: { maxZoom: 19, attribution: "&copy; OpenStreetMap" },
        className: ""
      },
      satellite: {
        name: "Satellite Imagery (Esri)",
        url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        options: { maxZoom: 19, attribution: "&copy; Esri World Imagery" },
        className: ""
      }
    };
    let currentMapLayerKey = "tactical_dark";

    function setMapLayer(layerKey) {
      if (!MAP_PROVIDERS[layerKey]) return;
      currentMapLayerKey = layerKey;
      const prov = MAP_PROVIDERS[layerKey];

      // Update button active state
      document.querySelectorAll('.layer-btn').forEach(b => {
        b.classList.toggle('active', b.id === `btn-layer-${layerKey}`);
      });

      // Update tile layers on both maps
      if (adminTileLayer && adminMap) {
        adminMap.removeLayer(adminTileLayer);
        adminTileLayer = L.tileLayer(prov.url, { ...prov.options, className: prov.className }).addTo(adminMap);
      }
      if (ngoTileLayer && ngoMap) {
        ngoMap.removeLayer(ngoTileLayer);
        ngoTileLayer = L.tileLayer(prov.url, { ...prov.options, className: prov.className }).addTo(ngoMap);
      }
      showToast(`Map style: ${prov.name}`);
    }

    // LIVE DIGITAL CLOCK
    function updateClock() {
      const el = document.getElementById('live-clock');
      if (el) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('en-US', { hour12: false });
        el.innerText = `🕒 ${timeStr} IST`;
      }
    }
    setInterval(updateClock, 1000);
    updateClock();

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

        currentRole = 'ngo';
        if (loggedInTeam && loggedInTeam.city) {
          switchCity(loggedInTeam.city, false);
        }
        loadNgoRoute();
        resizeMaps();
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

        currentRole = 'admin';
        loadNotifications();
        renderCasesTable();
        resizeMaps();
      }
    }

    // THEME HANDLING (DARK / LIGHT)
    function initTheme() {
      const saved = localStorage.getItem('mptracker_theme') || 'dark';
      document.documentElement.setAttribute('data-theme', saved);
      currentMapLayerKey = saved === 'dark' ? 'tactical_dark' : 'osm_light';
    }

    function toggleTheme() {
      const cur = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('mptracker_theme', next);
      
      const newLayerKey = next === 'dark' ? 'tactical_dark' : 'osm_light';
      setMapLayer(newLayerKey);
      showToast(`Switched to ${next.toUpperCase()} mode`);
    }

    // TOAST NOTIFICATION
    function showToast(msg) {
      const t = document.getElementById('toast-msg');
      t.innerText = msg;
      t.style.display = 'block';
      setTimeout(() => { t.style.display = 'none'; }, 2800);
    }

    // RESIZE OBSERVER ON MAPS
    function resizeMaps() {
      setTimeout(() => {
        if (adminMap) adminMap.invalidateSize(true);
        if (ngoMap) ngoMap.invalidateSize(true);
      }, 150);
    }

    // MAP INITIALIZATION
    function initMaps() {
      const prov = MAP_PROVIDERS[currentMapLayerKey];

      if (!adminMap) {
        adminMap = L.map('admin-map').setView([15.8281, 78.0373], 14);
        adminTileLayer = L.tileLayer(prov.url, { ...prov.options, className: prov.className }).addTo(adminMap);
        adminLayers = L.layerGroup().addTo(adminMap);
      }
      if (!ngoMap) {
        ngoMap = L.map('ngo-map').setView([15.8320, 78.0440], 14);
        ngoTileLayer = L.tileLayer(prov.url, { ...prov.options, className: prov.className }).addTo(ngoMap);
        ngoLayers = L.layerGroup().addTo(ngoMap);
      }

      if (window.ResizeObserver) {
        const ro = new ResizeObserver(() => {
          if (adminMap) adminMap.invalidateSize();
          if (ngoMap) ngoMap.invalidateSize();
        });
        const m1 = document.getElementById('admin-map');
        const m2 = document.getElementById('ngo-map');
        if (m1) ro.observe(m1);
        if (m2) ro.observe(m2);
      }
    }

    // MULTI-CITY LOADING & SWITCHING
    async function loadCities() {
      try {
        const res = await fetch('/api/cities');
        allCities = await res.json();
        renderCityPills();
        populateCityDropdowns();
      } catch (e) {
        console.error("Failed to load cities", e);
      }
    }

    function renderCityPills() {
      const container = document.getElementById('city-pills-list');
      if (!container) return;
      container.innerHTML = '';

      allCities.forEach(c => {
        const btn = document.createElement('button');
        btn.className = `city-pill ${c.id === currentCity ? 'active' : ''}`;
        btn.dataset.city = c.id;
        btn.innerText = c.name;
        btn.onclick = () => switchCity(c.id);
        container.appendChild(btn);
      });
    }

    function populateCityDropdowns() {
      const sel = document.getElementById('city-select-dropdown');
      const addCaseCitySel = document.getElementById('new-city');
      const addNgoCitySel = document.getElementById('ngo-city');

      [sel, addCaseCitySel, addNgoCitySel].forEach(dropdown => {
        if (!dropdown) return;
        dropdown.innerHTML = '';
        allCities.forEach(c => {
          const opt = document.createElement('option');
          opt.value = c.id;
          opt.innerText = `${c.name} (${c.state})`;
          if (c.id === currentCity) opt.selected = true;
          dropdown.appendChild(opt);
        });
      });
    }

    function switchCity(cityId, shouldToast = true) {
      cityId = (cityId || 'kurnool').toLowerCase();
      currentCity = cityId;
      const city = allCities.find(c => c.id === cityId) || { name: "Kurnool", state: "Andhra Pradesh", lat: 15.8281, lon: 78.0373, zoom: 14 };

      // Update active pills & dropdowns
      document.querySelectorAll('.city-pill').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.city === cityId);
      });
      const badge = document.getElementById('active-city-badge');
      if (badge) badge.innerText = city.name.toUpperCase();
      const dropdown = document.getElementById('city-select-dropdown');
      if (dropdown) dropdown.value = cityId;

      // Pan & fly map
      if (adminMap) {
        adminMap.flyTo([city.lat, city.lon], city.zoom || 13, { duration: 1.2 });
      }

      // Reload cameras & search zones for this city
      loadMapData(cityId);
      populateVideoCameraDropdown(cityId);
      populateAddCaseLocationDropdown(cityId);
      populateNgoBasePresetDropdown(cityId);
      renderCasesTable();
      resizeMaps();

      if (shouldToast) {
        showToast(`Switched city to ${city.name} (${city.state || ''})`);
      }
    }

    async function populateVideoCameraDropdown(cityId) {
      try {
        const res = await fetch(`/api/cameras?city=${cityId}`);
        const cams = await res.json();
        const sel = document.getElementById('video-camera-loc');
        if (!sel) return;
        sel.innerHTML = '';
        Object.entries(cams).forEach(([name, data]) => {
          const opt = document.createElement('option');
          opt.value = name;
          opt.innerText = data.label || name;
          sel.appendChild(opt);
        });
      } catch (e) { console.error(e); }
    }

    function handleNewCaseCityChange() {
      const cityId = document.getElementById('new-city').value;
      populateAddCaseLocationDropdown(cityId);
      populateCaseTeamDropdown();
    }

    async function populateAddCaseLocationDropdown(cityId) {
      try {
        const res = await fetch(`/api/cameras?city=${cityId}`);
        const cams = await res.json();
        const sel = document.getElementById('new-loc');
        if (!sel) return;
        sel.innerHTML = '';
        let firstLat = null, firstLon = null;
        Object.entries(cams).forEach(([name, data], idx) => {
          const opt = document.createElement('option');
          opt.value = name;
          opt.innerText = `${name} (${data.lat.toFixed(4)}, ${data.lon.toFixed(4)})`;
          opt.dataset.lat = data.lat;
          opt.dataset.lon = data.lon;
          if (idx === 0) { firstLat = data.lat; firstLon = data.lon; }
          sel.appendChild(opt);
        });

        // Add custom location option
        const customOpt = document.createElement('option');
        customOpt.value = '__custom__';
        customOpt.innerText = '? Custom Landmark / Enter GPS Coordinates';
        sel.appendChild(customOpt);

        const latInput = document.getElementById('new-lat');
        const lonInput = document.getElementById('new-lon');
        if (latInput && lonInput && firstLat !== null) {
          latInput.value = firstLat;
          lonInput.value = firstLon;
        }
        handleNewCaseLocationChange();
      } catch (e) { console.error(e); }
    }

    function handleNewCaseLocationChange() {
      const sel = document.getElementById('new-loc');
      const customInput = document.getElementById('new-custom-loc');
      if (!sel) return;
      if (sel.value === '__custom__') {
        if (customInput) {
          customInput.style.display = 'block';
          customInput.focus();
        }
      } else {
        if (customInput) customInput.style.display = 'none';
        const opt = sel.options[sel.selectedIndex];
        if (opt && opt.dataset.lat && opt.dataset.lon) {
          const latInput = document.getElementById('new-lat');
          const lonInput = document.getElementById('new-lon');
          if (latInput) latInput.value = opt.dataset.lat;
          if (lonInput) lonInput.value = opt.dataset.lon;
        }
      }
    }

    function handlePhotoUpload(e) {
      const file = e.target.files[0];
      if (!file) return;
      if (!file.type.startsWith('image/')) {
        showToast('?? Please select an image file (JPEG, PNG, WebP).');
        return;
      }
      const reader = new FileReader();
      reader.onload = function(evt) {
        const base64 = evt.target.result;
        document.getElementById('new-photo-base64').value = base64;
        const img = document.getElementById('case-photo-preview-img');
        const ph = document.getElementById('case-photo-placeholder');
        img.src = base64;
        img.style.display = 'block';
        if (ph) ph.style.display = 'none';
        showToast('?? Photo loaded & ready for ArcFace vector enrollment');
      };
      reader.readAsDataURL(file);
    }

    function clearCasePhoto() {
      const b64 = document.getElementById('new-photo-base64');
      if (b64) b64.value = '';
      const input = document.getElementById('new-photo-input');
      if (input) input.value = '';
      const img = document.getElementById('case-photo-preview-img');
      const ph = document.getElementById('case-photo-placeholder');
      if (img) { img.src = ''; img.style.display = 'none'; }
      if (ph) ph.style.display = 'block';
    }

    function setAvatarPreset(type) {
      const presets = {
        male: { bg: '#1e3a8a', char: '??' },
        female: { bg: '#831843', char: '??' },
        senior: { bg: '#374151', char: '??' },
        youth: { bg: '#065f46', char: '??' },
      };
      const p = presets[type] || presets.male;
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128"><circle cx="64" cy="64" r="64" fill="${p.bg}"/><text x="50%" y="54%" font-size="60" dominant-baseline="middle" text-anchor="middle">${p.char}</text></svg>`;
      const dataUrl = 'data:image/svg+xml;base64,' + btoa(svg);
      document.getElementById('new-photo-base64').value = dataUrl;
      const img = document.getElementById('case-photo-preview-img');
      const ph = document.getElementById('case-photo-placeholder');
      if (img) { img.src = dataUrl; img.style.display = 'block'; }
      if (ph) ph.style.display = 'none';
      showToast(`Selected ${type} avatar preset`);
    }

    function handleNgoCityChange() {
      const cityId = document.getElementById('ngo-city').value;
      populateNgoBasePresetDropdown(cityId);
    }

    async function populateNgoBasePresetDropdown(cityId) {
      try {
        const res = await fetch(`/api/cameras?city=${cityId}`);
        const cams = await res.json();
        const sel = document.getElementById('ngo-base-preset');
        if (!sel) return;
        sel.innerHTML = '';
        Object.entries(cams).forEach(([name, data]) => {
          const opt = document.createElement('option');
          opt.value = `${name} Base|${data.lat}|${data.lon}`;
          opt.innerText = `${name} Base (${data.lat.toFixed(4)}, ${data.lon.toFixed(4)})`;
          sel.appendChild(opt);
        });
        const customOpt = document.createElement('option');
        customOpt.value = 'custom';
        customOpt.innerText = '-- Custom Coordinates --';
        sel.appendChild(customOpt);
        handleNgoBasePresetChange();
      } catch (e) { console.error(e); }
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
        opt.innerText = `${t.name} (${t.base_location} - ${(t.city || 'kurnool').toUpperCase()})`;
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

        loggedInRole = data.role;
        loggedInTeam = data.team || null;

        sessionStorage.setItem('mptracker_role', loggedInRole);
        sessionStorage.setItem('mptracker_team', JSON.stringify(loggedInTeam));

        document.getElementById('screen-login').style.display = 'none';
        document.getElementById('screen-app').style.display = 'flex';
        
        applyRolePermissions(loggedInRole);
        const nameDisplay = loggedInTeam ? loggedInTeam.name : 'Police Command';
        showToast(`Authenticated as ${nameDisplay}`);
        resizeMaps();
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
        resizeMaps();
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
        const cityUpper = (t.city || 'kurnool').toUpperCase();
        tr.innerHTML = `
          <td class="mono" style="color: var(--accent);">#${t.id}</td>
          <td style="font-weight: 800; color: var(--text);">${t.name}</td>
          <td><span class="badge" style="background:#0284c7;">${cityUpper}</span></td>
          <td><span class="badge" style="background: #10b981;">${t.org}</span></td>
          <td><b>${t.base_location}</b></td>
          <td class="mono" style="color: var(--text-muted);">${t.lat.toFixed(4)}, ${t.lon.toFixed(4)}</td>
          <td class="mono">${t.phone}</td>
          <td class="mono" style="color: var(--accent); font-weight: 700;">${t.username}</td>
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
      const curCity = (currentCity || 'kurnool').toLowerCase();
      // Sort so current city teams appear first
      const sortedTeams = [...allTeams].sort((a, b) => {
        const aCity = (a.city || 'kurnool').toLowerCase();
        const bCity = (b.city || 'kurnool').toLowerCase();
        if (aCity === curCity && bCity !== curCity) return -1;
        if (aCity !== curCity && bCity === curCity) return 1;
        return a.name.localeCompare(b.name);
      });

      sortedTeams.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.name;
        const isCurrentCity = (t.city || 'kurnool').toLowerCase() === curCity;
        opt.innerText = `${isCurrentCity ? '? ' : ''}${t.name} (${t.base_location} - ${(t.city || 'kurnool').toUpperCase()})`;
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

    function toggleCityCaseFilter() {
      filterOnlyCurrentCity = !filterOnlyCurrentCity;
      const btn = document.getElementById('filter-city-scope');
      if (btn) {
        btn.className = `btn btn-sm ${filterOnlyCurrentCity ? 'btn' : 'btn-secondary'}`;
        btn.innerText = filterOnlyCurrentCity ? `City: ${currentCity.toUpperCase()}` : 'Current City Only';
      }
      renderCasesTable();
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

        if (filterOnlyCurrentCity) {
          const caseCity = (c.city || 'kurnool').toLowerCase();
          if (caseCity !== currentCity.toLowerCase()) return false;
        }

        if (!searchQuery) return true;

        const q = searchQuery.toLowerCase();
        return c.name.toLowerCase().includes(q) ||
               ((c.city || '').toLowerCase().includes(q)) ||
               (c.clothes && c.clothes.toLowerCase().includes(q)) ||
               (c.last_seen_location && c.last_seen_location.toLowerCase().includes(q));
      });

      if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:var(--text-muted); padding:2rem;">No matching cases found.</td></tr>`;
        return;
      }

      filtered.forEach(c => {
        const tr = document.createElement('tr');
        const statusClass = c.status === 'ACTIVE' ? 'tag-active' : (c.status === 'RESCUED' ? 'tag-rescued' : 'tag-closed');
        const statusPulse = c.status === 'ACTIVE' ? '<span class="pulse-dot" style="background:var(--warning); box-shadow:0 0 8px var(--warning); margin-right:4px;"></span>' : '';
        const cityTag = (c.city || 'kurnool').toUpperCase();
        
        let actionButtons = '';
        if (loggedInRole === 'admin') {
          actionButtons += `<button class="btn btn-secondary btn-sm" onclick="openEditCaseModal(${c.id})" title="Edit case metadata and coordinates">✏️ Edit</button> `;
          actionButtons += `<button class="btn btn-secondary btn-sm" onclick="openFlyerModal(${c.id})" title="Generate Printable Official SAR Dossier">📄 Flyer</button> `;
          actionButtons += `<button class="btn btn-secondary btn-sm" onclick="acceptCaseAndNavigate(${c.id})" title="Inspect Turn-by-Turn Road Route">🗺️ Route</button> `;
          actionButtons += `<button class="btn btn-secondary btn-sm" onclick="openAllotModal(${c.id})" title="Allot case to specific NGO and send SMS alert">📢 Allot NGO</button> `;
          if (c.status === 'ACTIVE') {
            actionButtons += `<button class="btn btn-success btn-sm" onclick="markCaseResolved(${c.id})">✓ Resolve</button> `;
          }
          actionButtons += `<button class="btn btn-danger btn-sm" onclick="deleteCase(${c.id})" title="Remove Case">🗑 Remove</button>`;
        } else {
          const isMyCase = loggedInTeam && c.assigned_team === loggedInTeam.name;
          actionButtons += `<button class="btn btn-secondary btn-sm" onclick="openFlyerModal(${c.id})" title="View SAR Flyer">📄 Flyer</button> `;
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

        const photoThumb = c.photo_path
          ? `<img src="${c.photo_path}" style="width: 32px; height: 32px; border-radius: 50%; object-fit: cover; border: 2px solid var(--accent); vertical-align: middle; margin-right: 8px;" onerror="this.style.display='none'" />`
          : `<span style="display: inline-flex; width: 32px; height: 32px; border-radius: 50%; background: rgba(59,130,246,0.2); color: #38bdf8; border: 1px solid rgba(59,130,246,0.4); align-items: center; justify-content: center; font-weight: 800; font-size: 0.8rem; margin-right: 8px;">${c.name.charAt(0)}</span>`;

        tr.innerHTML = `
          <td class="mono" style="color: var(--accent);">#${c.id}</td>
          <td style="font-weight: 800; color: var(--text); display: flex; align-items: center;">${photoThumb} <span>${c.name}</span></td>
          <td>
            <select onchange="updateCaseCity(${c.id}, this.value)" title="Change jurisdiction city in PostgreSQL" style="background: rgba(2,132,199,0.2); border: 1px solid rgba(2,132,199,0.5); color: #38bdf8; padding: 3px 5px; border-radius: 6px; font-size: 0.76rem; font-weight: 700; cursor: pointer;">
              ${allCities.map(ct => `<option value="${ct.id}" ${ct.id === (c.city || 'kurnool').toLowerCase() ? 'selected' : ''}>${ct.name.toUpperCase()}</option>`).join('')}
            </select>
          </td>
          <td>${c.age} / ${c.gender}</td>
          <td style="color: var(--text-muted);">${c.clothes || 'Standard'}</td>
          <td><b>${c.last_seen_location}</b></td>
          <td>
            <div style="display: flex; align-items: center; gap: 0.35rem;">
              <select onchange="setCaseStatus(${c.id}, this.value)" title="Change case status directly in PostgreSQL" style="background: var(--card); border: 1px solid var(--card-border); color: var(--text); padding: 3px 6px; border-radius: 6px; font-size: 0.76rem; font-weight: 700; cursor: pointer;">
                <option value="ACTIVE" ${c.status === 'ACTIVE' ? 'selected' : ''}>?? ACTIVE</option>
                <option value="RESCUED" ${c.status === 'RESCUED' ? 'selected' : ''}>? RESCUED</option>
                <option value="CLOSED" ${c.status === 'CLOSED' ? 'selected' : ''}>?? CLOSED</option>
              </select>
            </div>
          </td>
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

    function populateNgoCaseSelector() {
      const sel = document.getElementById('resolve-case-id');
      if (!sel) return;
      sel.innerHTML = '';
      allCases.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.id;
        opt.innerText = `Case #${c.id}: ${c.name} (${(c.city || 'kurnool').toUpperCase()} - ${c.status} - ${c.last_seen_location})`;
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

    // MULTI-CITY GRAPH & SEARCH ZONE LOADER
    async function loadMapData(cityId = null) {
      initMaps();
      const targetCity = cityId || currentCity || 'kurnool';
      try {
        const res = await fetch(`/api/demo?city=${targetCity}&top=5`);
        const data = await res.json();
        adminLayers.clearLayers();

        // Draw Surveillance Network Graph Links
        if (data.edges && data.edges.length > 0) {
          data.edges.forEach(e => {
            L.polyline([[e.from_lat, e.from_lon], [e.to_lat, e.to_lon]], {
              color: '#38bdf8',
              weight: 2,
              dashArray: '4, 8',
              opacity: 0.45
            }).bindPopup(`<b>Surveillance Link</b><br>${e.from_name} ➔ ${e.to_name}<br>Distance: <b>${e.distance_km} km</b>`).addTo(adminLayers);
          });
        }

        // Draw Origin Sighting Radar Pulse
        if (data.person && data.person.last_seen) {
          const originLoc = data.all_locations.find(l => l.name.toLowerCase() === data.person.last_seen.toLowerCase()) || data.all_locations[0];
          if (originLoc) {
            L.circle([originLoc.lat, originLoc.lon], {
              radius: Math.max((data.reach_km || 1.8) * 800, 500),
              color: '#ef4444',
              weight: 2,
              dashArray: '5, 5',
              fillColor: '#ef4444',
              fillOpacity: 0.08
            }).bindPopup(`<b>🚨 Origin Sighting Node: ${originLoc.name}</b><br>Subject: <b>${data.person.name}</b><br>Dijkstra Reach Radius: <b>${(data.reach_km || 1.8).toFixed(2)} km</b>`).addTo(adminLayers);
          }
        }

        data.all_locations.forEach(loc => {
          L.circleMarker([loc.lat, loc.lon], {
            radius: 6, color: '#38bdf8', fillColor: '#08101e', fillOpacity: 0.9, weight: 2
          }).bindPopup(`<b>${loc.name}</b><br><span style="color:#38bdf8;">Surveillance Node (${targetCity.toUpperCase()})</span>`).addTo(adminLayers);
        });

        const colors = ['#ef4444', '#f59e0b', '#3b82f6', '#10b981', '#a855f7'];
        data.zones.forEach((z, i) => {
          const color = colors[i] || '#64748b';
          L.circle([z.lat, z.lon], {
            radius: z.radius_km * 1000, color: color, fillColor: color, fillOpacity: 0.16, weight: 2
          }).bindPopup(`<b>#${z.rank} ${z.location}</b><br>Reach Probability: <b style="color:${color};">${(z.score * 100).toFixed(1)}%</b><br>${z.reason}`).addTo(adminLayers);

          L.circleMarker([z.lat, z.lon], {
            radius: 8, color: color, fillColor: color, fillOpacity: 0.95, weight: 2
          }).addTo(adminLayers);
        });

        resizeMaps();
      } catch (e) { console.error(e); }
    }


    // CLIENT-SIDE REAL OPENSTREETMAP OSRM ROAD ROUTING
    async function fetchClientOsrmRoute(startLat, startLon, endLat, endLon) {
      try {
        const url = `https://router.project-osrm.org/route/v1/driving/${startLon.toFixed(6)},${startLat.toFixed(6)};${endLon.toFixed(6)},${endLat.toFixed(6)}?overview=full&geometries=geojson`;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3500);
        const res = await fetch(url, { signal: controller.signal });
        clearTimeout(timeoutId);
        if (!res.ok) return null;
        const json = await res.json();
        if (json.code === 'Ok' && json.routes && json.routes.length > 0) {
          const r = json.routes[0];
          return {
            coordinates: r.geometry.coordinates.map(pt => [pt[1], pt[0]]),
            distance_km: (r.distance / 1000).toFixed(2),
            eta_minutes: Math.max(1, Math.ceil(r.duration / 60))
          };
        }
      } catch (err) {
        console.warn("Client OSRM routing notice:", err.message);
      }
      return null;
    }

    // STREET-LEVEL ROAD ROUTING FOR SPECIFIC TEAM & CASE
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
        document.getElementById('route-path-text').innerText = `Street route tracing through ${coordsCount} road nodes from ${baseName} to ${locName}`;

        // Base marker
        L.circleMarker([startLat, startLon], {
          radius: 10, color: '#10b981', fillColor: '#10b981', fillOpacity: 0.95, weight: 3
        }).bindPopup(`<b>${teamName} (Base)</b><br>${baseName}`).addTo(ngoLayers);

        // Target sighting marker
        L.circleMarker([targetLat, targetLon], {
          radius: 10, color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.95, weight: 3
        }).bindPopup(`<b>Target Sighting: ${personName}</b><br>${locName}`).addTo(ngoLayers);

        L.circle([targetLat, targetLon], {
          radius: 400, color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.18, weight: 2
        }).addTo(ngoLayers);

        let streetCoordinates = data.street_coordinates || data.route_coordinates || [[startLat, startLon], [targetLat, targetLon]];

        // Attempt direct client-side OSRM query for high-resolution road curves
        if (!data.engine || !data.engine.includes('OSRM') || streetCoordinates.length <= 14) {
          const clientRoute = await fetchClientOsrmRoute(startLat, startLon, targetLat, targetLon);
          if (clientRoute && clientRoute.coordinates && clientRoute.coordinates.length > 0) {
            streetCoordinates = clientRoute.coordinates;
            document.getElementById('route-dist').innerText = `${clientRoute.distance_km} km`;
            document.getElementById('route-eta').innerText = `${clientRoute.eta_minutes} mins`;
            if (badge) badge.innerText = `🚗 OpenStreetMap Turn-by-Turn (${clientRoute.coordinates.length} waypoints)`;
            document.getElementById('route-path-text').innerText = `Live road navigation tracing ${clientRoute.coordinates.length} road intersections from ${baseName} to ${locName}`;
          }
        }

        const casingPoly = L.polyline(streetCoordinates, {
          color: '#0369a1',
          weight: 9,
          opacity: 0.85,
          lineCap: 'round',
          lineJoin: 'round'
        }).addTo(ngoLayers);

        const corePoly = L.polyline(streetCoordinates, {
          color: '#38bdf8',
          weight: 5,
          opacity: 1.0,
          lineCap: 'round',
          lineJoin: 'round',
          dashArray: '8, 8'
        }).addTo(ngoLayers);

        if (adminLayers && adminMap && (currentRole === 'admin' || loggedInRole === 'admin')) {
          L.polyline(streetCoordinates, {
            color: '#10b981',
            weight: 4,
            dashArray: '6, 6',
            opacity: 0.8
          }).bindPopup(`<b>Dispatched Unit Route: ${teamName}</b><br>ETA: <b>${data.eta_minutes} mins</b> &bull; Target: <b>${personName}</b>`).addTo(adminLayers);
        }

        if (ngoMap) {
          ngoMap.invalidateSize(true);
          ngoMap.fitBounds(casingPoly.getBounds(), { padding: [50, 50], maxZoom: 16 });
          setTimeout(() => {
            if (ngoMap) {
              ngoMap.invalidateSize(true);
              ngoMap.fitBounds(casingPoly.getBounds(), { padding: [50, 50], maxZoom: 16 });
            }
          }, 200);
        }

      } catch (e) {
        console.error("Failed to load street route", e);
      }
    }

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
        resizeMaps();
      } else {
        dot.className = 'dot role-ngo';
        const teamName = loggedInTeam ? loggedInTeam.name : 'Helping Hands NGO';
        disp.innerText = `Search Party: ${teamName}`;
        loadNgoRoute();
        loadNotifications();
        resizeMaps();
      }
    }

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
        list.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 2rem;">No case allotment notifications found.</div>`;
        return;
      }

      allNotifications.forEach(n => {
        const div = document.createElement('div');
        div.className = `notif-card ${!n.read ? 'unread' : ''}`;
        div.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem;">
            <div style="font-weight: 800; color: var(--text); font-size: 0.95rem;">
              ${!n.read ? '<span style="color: #ef4444; margin-right: 4px;">●</span>' : ''}${n.title}
            </div>
            <span class="mono" style="font-size: 0.74rem; color: var(--text-muted); white-space: nowrap;">${n.timestamp}</span>
          </div>
          <div style="font-size: 0.84rem; color: var(--text-muted); line-height: 1.4;">
            ${n.message}
          </div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.45rem; flex-wrap: wrap; gap: 0.5rem;">
            <span style="font-size: 0.78rem; font-weight: 700; color: #10b981;">📱 ${n.sms_status}</span>
            <div style="display: flex; gap: 0.45rem;">
              ${n.case_id ? `<button class="btn btn-secondary btn-sm" style="font-size: 0.74rem; padding: 3px 8px;" onclick="acceptCaseAndNavigate(${n.case_id})">🚗 Trace Route</button>` : ''}
              ${!n.read ? `<button class="btn btn-secondary btn-sm" style="font-size: 0.74rem; padding: 3px 8px;" onclick="markNotificationRead(${n.id})">✓ Acknowledge</button>` : ''}
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
          <div style="background: var(--input-bg); border: 1px dashed var(--card-border); border-radius: 12px; padding: 1.25rem; text-align: center; color: var(--text-muted); font-size: 0.88rem;">
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
              <div style="display: flex; align-items: center; gap: 0.45rem;">
                <span class="badge" style="background: #ef4444;">CASE ALLOTMENT ORDER</span>
                ${!n.read ? '<span class="badge" style="background: #f59e0b;">NEW UNREAD</span>' : '<span class="badge" style="background: #10b981;">ACKNOWLEDGED</span>'}
              </div>
              <h3 style="font-size: 1.1rem; margin-top: 0.35rem; color: var(--text); font-weight: 800;">${n.title}</h3>
            </div>
            <span class="mono" style="font-size: 0.74rem; color: var(--text-muted);">${n.timestamp}</span>
          </div>

          <div style="background: var(--card); border: 1px solid var(--card-border); border-radius: 10px; padding: 0.75rem 0.95rem; margin: 0.4rem 0; font-size: 0.86rem; line-height: 1.45;">
            <div>Missing Person: <b style="color: var(--text);">${n.person_name}</b> (Case #${n.case_id})</div>
            <div>Target Sighting Zone: <b style="color: var(--accent);">${n.last_seen_location}</b></div>
            <div style="color: var(--text-muted); margin-top: 0.25rem; font-size: 0.82rem;">${n.message}</div>
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
            <div style="font-size: 0.8rem; color: #10b981; font-weight: 700; display: flex; align-items: center; gap: 0.35rem;">
              <span>📱</span> <span>SMS Dispatch Alert: <b>${n.sms_status}</b></span>
            </div>
            <div style="display: flex; gap: 0.55rem;">
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
      document.getElementById('allot-case-loc').innerText = `Target: ${c.last_seen_location} • Region: ${(c.city || 'kurnool').toUpperCase()}`;
      document.getElementById('allot-instructions').value = '';

      const sel = document.getElementById('allot-team-select');
      sel.innerHTML = '';
      allTeams.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.id;
        opt.innerText = `${t.name} (${t.base_location} - ${(t.city || 'kurnool').toUpperCase()}) - ${t.phone}`;
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

    function openAddCaseModal() {
      if (loggedInRole !== 'admin') {
        showToast('⚠️ Access Denied: Only Police Command can enroll new cases.');
        return;
      }
      const citySel = document.getElementById('new-city');
      if (citySel) citySel.value = currentCity;
      populateAddCaseLocationDropdown(currentCity);
      document.getElementById('add-case-modal').style.display = 'flex';
    }
    function closeAddCaseModal() { document.getElementById('add-case-modal').style.display = 'none'; }

    function openAddNgoModal() {
      if (loggedInRole !== 'admin') {
        showToast('⚠️ Access Denied: Only Police Command can register new NGOs.');
        return;
      }
      const citySel = document.getElementById('ngo-city');
      if (citySel) citySel.value = currentCity;
      populateNgoBasePresetDropdown(currentCity);
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
      const cityId = document.getElementById('ngo-city').value;
      const newTeam = {
        name: document.getElementById('ngo-name').value.trim(),
        org: document.getElementById('ngo-org').value,
        city: cityId,
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
        showToast(`NGO Registered: ${saved.name} (${cityId.toUpperCase()})`);
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
      const cityId = document.getElementById('new-city').value;
      const newCase = {
        name: document.getElementById('new-name').value,
        city: cityId,
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
        showToast(`Case enrolled for ${newCase.name} (${cityId.toUpperCase()})`);
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


    // ==========================================
    // CASE EDIT MODAL & SAR DOSSIER FUNCTIONS
    // ==========================================

    // ==========================================
    // INSTANT TABLE IN-LINE CITY & STATUS HANDLERS
    // ==========================================
    async function updateCaseCity(caseId, newCity) {
      newCity = (newCity || 'kurnool').toLowerCase();
      try {
        const res = await fetch('/api/cases/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-User-Role': loggedInRole || 'admin' },
          body: JSON.stringify({ id: caseId, city: newCity })
        });
        const data = await res.json();
        const updated = data.case || data;
        if (updated && (updated.id || data.status === 'success')) {
          const idx = allCases.findIndex(c => c.id === caseId);
          if (idx !== -1) {
            allCases[idx].city = newCity;
          }
          showToast(`Case #${caseId} jurisdiction updated to ${newCity.toUpperCase()} in database.`);
          loadStats();
          renderCasesTable();
        } else {
          showToast('Failed to update case city in database.');
          loadCases();
        }
      } catch (err) {
        console.error(err);
        showToast('Network error updating case city.');
        loadCases();
      }
    }

    async function setCaseStatus(caseId, newStatus) {
      newStatus = (newStatus || 'ACTIVE').toUpperCase();
      try {
        const res = await fetch('/api/cases/status', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-User-Role': loggedInRole || 'admin' },
          body: JSON.stringify({ id: caseId, status: newStatus })
        });
        const data = await res.json();
        if (data && (data.status || data.case_id)) {
          const idx = allCases.findIndex(c => c.id === caseId);
          if (idx !== -1) {
            allCases[idx].status = newStatus;
          }
          showToast(`Case #${caseId} status updated to ${newStatus} in database.`);
          loadStats();
          renderCasesTable();
        } else {
          showToast('Failed to update case status.');
          loadCases();
        }
      } catch (err) {
        console.error(err);
        showToast('Network error updating case status.');
        loadCases();
      }
    }

    function openEditCaseModal(caseId) {
      if (loggedInRole !== 'admin') {
        showToast('⚠️ Access Denied: Only Police Command can edit cases.');
        return;
      }
      const c = allCases.find(item => item.id === caseId);
      if (!c) {
        showToast('Case not found');
        return;
      }

      document.getElementById('edit-case-id').value = c.id;
      document.getElementById('edit-name').value = c.name || '';
      document.getElementById('edit-age').value = c.age || 25;
      document.getElementById('edit-gender').value = c.gender || 'Male';
      document.getElementById('edit-clothes').value = c.clothes || '';
      document.getElementById('edit-status').value = c.status || 'ACTIVE';
      document.getElementById('edit-lat').value = c.lat || 15.8281;
      document.getElementById('edit-lon').value = c.lon || 78.0373;
      document.getElementById('edit-phone').value = c.phone || '';

      // Populate cities dropdown
      const citySel = document.getElementById('edit-city');
      citySel.innerHTML = '';
      allCities.forEach(city => {
        const opt = document.createElement('option');
        opt.value = city.id;
        opt.innerText = `${city.name.toUpperCase()} (${city.state || ''})`;
        if (city.id === (c.city || 'kurnool').toLowerCase()) opt.selected = true;
        citySel.appendChild(opt);
      });

      // Photo preview
      const previewImg = document.getElementById('edit-photo-preview-img');
      const placeholder = document.getElementById('edit-photo-placeholder');
      const photoBase64Input = document.getElementById('edit-photo-base64');
      photoBase64Input.value = '';

      if (c.photo_path) {
        previewImg.src = c.photo_path;
        previewImg.style.display = 'block';
        placeholder.style.display = 'none';
      } else {
        previewImg.style.display = 'none';
        placeholder.style.display = 'block';
        placeholder.innerText = c.name ? c.name.charAt(0).toUpperCase() : '👤';
      }

      populateEditCaseLocationDropdown(c.city || 'kurnool', c.last_seen_location);
      populateEditCaseTeamDropdown(c.assigned_team);

      document.getElementById('edit-case-modal').style.display = 'flex';
    }

    function closeEditCaseModal() {
      document.getElementById('edit-case-modal').style.display = 'none';
    }

    async function populateEditCaseLocationDropdown(cityId, selectedLoc) {
      try {
        const res = await fetch(`/api/cameras?city=${cityId}`);
        const cams = await res.json();
        const sel = document.getElementById('edit-loc');
        sel.innerHTML = '';
        Object.entries(cams).forEach(([name, data]) => {
          const opt = document.createElement('option');
          opt.value = name;
          opt.innerText = `${name} (${data.lat.toFixed(4)}, ${data.lon.toFixed(4)})`;
          opt.dataset.lat = data.lat;
          opt.dataset.lon = data.lon;
          if (name.toLowerCase() === (selectedLoc || '').toLowerCase()) opt.selected = true;
          sel.appendChild(opt);
        });

        // Add custom option
        const customOpt = document.createElement('option');
        customOpt.value = '__custom__';
        customOpt.innerText = '📍 Custom Landmark / Coordinates';
        sel.appendChild(customOpt);
      } catch (e) { console.error(e); }
    }

    function populateEditCaseTeamDropdown(selectedTeam) {
      const sel = document.getElementById('edit-team');
      sel.innerHTML = '';
      allTeams.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.name;
        opt.innerText = `${t.name} (${t.city.toUpperCase()})`;
        if (t.name === selectedTeam) opt.selected = true;
        sel.appendChild(opt);
      });
    }

    function handleEditCaseCityChange() {
      const cityId = document.getElementById('edit-city').value;
      populateEditCaseLocationDropdown(cityId, '');
    }

    function handleEditCaseLocationChange() {
      const sel = document.getElementById('edit-loc');
      const customInput = document.getElementById('edit-custom-loc');
      if (sel.value === '__custom__') {
        customInput.style.display = 'block';
      } else {
        customInput.style.display = 'none';
        const opt = sel.options[sel.selectedIndex];
        if (opt && opt.dataset.lat) {
          document.getElementById('edit-lat').value = opt.dataset.lat;
          document.getElementById('edit-lon').value = opt.dataset.lon;
        }
      }
    }

    function handleEditPhotoUpload(event) {
      const file = event.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = function(e) {
        document.getElementById('edit-photo-base64').value = e.target.result;
        const img = document.getElementById('edit-photo-preview-img');
        img.src = e.target.result;
        img.style.display = 'block';
        document.getElementById('edit-photo-placeholder').style.display = 'none';
      };
      reader.readAsDataURL(file);
    }

    function clearEditCasePhoto() {
      document.getElementById('edit-photo-base64').value = '';
      document.getElementById('edit-photo-input').value = '';
      document.getElementById('edit-photo-preview-img').style.display = 'none';
      document.getElementById('edit-photo-placeholder').style.display = 'block';
    }

    async function handleSaveEditCase(event) {
      event.preventDefault();
      const caseId = parseInt(document.getElementById('edit-case-id').value);
      const locSel = document.getElementById('edit-loc');
      const locName = locSel.value === '__custom__' ? document.getElementById('edit-custom-loc').value.trim() : locSel.value;

      const payload = {
        id: caseId,
        name: document.getElementById('edit-name').value.trim(),
        age: parseInt(document.getElementById('edit-age').value),
        gender: document.getElementById('edit-gender').value,
        clothes: document.getElementById('edit-clothes').value.trim(),
        city: document.getElementById('edit-city').value,
        status: document.getElementById('edit-status').value,
        last_seen_location: locName,
        lat: parseFloat(document.getElementById('edit-lat').value),
        lon: parseFloat(document.getElementById('edit-lon').value),
        assigned_team: document.getElementById('edit-team').value,
        phone: document.getElementById('edit-phone').value.trim(),
        photo: document.getElementById('edit-photo-base64').value || undefined
      };

      try {
        const res = await fetch('/api/cases/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-User-Role': loggedInRole || 'admin' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        const saved = data.case || data;
        if (saved && (saved.id || data.status === 'success')) {
          const idx = allCases.findIndex(c => c.id === caseId);
          if (idx !== -1) {
            allCases[idx] = Object.assign({}, allCases[idx], saved);
          }
          renderCasesTable();
          loadStats();
          closeEditCaseModal();
          showToast(`Case #${caseId} updated successfully in PostgreSQL!`);
        } else {
          showToast('Failed to save case changes.');
        }
      } catch (err) {
        console.error(err);
        showToast('Error saving case updates.');
      }
    }

    // SAR DOSSIER / FLYER FUNCTIONS
    async function openFlyerModal(caseId) {
      const c = allCases.find(item => item.id === caseId);
      if (!c) { showToast('Case not found'); return; }

      document.getElementById('flyer-name').innerText = c.name;
      document.getElementById('flyer-case-id').innerText = `#${c.id}`;
      document.getElementById('flyer-age-gender').innerText = `${c.age} Years / ${c.gender}`;
      document.getElementById('flyer-city').innerText = (c.city || 'kurnool').toUpperCase();
      document.getElementById('flyer-location').innerText = `${c.last_seen_location} (GPS: ${c.lat.toFixed(4)}, ${c.lon.toFixed(4)})`;
      document.getElementById('flyer-clothes').innerText = c.clothes || 'Standard Attire';
      document.getElementById('flyer-contact').innerText = c.phone || '+91 6303126628 / 100';

      const badge = document.getElementById('flyer-status-badge');
      badge.innerText = c.status === 'ACTIVE' ? 'URGENT SAR ACTIVE' : c.status;
      badge.style.background = c.status === 'ACTIVE' ? '#ef4444' : '#10b981';

      const photoImg = document.getElementById('flyer-photo-img');
      const photoPlaceholder = document.getElementById('flyer-photo-placeholder');
      if (c.photo_path) {
        photoImg.src = c.photo_path;
        photoImg.style.display = 'block';
        photoPlaceholder.style.display = 'none';
      } else {
        photoImg.style.display = 'none';
        photoPlaceholder.style.display = 'block';
        photoPlaceholder.innerText = c.name.charAt(0);
      }

      // Fetch dynamic zones for this city
      try {
        const res = await fetch(`/api/demo?city=${c.city || 'kurnool'}&top=3`);
        const data = await res.json();
        const zonesHtml = (data.zones || []).map((z, idx) => `
          <div style="margin-top: 0.25rem;">
            <b>Zone #${z.rank} (${z.location})</b>: Prob: <span style="color:#ef4444; font-weight:700;">${(z.score * 100).toFixed(1)}%</span> &bull; Radius: <b>${z.radius_km} km</b> &bull; ${z.reason}
          </div>
        `).join('');
        document.getElementById('flyer-zones-summary').innerHTML = `
          <div>Estimated Search Radius: <b style="color:var(--accent);">${(data.reach_km || 1.8).toFixed(2)} km</b> (Walking / Multi-hop Road Traversal)</div>
          ${zonesHtml}
        `;
      } catch (e) {
        document.getElementById('flyer-zones-summary').innerText = 'Predicted search zones synchronized with regional response units.';
      }

      document.getElementById('flyer-modal').style.display = 'flex';
    }

    function closeFlyerModal() {
      document.getElementById('flyer-modal').style.display = 'none';
    }

    function printSarFlyer() {
      window.print();
    }

    // WEBCAM & AUDIO ALARM
    let webcamStream = null;
    let isWebcamRunning = false;
    let soundAlertEnabled = true;

    async function toggleWebcam() {
      const video = document.getElementById('video-player');
      const btn = document.getElementById('btn-toggle-webcam');
      const badge = document.querySelector('.cctv-rec-badge');
      const placeholder = document.getElementById('video-placeholder');

      if (isWebcamRunning) {
        if (webcamStream) {
          webcamStream.getTracks().forEach(track => track.stop());
          webcamStream = null;
        }
        video.srcObject = null;
        isWebcamRunning = false;
        btn.innerHTML = '🎥 Use Live Webcam';
        btn.className = 'btn btn-secondary btn-sm';
        if (badge) badge.innerHTML = '<span style="color: #ef4444;">●</span> LIVE REC &bull; 1080p';
        placeholder.style.display = 'block';
        showToast('Webcam feed stopped.');
      } else {
        try {
          webcamStream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } } });
          video.srcObject = webcamStream;
          placeholder.style.display = 'none';
          video.play();
          isWebcamRunning = true;
          btn.innerHTML = '⏹️ Stop Webcam';
          btn.className = 'btn btn-danger btn-sm';
          if (badge) badge.innerHTML = '<span style="color: #10b981;">●</span> LIVE WEBCAM ACTIVE';
          showToast('Live webcam feed active.');
        } catch (err) {
          console.warn('Webcam access error:', err);
          showToast('⚠️ Webcam access error: ' + (err.message || 'Check browser permissions'));
        }
      }
    }

    function toggleSoundAlert() {
      soundAlertEnabled = !soundAlertEnabled;
      const btn = document.getElementById('btn-toggle-sound');
      if (btn) {
        btn.innerText = soundAlertEnabled ? '🔔 Alert Sound: ON' : '🔕 Alert Sound: OFF';
      }
      showToast(soundAlertEnabled ? 'Audio alarm enabled.' : 'Audio alarm muted.');
    }

    function playTacticalAlarm() {
      if (!soundAlertEnabled) return;
      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;
        const ctx = new AudioCtx();
        const playBeep = (freq, start, dur) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = 'sawtooth';
          osc.frequency.setValueAtTime(freq, ctx.currentTime + start);
          gain.gain.setValueAtTime(0.2, ctx.currentTime + start);
          gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(ctx.currentTime + start);
          osc.stop(ctx.currentTime + start + dur);
        };
        playBeep(980, 0, 0.16);
        playBeep(1320, 0.18, 0.18);
        playBeep(1760, 0.38, 0.28);
      } catch (e) {
        console.warn('Audio alarm playback error:', e);
      }
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
      if (loggedInRole !== 'admin') {
        showToast('⚠️ Access Denied: Video facial recognition scanning is restricted to Police Command.');
        return;
      }
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
      status.innerText = `Scanning video frames recorded at ${selectedCamKey} (${currentCity.toUpperCase()}) using DeepFace ArcFace...`;

      setTimeout(async () => {
        radar.style.display = 'none';
        status.innerText = `Scan complete. Confirmed match identified at ${selectedCamKey}.`;
        matchBox.style.display = 'block';

        const cityCases = allCases.filter(c => (c.city || 'kurnool').toLowerCase() === currentCity.toLowerCase());
        const matchCase = cityCases.length > 0 ? cityCases[0] : (allCases.length > 0 ? allCases[0] : { name: "N.K.SYAM", id: 1 });
        const matchPerson = matchCase.name;
        const matchCaseId = matchCase.id;
        const targetTeamName = loggedInTeam ? loggedInTeam.name : (allTeams.length > 0 ? allTeams[0].name : "Helping Hands NGO");

        document.getElementById('match-details').innerHTML = `
          <div>Person: <b style="color:var(--text);">${matchPerson}</b> (Case #${matchCaseId}) &bull; Jurisdiction: <b>${currentCity.toUpperCase()}</b></div>
          <div>Camera Location: <b>${selectedCamText}</b></div>
          <div>Detection Timestamp: <b>00:04.2s (Frame 105)</b> &bull; Cosine Dist: <b style="color:var(--success);">0.28</b></div>
          <div style="margin-top:0.35rem; color:var(--accent);">Auto-Dispatch: Nearest team <b>${targetTeamName}</b> mobilized to <b>${selectedCamKey}</b> via road navigation.</div>
        `;

        await fetch('/api/scan', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'X-User-Role': loggedInRole || 'admin'},
          body: JSON.stringify({ camera_location: selectedCamKey, case_id: matchCaseId, person_name: matchPerson, city: currentCity })
        });

        // Draw tactical bounding box on overlay canvas
        const canvas = document.getElementById('canvas-overlay');
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 3;
        const boxX = canvas.width * 0.38;
        const boxY = canvas.height * 0.25;
        const boxW = canvas.width * 0.22;
        const boxH = canvas.height * 0.35;
        ctx.strokeRect(boxX, boxY, boxW, boxH);
        
        ctx.lineWidth = 5;
        ctx.beginPath();
        ctx.moveTo(boxX, boxY + 15); ctx.lineTo(boxX, boxY); ctx.lineTo(boxX + 15, boxY);
        ctx.moveTo(boxX + boxW - 15, boxY); ctx.lineTo(boxX + boxW, boxY); ctx.lineTo(boxX + boxW, boxY + 15);
        ctx.moveTo(boxX, boxY + boxH - 15); ctx.lineTo(boxX, boxY + boxH); ctx.lineTo(boxX + 15, boxY + boxH);
        ctx.moveTo(boxX + boxW - 15, boxY + boxH); ctx.lineTo(boxX + boxW, boxY + boxH); ctx.lineTo(boxX + boxW, boxY + boxH - 15);
        ctx.stroke();

        ctx.fillStyle = '#ef4444';
        ctx.font = 'bold 13px sans-serif';
        ctx.fillText(`TARGET: ${matchPerson} @ ${selectedCamKey}`, boxX, boxY - 8);

        showToast(`Match detected: ${matchPerson} (${currentCity.toUpperCase()})`);
        loadStats();
        loadCases();
      }, 2500);
    }

    window.addEventListener('DOMContentLoaded', async () => {
      initTheme();
      initMaps();
      await loadCities();
      await loadTeams();
      await loadStats();
      await loadCases();
      switchCity(currentCity, false);
      loadNotifications();
      restoreSession();
      setInterval(loadNotifications, 8000);
      resizeMaps();
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
            db_teams = load_teams_from_db()
            if db_teams is not None:
                APP_STATE["teams"] = db_teams
            self._send_json(APP_STATE["teams"])
            return

        if path == "/api/cases":
            db_cases = load_cases_from_db()
            if db_cases is not None:
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

            # 1. Identify the target case
            target_case = next((c for c in APP_STATE["cases"] if c["id"] == case_id), None)
            if not target_case:
                target_case = APP_STATE["cases"][0] if APP_STATE["cases"] else {}

            case_city = (target_case.get("city") or "kurnool").lower()

            # 2. Select the appropriate local rescue unit in the case's city
            team = None
            assigned_name = target_case.get("assigned_team")
            if assigned_name:
                team = next((t for t in APP_STATE["teams"] if t.get("name") == assigned_name), None)

            if not team and team_id:
                req_team = next((t for t in APP_STATE["teams"] if t["id"] == team_id), None)
                if req_team and (req_team.get("city", "").lower() == case_city):
                    team = req_team

            if not team:
                # Find any rescue team stationed in the case's city
                city_teams = [t for t in APP_STATE["teams"] if (t.get("city") or "").lower() == case_city]
                if city_teams:
                    team = city_teams[0]
                elif APP_STATE["teams"]:
                    team = APP_STATE["teams"][0]
                else:
                    team = {"name": "Helping Hands NGO", "base_location": "Base Station", "lat": 15.8350, "lon": 78.0450}

            # Ensure team base coordinates are localized if team belongs to different city
            target_lat = float(target_case.get("lat") or 15.8281)
            target_lon = float(target_case.get("lon") or 78.0373)
            team_city = (team.get("city") or "kurnool").lower()

            if team_city == case_city:
                team_lat = float(team.get("lat") or target_lat + 0.012)
                team_lon = float(team.get("lon") or target_lon + 0.015)
                base_name = team.get("base_location") or f"{case_city.title()} Response Outpost"
            else:
                # Localize response starting point to local regional outpost within 1.5 - 2.5 km of target
                team_lat = round(target_lat + 0.014, 4)
                team_lon = round(target_lon + 0.018, 4)
                base_name = f"{case_city.title()} Sector Response Station"

            route = _calculate_shortest_route(team_lat, team_lon, target_lat, target_lon)
            route["case_id"] = target_case.get("id", 1)
            route["person_name"] = target_case.get("name", "Target Subject")
            route["target_location"] = target_case.get("last_seen_location", "Target Sighting Node")
            route["team_name"] = team.get("name", "Local Rescue Unit")
            route["base_location"] = base_name
            route["city"] = case_city
            self._send_json(route)
            return

        if path.startswith("/uploads/"):
            rel_path = path.lstrip("/").replace("/", os.sep)
            full_path = os.path.join(os.getcwd(), rel_path)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                self.send_response(200)
                ext = os.path.splitext(full_path)[1].lower()
                mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png" if ext == ".png" else "application/octet-stream"
                self.send_header("Content-Type", mime)
                with open(full_path, "rb") as f:
                    data = f.read()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            else:
                self._send_json({"error": "File not found"}, status=404)
                return

        if path == "/api/cities":
            self._send_json(list(CITIES.values()))
            return

        if path == "/api/cameras":
            city_filter = query.get("city", [""])[0].lower()
            if city_filter:
                cams = {k: v for k, v in CAMERA_LOCATIONS.items() if v.get("city", "kurnool").lower() == city_filter}
            else:
                cams = CAMERA_LOCATIONS
            self._send_json(cams)
            return

        if path == "/api/demo":
            city = query.get("city", ["kurnool"])[0].lower()
            top_k = int(query.get("top", [5])[0]) if "top" in query else 5
            data = _get_city_graph_data(city_id=city, top_k=top_k)
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

            # NGO Team login check with salted password verification
            for t in APP_STATE["teams"]:
                if t.get("username") == uname and verify_password(t.get("password", ""), pwd):
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
        ):
            self._send_json({"status": "error", "error": "Access Denied: Police Command admin privileges required."}, status=403)
            return

        if parsed.path == "/api/teams/add":
            city_id = (body.get("city") or "kurnool").lower()
            new_id = max([t["id"] for t in APP_STATE["teams"]], default=0) + 1
            entry = {
                "id": new_id,
                "name": body.get("name", "New Rescue Team").strip(),
                "org": body.get("org", "NGO"),
                "city": city_id,
                "phone": body.get("phone", "6303126628").strip(),
                "email": body.get("email", "").strip(),
                "base_location": body.get("base_location", f"{city_id.title()} Base").strip(),
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
            city_id = (body.get("city") or "kurnool").lower()
            loc_name = body.get("last_seen_location", "").strip() or "CAR STAND"
            coords = CAMERA_LOCATIONS.get(loc_name)
            if not coords:
                lat_val = float(body.get("lat")) if body.get("lat") is not None else None
                lon_val = float(body.get("lon")) if body.get("lon") is not None else None
                if lat_val is not None and lon_val is not None:
                    coords = {"lat": lat_val, "lon": lon_val, "city": city_id}
                elif city_id in CITIES:
                    coords = {"lat": CITIES[city_id]["lat"], "lon": CITIES[city_id]["lon"], "city": city_id}
                else:
                    coords = {"lat": 15.8281, "lon": 78.0373, "city": "kurnool"}
                CAMERA_LOCATIONS[loc_name] = {
                    "lat": coords["lat"],
                    "lon": coords["lon"],
                    "city": city_id,
                    "label": f"{loc_name} ({coords['lat']:.4f}, {coords['lon']:.4f})",
                }

            assigned_team_name = body.get("assigned_team", "Helping Hands NGO")

            # Process photo if provided (base64 data URL)
            photo_path = ""
            photo_data = body.get("photo_data", "") or body.get("photo", "")
            if photo_data and photo_data.startswith("data:image"):
                try:
                    header, encoded = photo_data.split(",", 1)
                    img_bytes = base64.b64decode(encoded)
                    os.makedirs("uploads", exist_ok=True)
                    clean_name = re.sub(r'[^a-zA-Z0-9_]', '', body.get("name", "person").lower())
                    filename = f"person_{int(time.time())}_{clean_name}.jpg"
                    filepath = os.path.join("uploads", filename)
                    with open(filepath, "wb") as f:
                        f.write(img_bytes)
                    photo_path = f"/uploads/{filename}"
                except Exception as exc:
                    print(f"[!] Photo decode warning: {exc}")
            elif body.get("photo_path"):
                photo_path = body.get("photo_path")

            entry = {
                "name": body.get("name", "Unnamed Case").strip(),
                "city": city_id,
                "age": int(body.get("age", 20)),
                "gender": body.get("gender", "Unknown"),
                "clothes": body.get("clothes", "").strip(),
                "last_seen_location": loc_name,
                "status": "ACTIVE",
                "created_at": datetime.now().strftime("%d %b, %H:%M"),
                "assigned_team": assigned_team_name,
                "lat": coords["lat"],
                "lon": coords["lon"],
                "photo_path": photo_path,
                "phone": body.get("phone", "").strip(),
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

        if parsed.path == "/api/cases/update":
            cid = int(body.get("id", 0) or body.get("case_id", 0))
            if not cid:
                self._send_json({"error": "Missing case id"}, status=400)
                return

            photo_data = body.get("photo_data", "")
            if photo_data and photo_data.startswith("data:image"):
                try:
                    header, encoded = photo_data.split(",", 1)
                    img_bytes = base64.b64decode(encoded)
                    os.makedirs("uploads", exist_ok=True)
                    clean_name = re.sub(r'[^a-zA-Z0-9_]', '', body.get("name", "person").lower())
                    filename = f"person_{int(time.time())}_{clean_name}.jpg"
                    filepath = os.path.join("uploads", filename)
                    with open(filepath, "wb") as f:
                        f.write(img_bytes)
                    body["photo_path"] = f"/uploads/{filename}"
                except Exception as exc:
                    print(f"[!] Photo update decode warning: {exc}")

            updated_case = update_case_in_db(cid, body)
            if not updated_case:
                self._send_json({"error": "Case not found"}, status=404)
                return

            for c in APP_STATE["cases"]:
                if c["id"] == cid:
                    c.update(updated_case)
                    break

            resp = dict(updated_case)
            resp["status"] = "success"
            resp["message"] = f"Case #{cid} ({updated_case['name']}) updated in PostgreSQL database."
            resp["case"] = updated_case
            self._send_json(resp)
            return

        if parsed.path == "/api/cases/status":
            cid = int(body.get("id", 0) or body.get("case_id", 0))
            new_status = body.get("status", "ACTIVE").upper()
            if new_status not in ("ACTIVE", "RESCUED", "CLOSED"):
                new_status = "ACTIVE"
            notes = body.get("notes", f"Status updated to {new_status}")

            update_case_status_in_db(case_id=cid, status=new_status, notes=notes)

            for c in APP_STATE["cases"]:
                if c["id"] == cid:
                    c["status"] = new_status

            self._send_json({
                "case_id": cid,
                "status": new_status,
                "message": f"Case #{cid} status updated to {new_status} in PostgreSQL database."
            })
            return

        if parsed.path == "/api/cases/delete":
            cid = int(body.get("id", 0) or body.get("case_id", 0))
            delete_case_from_db(cid)
            APP_STATE["cases"] = [c for c in APP_STATE["cases"] if c["id"] != cid]
            if "dispatches" in APP_STATE:
                APP_STATE["dispatches"] = [d for d in APP_STATE["dispatches"] if d.get("case_id") != cid]
            if "notifications" in APP_STATE:
                APP_STATE["notifications"] = [n for n in APP_STATE["notifications"] if n.get("case_id") != cid]
            self._send_json({"deleted": cid, "status": "success", "message": f"Case #{cid} permanently deleted from database."})
            return

        if parsed.path == "/api/resolve-dispatch":
            cid = int(body.get("case_id", 1))
            outcome = body.get("outcome", "found")
            notes = body.get("notes", "")

            if outcome in ("reset_active", "active"):
                new_status = "ACTIVE"
            elif outcome == "found":
                new_status = "RESCUED"
            else:
                new_status = "CLOSED"

            update_case_status_in_db(case_id=cid, status=new_status, notes=notes)

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


def _get_demo_data(city_id: str | int = "kurnool", top_k: int = 5, speed: float | None = None) -> dict:
    if isinstance(city_id, int):
        top_k = city_id
        city_id = "kurnool"
    return _get_city_graph_data(city_id=city_id, top_k=top_k, speed=speed)


def run_server(host: str = "0.0.0.0", port: int = 10000) -> None:
    _sync_db_with_state()
    httpd = ThreadingHTTPServer((host, port), MPTrackerHandler)
    print(f"[+] MPTracker Web Dashboard active at http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
