"""SQL access: persons, cameras, sightings, graph loading."""
from __future__ import annotations

from typing import List, Optional

from .graph import SightingGraph
from .models import GeoPoint, Location, Person, Sighting


def insert_person(cur, name, age, gender, photo_path, clothes, last_seen, embedding,
                  lat: Optional[float] = None, lon: Optional[float] = None):
    cur.execute("""INSERT INTO missing_persons
        (name, age, gender, photo_path, clothes_description, last_seen_location,
         last_seen_latitude, last_seen_longitude, face_embedding)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id, created_at""",
        (name, age, gender, photo_path, clothes, last_seen, lat, lon, embedding))
    return cur.fetchone()


def find_match(cur, embedding, threshold: float):
    """Nearest ACTIVE person by cosine distance. Returns (person_dict|None, distance)."""
    cur.execute("""SELECT id, name, age, gender, clothes_description, last_seen_location,
                          face_embedding <=> %s AS distance
                   FROM missing_persons
                   WHERE face_embedding IS NOT NULL AND case_status = 'ACTIVE'
                   ORDER BY distance ASC LIMIT 1""", (embedding,))
    row = cur.fetchone()
    if not row:
        return None, 1.0
    dist = float(row[6])
    if dist <= threshold:
        return {"id": row[0], "name": row[1], "age": row[2], "gender": row[3],
                "clothes": row[4], "last_seen": row[5], "distance": dist}, dist
    return None, dist


def get_or_create_camera(cur, name: str, lat: Optional[float] = None,
                         lon: Optional[float] = None) -> Optional[Location]:
    cur.execute("SELECT id, name, latitude, longitude FROM camera_locations WHERE name=%s", (name,))
    row = cur.fetchone()
    if not row:
        cur.execute("""INSERT INTO camera_locations (name, latitude, longitude)
                       VALUES (%s,%s,%s) RETURNING id, name, latitude, longitude""", (name, lat, lon))
        row = cur.fetchone()
    if row[2] is None or row[3] is None:
        return Location(row[0], row[1], GeoPoint(float("nan"), float("nan")))
    return Location(row[0], row[1], GeoPoint(row[2], row[3]))


def log_sighting(cur, person_id, camera: Optional[Location], source, ts_sec, frame_no, distance):
    cur.execute("""INSERT INTO person_sightings
        (missing_person_id, camera_id, video_source, video_timestamp_sec, frame_number, confidence_distance)
        VALUES (%s,%s,%s,%s,%s,%s)""",
        (person_id, camera.id if camera else None, source, ts_sec, frame_no, round(distance, 4)))
    if camera:
        cur.execute("UPDATE missing_persons SET last_seen_location=%s WHERE id=%s", (camera.name, person_id))


def load_graph(cur, connect_km: float = 1.5) -> SightingGraph:
    g = SightingGraph()
    cur.execute("""SELECT id, name, latitude, longitude FROM camera_locations
                   WHERE latitude IS NOT NULL AND longitude IS NOT NULL""")
    for r in cur.fetchall():
        g.add_location(Location(r[0], r[1], GeoPoint(r[2], r[3])))
    g.connect_nearby(connect_km)
    return g


def load_person(cur, person_id: int, graph: SightingGraph) -> Person:
    cur.execute("SELECT id, name, age, gender, clothes_description, case_status FROM missing_persons WHERE id=%s",
                (person_id,))
    r = cur.fetchone()
    if not r:
        raise LookupError(f"Person {person_id} not found")
    person = Person(r[0], r[1], r[2], r[3], r[4], r[5])
    cur.execute("""SELECT camera_id, spotted_at, confidence_distance, video_source
                   FROM person_sightings WHERE missing_person_id=%s AND camera_id IS NOT NULL
                   ORDER BY spotted_at""", (person_id,))
    for cam_id, ts, conf, src in cur.fetchall():
        try:
            loc = graph.location(cam_id)
        except KeyError:
            continue  # camera has no coordinates
        person.add_sighting(Sighting(person_id, loc, ts, float(conf) if conf is not None else None, src))
    return person
