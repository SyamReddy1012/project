"""Database helpers (PostgreSQL + pgvector) and full persistence layer."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
from pgvector.psycopg2 import register_vector

from .config import Settings, get_settings
import hashlib
import secrets


def hash_password(password: str) -> str:
    """Return a salted SHA-256 hash string in the format: sha256$salt$hash"""
    if not password:
        return ""
    salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"sha256${salt}${h}"


def verify_password(stored: str, provided: str) -> bool:
    """Verify password against stored string. Supports both hashed (sha256$salt$hash) and plaintext."""
    if not stored or not provided:
        return False
    if stored.startswith("sha256$") and stored.count("$") == 2:
        try:
            _, salt, expected_hash = stored.split("$", 2)
            test_hash = hashlib.sha256((salt + provided).encode("utf-8")).hexdigest()
            return test_hash == expected_hash
        except Exception:
            return False
    # Backward compatible fallback for existing plaintext passwords in db
    return stored == provided


SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "schema.sql")

DEFAULT_CAMERAS = {
    "CAR STAND": (15.8281, 78.0373),
    "Budhwarpet Market": (15.835, 78.045),
    "Kurnool City Railway": (15.831, 78.042),
    "Kurnool Bus Stand": (15.8281, 78.0373),
    "RGM grounds": (15.831, 78.042),
    "cantene": (15.835, 78.045),
    "DS labs": (15.82, 78.045),
    "RGM hostel": (15.815, 78.03),
    "RGM gardens": (15.834, 78.056),
    "Konda Reddy Fort": (15.834, 78.056),
    "maha nandhi": (15.81, 78.06),
    "Collectorate": (15.82, 78.045),
    "Government Hospital": (15.815, 78.03),
    "Tungabhadra Bridge": (15.842, 78.03),
    "Charminar Heritage Zone": (17.3616, 78.4747),
    "Secunderabad Railway Station": (17.4344, 78.5017),
    "HITEC City Cyber Towers": (17.4504, 78.3808),
    "Gachibowli Junction": (17.4401, 78.3489),
    "Kacheguda Railway Station": (17.3892, 78.4975),
    "Mehdipatnam Bus Depot": (17.3916, 78.4418),
    "Hussain Sagar Tank Bund": (17.4239, 78.4738),
    "Jubilee Hills Checkpost": (17.4319, 78.4073),
    "Dilsukhnagar Metro Hub": (17.3688, 78.5247),
    "Ameerpet Metro Junction": (17.4375, 78.4483),
    "Majestic Central Terminal": (12.9767, 77.5713),
    "MG Road Metro Station": (12.9756, 77.6066),
    "Koramangala Sony World Signal": (12.9352, 77.6245),
    "Whitefield ITPL Tech Zone": (12.9863, 77.7308),
    "Electronic City Phase 1 Toll": (12.8452, 77.6602),
    "Indiranagar 100ft Road": (12.9784, 77.6408),
    "Yeshwanthpur Railway Junction": (13.0238, 77.5501),
    "Silk Board Junction": (12.9177, 77.6238),
    "PNBS Central Bus Station": (16.5165, 80.62),
    "Vijayawada Railway Junction": (16.5186, 80.6203),
    "Prakasam Barrage Point": (16.509, 80.6065),
    "Kanaka Durga Temple Gate": (16.5162, 80.6052),
    "Benz Circle Commercial Hub": (16.4988, 80.6552),
    "Besant Road Market Zone": (16.5112, 80.6288),
    "Ramavarappadu Ring": (16.5244, 80.675),
    "RK Beach Promenade": (17.7126, 83.3182),
    "Visakhapatnam Railway Station": (17.7215, 83.2906),
    "Dwaraka RTC Bus Complex": (17.7265, 83.304),
    "Jagadamba Junction": (17.7118, 83.3015),
    "Rushikonda IT Hill": (17.7818, 83.3855),
    "Gajuwaka Industrial Hub": (17.6908, 83.2132),
    "Kailasagiri Viewpoint": (17.749, 83.3424),
    "Tirupati Central Railway Station": (13.6267, 79.4217),
    "Central Bus Stand (CBS)": (13.6282, 79.4261),
    "Alipiri Footpath Toll Gate": (13.6521, 79.3872),
    "TUDA Circle": (13.6334, 79.4168),
    "Renigunta Junction": (13.6496, 79.5164),
    "Ramanuja Circle": (13.631, 79.4312),
    "Nandyal Clock Tower": (15.482, 78.487),
    "Nandyal Railway Station": (15.4912, 78.4815),
    "RTC Central Bus Stand": (15.4795, 78.485),
    "Rythu Bazaar Gate": (15.485, 78.489),
    "Atmakur Gate Circle": (15.495, 78.478),
    "Balapanur Crossroad": (15.468, 78.492),
    "Chennai Central Puratchi Thalaivar": (13.0823, 80.2755),
    "Koyambedu CMBT Bus Terminal": (13.0694, 80.1948),
    "Marina Beach Promenade": (13.05, 80.2824),
    "T. Nagar Panagal Park": (13.0405, 80.2337),
    "Guindy Kathipara Flyover": (13.0067, 80.2016),
    "Chennai International Airport": (12.9941, 80.1709),
    "Chhatrapati Shivaji Maharaj Terminus": (18.94, 72.8354),
    "Dadar Central Station": (19.0178, 72.8478),
    "Bandra Kurla Complex (BKC)": (19.0657, 72.8687),
    "Gateway of India Promenade": (18.922, 72.8347),
    "Andheri Metro Hub": (19.1197, 72.8468),
    "Marine Drive Promenade": (18.9432, 72.823),
    "New Delhi Railway Station (NDLS)": (28.6429, 77.2195),
    "Rajiv Chowk Connaught Place": (28.6328, 77.2197),
    "Kashmiri Gate ISBT": (28.6678, 77.2285),
    "India Gate Circle": (28.6129, 77.2295),
    "Indira Gandhi Airport T3": (28.5562, 77.1),
    "Anand Vihar Terminal": (28.6469, 77.316),
}

DEFAULT_SEED_TEAMS = [
    {
        "id": 1,
        "name": "Helping Hands NGO",
        "org": "NGO",
        "city": "kurnool",
        "base_location": "Budhwarpet Base",
        "lat": 15.8350,
        "lon": 78.0450,
        "phone": "6303126628",
        "email": "contact@helpinghands-knl.org",
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
        "email": "patrol1@kurnoolpolice.gov.in",
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
        "email": "volunteer.a@rayalaseema.org",
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
        "phone": "94401-22334",
        "email": "hyd.rescue@telangana.gov.in",
        "username": "hyd_rescue",
        "password": "hyd123",
        "available": True,
    },
    {
        "id": 5,
        "name": "Bengaluru Red Cross Unit",
        "org": "NGO",
        "city": "bengaluru",
        "base_location": "MG Road Operations Center",
        "lat": 12.9750,
        "lon": 77.6050,
        "phone": "98860-44556",
        "email": "redcross@bengaluru.org",
        "username": "blr_redcross",
        "password": "blr123",
        "available": True,
    },
    {
        "id": 6,
        "name": "Amaravati Emergency Corps",
        "org": "Disaster Relief",
        "city": "vijayawada",
        "base_location": "Benz Circle Response Depot",
        "lat": 16.5020,
        "lon": 80.6450,
        "phone": "98480-77889",
        "email": "emergency@amaravati.gov.in",
        "username": "amaravati_corps",
        "password": "vja123",
        "available": True,
    },
    {
        "id": 7,
        "name": "Coastal Rescue Force",
        "org": "Volunteer",
        "city": "visakhapatnam",
        "base_location": "RK Beach Watch Station",
        "lat": 17.7110,
        "lon": 83.3150,
        "phone": "98499-11223",
        "email": "coastal@vizagrescue.in",
        "username": "vizag_coastal",
        "password": "vizag123",
        "available": True,
    },
    {
        "id": 8,
        "name": "Tirumala Pilgrim Assistance Patrol",
        "org": "Police",
        "city": "tirupati",
        "base_location": "Alipiri Security Outpost",
        "lat": 13.6510,
        "lon": 79.3850,
        "phone": "94408-33445",
        "email": "security@tirumala.org",
        "username": "tirupati_patrol",
        "password": "tpt123",
        "available": True,
    },
    {
        "id": 9,
        "name": "Mumbai Rapid Search & Rescue",
        "org": "NGO",
        "city": "mumbai",
        "base_location": "Dadar Emergency Depot",
        "lat": 19.0178,
        "lon": 72.8478,
        "phone": "98200-99887",
        "email": "rescue@mumbaisos.org",
        "username": "mumbai_rapid",
        "password": "mum123",
        "available": True,
    },
]

DEFAULT_SEED_CASES = [
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
        "name": "S.javeed",
        "age": 19,
        "gender": "Male",
        "clothes": "greyish green shirt",
        "city": "kurnool",
        "last_seen_location": "RGM hostel",
        "status": "ACTIVE",
        "created_at": "3 days ago",
        "assigned_team": "City Police Patrol 1",
        "lat": 15.8150,
        "lon": 78.0300,
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


def _infer_city(name_or_loc: str) -> str:
    """Infer city string from location or landmark name."""
    text = (name_or_loc or "").lower()
    if any(k in text for k in ["charminar", "hitec", "secunderabad", "gachibowli", "hyderabad"]):
        return "hyderabad"
    if any(k in text for k in ["majestic", "mg road", "electronic city", "whitefield", "bengaluru", "bangalore"]):
        return "bengaluru"
    if any(k in text for k in ["pnbs", "benz circle", "prakasam", "vijayawada"]):
        return "vijayawada"
    if any(k in text for k in ["beach", "rtc complex", "visakhapatnam", "vizag"]):
        return "visakhapatnam"
    if any(k in text for k in ["alipiri", "tirumala", "tirupati"]):
        return "tirupati"
    if any(k in text for k in ["nandyal", "sanjeeva"]):
        return "nandyal"
    if any(k in text for k in ["chennai", "central", "t-nagar", "marina"]):
        return "chennai"
    if any(k in text for k in ["csmt", "gateway", "bandra", "mumbai"]):
        return "mumbai"
    if any(k in text for k in ["connaught", "delhi", "anand vihar"]):
        return "delhi"
    return "kurnool"


def connect(settings: Optional[Settings] = None, vector: bool = True):
    if settings is None:
        settings = get_settings()
    conn = psycopg2.connect(**settings.db_kwargs)
    if vector:
        try:
            register_vector(conn)
        except Exception:
            pass
    return conn


def init_db(settings: Optional[Settings] = None) -> None:
    if settings is None:
        settings = get_settings()
    conn = connect(settings, vector=False)
    with conn, conn.cursor() as cur:
        if os.path.exists(SCHEMA_PATH):
            with open(SCHEMA_PATH, encoding="utf-8") as fh:
                cur.execute(fh.read())
    conn.close()


def ensure_db_schema(settings: Optional[Settings] = None) -> bool:
    """Ensure all required tables, columns, constraints and initial seed records exist in PostgreSQL."""
    try:
        init_db(settings)
        conn = connect(settings, vector=False)
        with conn, conn.cursor() as cur:
            # Upgrade columns safely
            cur.execute("ALTER TABLE rescue_teams ADD COLUMN IF NOT EXISTS username VARCHAR(100);")
            cur.execute("ALTER TABLE rescue_teams ADD COLUMN IF NOT EXISTS password VARCHAR(100);")
            cur.execute("ALTER TABLE rescue_teams ADD COLUMN IF NOT EXISTS city VARCHAR(100) DEFAULT 'kurnool';")
            cur.execute("ALTER TABLE rescue_teams ADD COLUMN IF NOT EXISTS email VARCHAR(150);")
            cur.execute("ALTER TABLE missing_persons ADD COLUMN IF NOT EXISTS city VARCHAR(100) DEFAULT 'kurnool';")
            cur.execute("ALTER TABLE missing_persons ADD COLUMN IF NOT EXISTS photo_path TEXT;")
            cur.execute("ALTER TABLE missing_persons ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(50);")
            cur.execute("ALTER TABLE missing_persons ADD COLUMN IF NOT EXISTS last_seen_latitude DOUBLE PRECISION;")
            cur.execute("ALTER TABLE missing_persons ADD COLUMN IF NOT EXISTS last_seen_longitude DOUBLE PRECISION;")
            cur.execute("ALTER TABLE camera_locations ADD COLUMN IF NOT EXISTS city VARCHAR(100) DEFAULT 'kurnool';")

            # Seed camera locations
            for cname, (clat, clon) in DEFAULT_CAMERAS.items():
                cur.execute(
                    """INSERT INTO camera_locations (name, latitude, longitude, city)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (name) DO UPDATE SET latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude, city=EXCLUDED.city""",
                    (cname, clat, clon, _infer_city(cname) or "kurnool"),
                )

            # Check if rescue_teams has ANY records; seed ONLY if table is completely empty
            cur.execute("SELECT COUNT(*) FROM rescue_teams")
            team_count = cur.fetchone()[0]
            if team_count == 0:
                for t in DEFAULT_SEED_TEAMS:
                    cur.execute(
                        """INSERT INTO rescue_teams
                           (name, organization_type, contact_phone, city, current_location_name, latitude, longitude, is_available, username, password, email)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (t["name"], t["org"], t["phone"], t["city"], t["base_location"], t["lat"], t["lon"], t["available"], t["username"], t["password"], t.get("email", "")),
                    )

            # Check if missing_persons has ANY records; seed ONLY if table is completely empty
            cur.execute("SELECT COUNT(*) FROM missing_persons")
            case_count = cur.fetchone()[0]
            if case_count == 0:
                for c in DEFAULT_SEED_CASES:
                    cur.execute(
                        """INSERT INTO missing_persons
                           (name, age, gender, clothes_description, city, last_seen_location, case_status, last_seen_latitude, last_seen_longitude)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                        (c["name"], c["age"], c["gender"], c["clothes"], c["city"], c["last_seen_location"], c["status"], c["lat"], c["lon"]),
                    )
                    new_pid = cur.fetchone()[0]
                    cur.execute("SELECT id FROM rescue_teams WHERE name=%s LIMIT 1", (c["assigned_team"],))
                    t_row = cur.fetchone()
                    if t_row:
                        cur.execute(
                            "INSERT INTO case_assignments (missing_person_id, rescue_team_id, status) VALUES (%s, %s, 'ACTIVE')",
                            (new_pid, t_row[0]),
                        )

            conn.commit()
        conn.close()
        print("[+] PostgreSQL schema verified and synchronized.")
        return True
    except Exception as exc:
        print(f"[!] PostgreSQL ensure_db_schema warning: {exc}")
        return False


def load_cases_from_db(settings: Optional[Settings] = None) -> List[Dict[str, Any]]:
    """Fetch all cases from PostgreSQL missing_persons joined with case_assignments."""
    try:
        conn = connect(settings, vector=False)
        cases = []
        with conn, conn.cursor() as cur:
            query = """
                SELECT m.id, m.name, m.age, m.gender, m.clothes_description,
                       m.city, m.last_seen_location, m.case_status, m.created_at,
                       m.last_seen_latitude, m.last_seen_longitude, m.photo_path,
                       m.contact_phone, r.name AS assigned_team
                FROM missing_persons m
                LEFT JOIN LATERAL (
                    SELECT rescue_team_id FROM case_assignments
                    WHERE missing_person_id = m.id
                    ORDER BY id DESC LIMIT 1
                ) ca ON TRUE
                LEFT JOIN rescue_teams r ON ca.rescue_team_id = r.id
                ORDER BY m.id DESC
            """
            cur.execute(query)
            for r in cur.fetchall():
                pid, name, age, gender, clothes, city, loc, status, created_at, lat, lon, photo, phone, assigned_team = r
                created_str = created_at.strftime("%d %b, %H:%M") if hasattr(created_at, "strftime") else "Recently"
                default_coords = DEFAULT_CAMERAS.get(loc or "", (15.8281, 78.0373))
                case_city = (city or _infer_city(loc or name or "") or "kurnool").lower()
                cases.append({
                    "id": pid,
                    "name": name,
                    "age": age or 25,
                    "gender": gender or "Male",
                    "clothes": clothes or "",
                    "city": case_city,
                    "last_seen_location": loc or "CAR STAND",
                    "status": status or "ACTIVE",
                    "created_at": created_str,
                    "assigned_team": assigned_team or "Helping Hands NGO",
                    "lat": float(lat) if lat is not None else default_coords[0],
                    "lon": float(lon) if lon is not None else default_coords[1],
                    "photo_path": photo or "",
                    "phone": phone or "",
                })
        conn.close()
        return cases
    except Exception as exc:
        print(f"[!] load_cases_from_db connection failure: {exc}")
        return list(DEFAULT_SEED_CASES)


def save_case_to_db(case: Dict[str, Any], settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Insert a new missing person case into PostgreSQL and assign team."""
    try:
        conn = connect(settings, vector=False)
        city = (case.get("city") or _infer_city(case.get("last_seen_location", "") or case.get("name", "")) or "kurnool").lower()
        with conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO missing_persons
                   (name, age, gender, clothes_description, city, last_seen_location, case_status,
                    last_seen_latitude, last_seen_longitude, photo_path, contact_phone)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id, created_at""",
                (
                    case.get("name", "Unnamed Case"),
                    int(case.get("age", 20)),
                    case.get("gender", "Unknown"),
                    case.get("clothes", ""),
                    city,
                    case.get("last_seen_location", "CAR STAND"),
                    case.get("status", "ACTIVE"),
                    float(case.get("lat", 15.8281)),
                    float(case.get("lon", 78.0373)),
                    case.get("photo_path", ""),
                    case.get("phone", ""),
                ),
            )
            row = cur.fetchone()
            new_id = row[0]
            created_at = row[1].strftime("%d %b, %H:%M") if hasattr(row[1], "strftime") else "Just now"
            case["id"] = new_id
            case["created_at"] = created_at
            case["city"] = city

            assigned_team_name = case.get("assigned_team")
            if assigned_team_name:
                cur.execute("SELECT id FROM rescue_teams WHERE name=%s LIMIT 1", (assigned_team_name,))
                t_row = cur.fetchone()
                if t_row:
                    cur.execute(
                        "INSERT INTO case_assignments (missing_person_id, rescue_team_id, status) VALUES (%s, %s, 'ACTIVE')",
                        (new_id, t_row[0]),
                    )
            conn.commit()
        conn.close()
        print(f"[+] Case #{new_id} ({case.get('name')}, {city.upper()}) successfully saved to PostgreSQL.")
        return case
    except Exception as exc:
        print(f"[!] save_case_to_db warning: {exc}")
        return case


def update_case_in_db(case_id: int, updates: Dict[str, Any], settings: Optional[Settings] = None) -> Optional[Dict[str, Any]]:
    """Update any fields of a missing person case in PostgreSQL and sync dispatches/assignments."""
    try:
        conn = connect(settings, vector=False)
        with conn, conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, age, gender, clothes_description, city,
                       last_seen_location, case_status, last_seen_latitude,
                       last_seen_longitude, photo_path, contact_phone
                FROM missing_persons WHERE id=%s
            """, (case_id,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return None

            name = (updates.get("name") if updates.get("name") is not None else row[1]) or "Unnamed Case"
            name = str(name).strip()
            age = int(updates.get("age") if updates.get("age") is not None else (row[2] or 25))
            gender = updates.get("gender") if updates.get("gender") is not None else (row[3] or "Unknown")
            clothes = str(updates.get("clothes") if "clothes" in updates else (updates.get("clothes_description") if "clothes_description" in updates else (row[4] or ""))).strip()
            city = str(updates.get("city") if updates.get("city") is not None else (row[5] or "kurnool")).strip().lower()
            last_seen = str(updates.get("last_seen_location") if "last_seen_location" in updates else (updates.get("location") if "location" in updates else (row[6] or "CAR STAND"))).strip()
            status = str(updates.get("status") if "status" in updates else (updates.get("case_status") if "case_status" in updates else (row[7] or "ACTIVE"))).strip().upper()
            lat = float(updates.get("lat") if updates.get("lat") is not None else (row[8] or 15.8281))
            lon = float(updates.get("lon") if updates.get("lon") is not None else (row[9] or 78.0373))
            photo = updates.get("photo_path") if "photo_path" in updates else (row[10] or "")
            phone = str((updates.get("phone") or updates.get("contact_phone")) if ("phone" in updates or "contact_phone" in updates) else (row[11] or "")).strip()

            cur.execute(
                """UPDATE missing_persons
                   SET name=%s, age=%s, gender=%s, clothes_description=%s, city=%s,
                       last_seen_location=%s, case_status=%s, last_seen_latitude=%s,
                       last_seen_longitude=%s, photo_path=%s, contact_phone=%s
                   WHERE id=%s""",
                (name, age, gender, clothes, city, last_seen, status, lat, lon, photo, phone, case_id),
            )

            assigned_team = updates.get("assigned_team")
            if assigned_team:
                cur.execute("SELECT id FROM rescue_teams WHERE name=%s LIMIT 1", (assigned_team,))
                t_row = cur.fetchone()
                if t_row:
                    cur.execute(
                        """INSERT INTO case_assignments (missing_person_id, rescue_team_id, status)
                           VALUES (%s, %s, 'ACTIVE')
                           ON CONFLICT DO NOTHING""",
                        (case_id, t_row[0]),
                    )
                    cur.execute(
                        """UPDATE case_assignments
                           SET rescue_team_id=%s, status='ACTIVE'
                           WHERE id = (SELECT id FROM case_assignments WHERE missing_person_id=%s ORDER BY id DESC LIMIT 1)""",
                        (t_row[0], case_id),
                    )

            if status == "ACTIVE":
                cur.execute(
                    """UPDATE rescue_dispatches
                       SET status='EN_ROUTE', resolved_at=NULL
                       WHERE missing_person_id=%s""",
                    (case_id,),
                )
            elif status in ("RESCUED", "CLOSED"):
                d_status = "VERIFIED_FOUND" if status == "RESCUED" else "NOT_FOUND"
                cur.execute(
                    """UPDATE rescue_dispatches
                       SET status=%s, resolved_at=CURRENT_TIMESTAMP
                       WHERE missing_person_id=%s""",
                    (d_status, case_id),
                )

            conn.commit()
        conn.close()
        print(f"[+] Case #{case_id} ({name}, {city.upper()}) successfully updated in PostgreSQL.")
        return {
            "id": case_id,
            "name": name,
            "age": age,
            "gender": gender,
            "clothes": clothes,
            "city": city,
            "last_seen_location": last_seen,
            "status": status,
            "lat": lat,
            "lon": lon,
            "photo_path": photo,
            "phone": phone,
            "assigned_team": assigned_team or "Helping Hands NGO",
        }
    except Exception as exc:
        print(f"[!] update_case_in_db warning: {exc}")
        return None


def update_case_status_in_db(case_id: int, status: str, notes: str = "", settings: Optional[Settings] = None) -> bool:
    """Update missing person case_status in PostgreSQL and adjust dispatches and assignments."""
    status = (status or "ACTIVE").upper()
    if status not in ("ACTIVE", "RESCUED", "CLOSED"):
        status = "ACTIVE"
    try:
        conn = connect(settings, vector=False)
        with conn, conn.cursor() as cur:
            cur.execute("UPDATE missing_persons SET case_status=%s WHERE id=%s", (status, case_id))
            if status == "ACTIVE":
                cur.execute("UPDATE case_assignments SET status='ACTIVE' WHERE missing_person_id=%s", (case_id,))
                cur.execute(
                    """UPDATE rescue_dispatches
                       SET status='EN_ROUTE', responder_notes=%s, resolved_at=NULL
                       WHERE missing_person_id=%s""",
                    (f"Status reset to ACTIVE. {notes}".strip(), case_id),
                )
            elif status in ("RESCUED", "CLOSED"):
                dispatch_status = "VERIFIED_FOUND" if status == "RESCUED" else "NOT_FOUND"
                cur.execute(
                    """UPDATE rescue_dispatches
                       SET status=%s, responder_notes=%s, resolved_at=CURRENT_TIMESTAMP
                       WHERE missing_person_id=%s""",
                    (dispatch_status, notes or f"Marked as {status}", case_id),
                )
                cur.execute("UPDATE case_assignments SET status='RESOLVED' WHERE missing_person_id=%s", (case_id,))
            conn.commit()
        conn.close()
        print(f"[+] Case #{case_id} status updated to {status} in PostgreSQL.")
        return True
    except Exception as exc:
        print(f"[!] update_case_status_in_db warning: {exc}")
        return False


def delete_case_from_db(case_id: int, settings: Optional[Settings] = None) -> bool:
    """Delete case and all associated dispatches/assignments/sightings from PostgreSQL."""
    try:
        conn = connect(settings, vector=False)
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM rescue_dispatches WHERE missing_person_id=%s", (case_id,))
            cur.execute("DELETE FROM case_assignments WHERE missing_person_id=%s", (case_id,))
            cur.execute("DELETE FROM person_sightings WHERE missing_person_id=%s", (case_id,))
            cur.execute("DELETE FROM missing_persons WHERE id=%s", (case_id,))
            conn.commit()
        conn.close()
        print(f"[+] Case #{case_id} deleted from PostgreSQL.")
        return True
    except Exception as exc:
        print(f"[!] delete_case_from_db warning: {exc}")
        return False


def load_teams_from_db(settings: Optional[Settings] = None) -> List[Dict[str, Any]]:
    """Fetch all rescue teams from PostgreSQL."""
    try:
        conn = connect(settings, vector=False)
        teams = []
        with conn, conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, organization_type, contact_phone, city,
                       current_location_name, latitude, longitude, is_available,
                       username, password, email
                FROM rescue_teams
                ORDER BY id ASC
            """)
            for r in cur.fetchall():
                tid, name, org, phone, city, loc, lat, lon, avail, uname, pwd, email = r
                team_city = (city or _infer_city(loc or name or "") or "kurnool").lower()
                teams.append({
                    "id": tid,
                    "name": name,
                    "org": org or "NGO",
                    "city": team_city,
                    "phone": phone or "6303126628",
                    "email": email or "",
                    "base_location": loc or "Base Outpost",
                    "lat": float(lat) if lat is not None else 15.8350,
                    "lon": float(lon) if lon is not None else 78.0450,
                    "available": bool(avail) if avail is not None else True,
                    "username": uname or f"ngo_{tid}",
                    "password": pwd or "ngo123",
                })
        conn.close()
        return teams
    except Exception as exc:
        print(f"[!] load_teams_from_db connection failure: {exc}")
        return list(DEFAULT_SEED_TEAMS)


def save_team_to_db(team: Dict[str, Any], settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Insert a new rescue team / NGO into PostgreSQL."""
    try:
        conn = connect(settings, vector=False)
        city = (team.get("city") or _infer_city(team.get("base_location", "") or team.get("name", "")) or "kurnool").lower()
        with conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO rescue_teams
                   (name, organization_type, contact_phone, city, current_location_name, latitude, longitude, is_available, username, password, email)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    team.get("name", "New Rescue Team"),
                    team.get("org", "NGO"),
                    team.get("phone", "6303126628"),
                    city,
                    team.get("base_location", f"{city.title()} Base"),
                    float(team.get("lat", 15.8350)),
                    float(team.get("lon", 78.0450)),
                    team.get("available", True),
                    team.get("username", "new_team").strip(),
                    hash_password(team.get("password", "ngo123").strip()),
                    team.get("email", "").strip(),
                ),
            )
            new_id = cur.fetchone()[0]
            team["id"] = new_id
            team["city"] = city
            conn.commit()
        conn.close()
        print(f"[+] Team #{new_id} ({team.get('name')}, {city.upper()}) successfully saved to PostgreSQL.")
        return team
    except Exception as exc:
        print(f"[!] save_team_to_db warning: {exc}")
        return team


def delete_team_from_db(team_id: int, settings: Optional[Settings] = None) -> bool:
    """Delete a rescue team / NGO from PostgreSQL."""
    try:
        conn = connect(settings, vector=False)
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM rescue_dispatches WHERE rescue_team_id=%s", (team_id,))
            cur.execute("DELETE FROM case_assignments WHERE rescue_team_id=%s", (team_id,))
            cur.execute("DELETE FROM rescue_teams WHERE id=%s", (team_id,))
            conn.commit()
        conn.close()
        print(f"[+] Team #{team_id} deleted from PostgreSQL.")
        return True
    except Exception as exc:
        print(f"[!] delete_team_from_db warning: {exc}")
        return False


def save_sighting_to_db(
    case_id: int,
    camera_name: str,
    lat: float,
    lon: float,
    video_source: str = "Surveillance CCTV",
    confidence_dist: float = 0.28,
    frame_number: int = 105,
    timestamp_sec: float = 4.2,
    settings: Optional[Settings] = None,
) -> Optional[int]:
    """Record a facial recognition camera sighting in PostgreSQL person_sightings."""
    try:
        conn = connect(settings, vector=False)
        with conn, conn.cursor() as cur:
            # Ensure camera location exists in camera_locations
            cur.execute("SELECT id FROM camera_locations WHERE name=%s LIMIT 1", (camera_name,))
            row = cur.fetchone()
            if row:
                cam_id = row[0]
            else:
                cur.execute(
                    "INSERT INTO camera_locations (name, latitude, longitude) VALUES (%s, %s, %s) RETURNING id",
                    (camera_name, lat, lon),
                )
                cam_id = cur.fetchone()[0]

            # Insert sighting
            cur.execute(
                """INSERT INTO person_sightings
                   (missing_person_id, camera_id, video_source, video_timestamp_sec, frame_number, confidence_distance)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (case_id, cam_id, video_source, timestamp_sec, frame_number, round(confidence_dist, 4)),
            )
            sighting_id = cur.fetchone()[0]

            # Update person's latest spotted location & coordinates
            cur.execute(
                """UPDATE missing_persons
                   SET last_seen_location=%s, last_seen_latitude=%s, last_seen_longitude=%s
                   WHERE id=%s""",
                (camera_name, lat, lon, case_id),
            )
            conn.commit()
        conn.close()
        print(f"[+] Sighting #{sighting_id} for Case #{case_id} recorded at {camera_name} in PostgreSQL.")
        return sighting_id
    except Exception as exc:
        print(f"[!] save_sighting_to_db warning: {exc}")
        return None


def save_dispatch_to_db(
    case_id: int,
    team_id: int,
    location_name: str,
    distance_km: float,
    eta_minutes: float,
    status: str = "EN_ROUTE",
    notes: str = "",
    settings: Optional[Settings] = None,
) -> Optional[int]:
    """Record or update a rescue dispatch and case assignment in PostgreSQL."""
    try:
        conn = connect(settings, vector=False)
        with conn, conn.cursor() as cur:
            # Insert into rescue_dispatches
            cur.execute(
                """INSERT INTO rescue_dispatches
                   (missing_person_id, rescue_team_id, sighting_location, distance_km, estimated_eta_minutes, status, responder_notes)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (case_id, team_id, location_name, round(distance_km, 2), round(eta_minutes, 1), status, notes),
            )
            disp_id = cur.fetchone()[0]

            # Record or update case assignment
            cur.execute(
                """INSERT INTO case_assignments (missing_person_id, rescue_team_id, status)
                   VALUES (%s, %s, 'ACTIVE')""",
                (case_id, team_id),
            )

            # Update team availability if en route
            if status == "EN_ROUTE":
                cur.execute("UPDATE rescue_teams SET is_available = FALSE WHERE id = %s", (team_id,))

            conn.commit()
        conn.close()
        print(f"[+] Dispatch #{disp_id} (Case #{case_id} -> Team #{team_id}) recorded in PostgreSQL.")
        return disp_id
    except Exception as exc:
        print(f"[!] save_dispatch_to_db warning: {exc}")
        return None


def resolve_dispatch_in_db(
    case_id: int,
    outcome: str = "found",
    notes: str = "",
    settings: Optional[Settings] = None,
) -> bool:
    """Resolve active dispatches for a case, update person case_status, and free up rescue teams."""
    new_case_status = "RESCUED" if outcome == "found" else "CLOSED"
    dispatch_status = "VERIFIED_FOUND" if outcome == "found" else "NOT_FOUND"

    try:
        conn = connect(settings, vector=False)
        with conn, conn.cursor() as cur:
            # Find associated teams for this case's dispatches
            cur.execute(
                "SELECT DISTINCT rescue_team_id FROM rescue_dispatches WHERE missing_person_id=%s",
                (case_id,),
            )
            team_ids = [row[0] for row in cur.fetchall() if row[0] is not None]

            # Update dispatches
            cur.execute(
                """UPDATE rescue_dispatches
                   SET status=%s, responder_notes=%s, resolved_at=CURRENT_TIMESTAMP
                   WHERE missing_person_id=%s""",
                (dispatch_status, notes, case_id),
            )

            # Update person status
            cur.execute(
                "UPDATE missing_persons SET case_status=%s WHERE id=%s",
                (new_case_status, case_id),
            )

            # Free up the teams
            for tid in team_ids:
                cur.execute("UPDATE rescue_teams SET is_available=TRUE WHERE id=%s", (tid,))

            conn.commit()
        conn.close()
        print(f"[+] Case #{case_id} resolved as {new_case_status} in PostgreSQL.")
        return True
    except Exception as exc:
        print(f"[!] resolve_dispatch_in_db warning: {exc}")
        return False


def load_dispatches_from_db(settings: Optional[Settings] = None) -> List[Dict[str, Any]]:
    """Fetch all rescue dispatches from PostgreSQL joined with person and team."""
    try:
        conn = connect(settings, vector=False)
        dispatches = []
        with conn, conn.cursor() as cur:
            query = """
                SELECT d.id, d.missing_person_id, m.name, d.rescue_team_id, r.name,
                       d.sighting_location, d.distance_km, d.estimated_eta_minutes,
                       d.status, d.dispatched_at, d.responder_notes,
                       r.latitude, r.longitude, m.last_seen_latitude, m.last_seen_longitude
                FROM rescue_dispatches d
                LEFT JOIN missing_persons m ON d.missing_person_id = m.id
                LEFT JOIN rescue_teams r ON d.rescue_team_id = r.id
                ORDER BY d.id DESC
            """
            cur.execute(query)
            for r in cur.fetchall():
                (
                    did, pid, pname, tid, tname, loc, dist, eta,
                    status, dt, notes, tlat, tlon, mlat, mlon,
                ) = r
                dispatches.append({
                    "id": did,
                    "case_id": pid or 1,
                    "person_name": pname or "N.K.SYAM",
                    "team_id": tid or 1,
                    "team_name": tname or "Helping Hands NGO",
                    "target_location": loc or "CAR STAND",
                    "target_lat": float(mlat) if mlat is not None else 15.8281,
                    "target_lon": float(mlon) if mlon is not None else 78.0373,
                    "team_lat": float(tlat) if tlat is not None else 15.8350,
                    "team_lon": float(tlon) if tlon is not None else 78.0450,
                    "distance_km": float(dist) if dist is not None else 1.74,
                    "eta_minutes": float(eta) if eta is not None else 2.8,
                    "status": status or "EN_ROUTE",
                    "responder_notes": notes or "",
                })
        conn.close()
        return dispatches
    except Exception as exc:
        print(f"[!] load_dispatches_from_db warning: {exc}")
        return []
