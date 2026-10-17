"""Database helpers (PostgreSQL + pgvector) and full persistence layer."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
from pgvector.psycopg2 import register_vector

from .config import Settings, get_settings

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "schema.sql")

DEFAULT_CAMERAS = {
    "CAR STAND": (15.8281, 78.0373),
    "Budhwarpet Market": (15.8350, 78.0450),
    "Kurnool City Railway": (15.8310, 78.0420),
    "Kurnool Bus Stand": (15.8281, 78.0373),
    "RGM grounds": (15.8310, 78.0420),
    "cantene": (15.8350, 78.0450),
    "DS labs": (15.8200, 78.0450),
    "RGM hostel": (15.8150, 78.0300),
    "RGM gardens": (15.8340, 78.0560),
    "Konda Reddy Fort": (15.8340, 78.0560),
    "maha nandhi": (15.8100, 78.0600),
    "Collectorate": (15.8200, 78.0450),
    "Government Hospital": (15.8150, 78.0300),
    "Tungabhadra Bridge": (15.8420, 78.0300),
}

DEFAULT_SEED_TEAMS = [
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

DEFAULT_SEED_CASES = [
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
    # Connect plain first to ensure vector extension can be created
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
            # Add missing columns safely if upgrading existing tables
            cur.execute("ALTER TABLE rescue_teams ADD COLUMN IF NOT EXISTS username VARCHAR(100);")
            cur.execute("ALTER TABLE rescue_teams ADD COLUMN IF NOT EXISTS password VARCHAR(100);")
            cur.execute("ALTER TABLE missing_persons ADD COLUMN IF NOT EXISTS last_seen_latitude DOUBLE PRECISION;")
            cur.execute("ALTER TABLE missing_persons ADD COLUMN IF NOT EXISTS last_seen_longitude DOUBLE PRECISION;")

            # Seed camera locations
            for cname, (clat, clon) in DEFAULT_CAMERAS.items():
                cur.execute(
                    """INSERT INTO camera_locations (name, latitude, longitude)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (name) DO UPDATE SET latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude""",
                    (cname, clat, clon),
                )

            # Check rescue teams count
            cur.execute("SELECT COUNT(*) FROM rescue_teams")
            count_teams = cur.fetchone()[0]
            if count_teams == 0:
                for t in DEFAULT_SEED_TEAMS:
                    cur.execute(
                        """INSERT INTO rescue_teams
                           (name, organization_type, contact_phone, current_location_name, latitude, longitude, is_available, username, password)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (t["name"], t["org"], t["phone"], t["base_location"], t["lat"], t["lon"], t["available"], t["username"], t["password"]),
                    )
            else:
                # Update existing teams with default credentials and current phone numbers if NULL
                cur.execute("UPDATE rescue_teams SET username='helping_hands', password='ngo123', contact_phone='6303126628' WHERE name ILIKE '%Helping Hands%' AND (username IS NULL OR contact_phone != '6303126628');")
                cur.execute("UPDATE rescue_teams SET username='police_patrol', password='police123' WHERE name ILIKE '%Police%' AND username IS NULL;")
                cur.execute("UPDATE rescue_teams SET username='volunteer_a', password='volunteer123' WHERE name ILIKE '%Volunteer%' AND username IS NULL;")

            # Check missing persons count
            cur.execute("SELECT COUNT(*) FROM missing_persons")
            count_cases = cur.fetchone()[0]
            if count_cases == 0:
                for c in DEFAULT_SEED_CASES:
                    cur.execute(
                        """INSERT INTO missing_persons
                           (name, age, gender, clothes_description, last_seen_location, case_status, last_seen_latitude, last_seen_longitude)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                        (c["name"], c["age"], c["gender"], c["clothes"], c["last_seen_location"], c["status"], c["lat"], c["lon"]),
                    )
                    new_pid = cur.fetchone()[0]
                    # Link initial case assignment if team exists
                    cur.execute("SELECT id FROM rescue_teams WHERE name=%s LIMIT 1", (c["assigned_team"],))
                    t_row = cur.fetchone()
                    if t_row:
                        cur.execute(
                            "INSERT INTO case_assignments (missing_person_id, rescue_team_id, status) VALUES (%s, %s, 'ACTIVE')",
                            (new_pid, t_row[0]),
                        )
            else:
                # Backfill coordinates for existing cases from DEFAULT_CAMERAS if NULL
                for cname, (clat, clon) in DEFAULT_CAMERAS.items():
                    cur.execute(
                        """UPDATE missing_persons
                           SET last_seen_latitude=%s, last_seen_longitude=%s
                           WHERE (last_seen_latitude IS NULL OR last_seen_longitude IS NULL)
                             AND (last_seen_location ILIKE %s OR last_seen_location = %s)""",
                        (clat, clon, f"%{cname}%", cname),
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
                       m.last_seen_location, m.case_status, m.created_at,
                       m.last_seen_latitude, m.last_seen_longitude,
                       r.name AS assigned_team
                FROM missing_persons m
                LEFT JOIN LATERAL (
                    SELECT rescue_team_id FROM case_assignments
                    WHERE missing_person_id = m.id
                    ORDER BY id DESC LIMIT 1
                ) ca ON TRUE
                LEFT JOIN rescue_teams r ON ca.rescue_team_id = r.id
                ORDER BY m.id ASC
            """
            cur.execute(query)
            for r in cur.fetchall():
                pid, name, age, gender, clothes, loc, status, created_at, lat, lon, assigned_team = r
                created_str = created_at.strftime("%d %b, %H:%M") if hasattr(created_at, "strftime") else "Recently"
                default_coords = DEFAULT_CAMERAS.get(loc or "", (15.8281, 78.0373))
                cases.append({
                    "id": pid,
                    "name": name,
                    "age": age or 25,
                    "gender": gender or "Male",
                    "clothes": clothes or "",
                    "last_seen_location": loc or "CAR STAND",
                    "status": status or "ACTIVE",
                    "created_at": created_str,
                    "assigned_team": assigned_team or "Helping Hands NGO",
                    "lat": float(lat) if lat is not None else default_coords[0],
                    "lon": float(lon) if lon is not None else default_coords[1],
                })
        conn.close()
        if cases:
            return cases
    except Exception as exc:
        print(f"[!] load_cases_from_db fallback to memory: {exc}")
    return list(DEFAULT_SEED_CASES)


def save_case_to_db(case: Dict[str, Any], settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Insert a new missing person case into PostgreSQL and assign team."""
    try:
        conn = connect(settings, vector=False)
        with conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO missing_persons
                   (name, age, gender, clothes_description, last_seen_location, case_status, last_seen_latitude, last_seen_longitude)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id, created_at""",
                (
                    case.get("name", "Unnamed Case"),
                    case.get("age", 20),
                    case.get("gender", "Unknown"),
                    case.get("clothes", ""),
                    case.get("last_seen_location", "CAR STAND"),
                    case.get("status", "ACTIVE"),
                    float(case.get("lat", 15.8281)),
                    float(case.get("lon", 78.0373)),
                ),
            )
            row = cur.fetchone()
            new_id = row[0]
            created_at = row[1].strftime("%d %b, %H:%M") if hasattr(row[1], "strftime") else "Just now"
            case["id"] = new_id
            case["created_at"] = created_at

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
        print(f"[+] Case #{new_id} ({case.get('name')}) successfully saved to PostgreSQL.")
        return case
    except Exception as exc:
        print(f"[!] save_case_to_db warning: {exc}")
        return case


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
    """Fetch rescue teams / NGOs from PostgreSQL."""
    try:
        conn = connect(settings, vector=False)
        teams = []
        with conn, conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, organization_type, contact_phone, current_location_name,
                       latitude, longitude, is_available, username, password
                FROM rescue_teams
                ORDER BY id ASC
            """)
            for r in cur.fetchall():
                tid, name, org, phone, base, lat, lon, avail, uname, pwd = r
                teams.append({
                    "id": tid,
                    "name": name,
                    "org": org or "NGO",
                    "phone": phone or "N/A",
                    "base_location": base or "Base Station",
                    "lat": float(lat) if lat is not None else 15.8350,
                    "lon": float(lon) if lon is not None else 78.0450,
                    "available": bool(avail) if avail is not None else True,
                    "username": uname or f"ngo_{tid}",
                    "password": pwd or "ngo123",
                })
        conn.close()
        if teams:
            return teams
    except Exception as exc:
        print(f"[!] load_teams_from_db fallback to memory: {exc}")
    return list(DEFAULT_SEED_TEAMS)


def save_team_to_db(team: Dict[str, Any], settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Insert a new rescue team / NGO into PostgreSQL."""
    try:
        conn = connect(settings, vector=False)
        with conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO rescue_teams
                   (name, organization_type, contact_phone, current_location_name, latitude, longitude, is_available, username, password)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    team.get("name", "New Rescue Team"),
                    team.get("org", "NGO"),
                    team.get("phone", "6303126628"),
                    team.get("base_location", "Kurnool"),
                    float(team.get("lat", 15.8350)),
                    float(team.get("lon", 78.0450)),
                    team.get("available", True),
                    team.get("username", "new_team").strip(),
                    team.get("password", "ngo123").strip(),
                ),
            )
            new_id = cur.fetchone()[0]
            team["id"] = new_id
            conn.commit()
        conn.close()
        print(f"[+] Team #{new_id} ({team.get('name')}) successfully saved to PostgreSQL.")
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
