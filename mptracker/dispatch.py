"""Nearest-team selection, dispatch creation and resolution."""
from __future__ import annotations

from typing import List, Optional, Tuple

from .models import GeoPoint, RescueTeam

AVG_RESPONSE_SPEED_KMPH = 30.0
OUTCOMES = {"found": "VERIFIED_FOUND", "not-found": "NOT_FOUND", "false-alarm": "FALSE_ALARM"}


def nearest_team(teams: List[RescueTeam], point: GeoPoint) -> Optional[Tuple[RescueTeam, float]]:
    candidates = [(t, t.point.distance_km(point)) for t in teams if t.available]
    return min(candidates, key=lambda x: x[1]) if candidates else None


def eta_minutes(distance_km: float, speed_kmph: float = AVG_RESPONSE_SPEED_KMPH) -> float:
    return round(distance_km / speed_kmph * 60.0, 1)


def available_teams(cur) -> List[RescueTeam]:
    cur.execute("""SELECT id, name, organization_type, contact_phone, latitude, longitude
                   FROM rescue_teams WHERE is_available = TRUE AND latitude IS NOT NULL""")
    return [RescueTeam(r[0], r[1], r[2], r[3], GeoPoint(float(r[4]), float(r[5]))) for r in cur.fetchall()]


def has_open_dispatch(cur, person_id: int) -> bool:
    cur.execute("SELECT 1 FROM rescue_dispatches WHERE missing_person_id=%s AND status='EN_ROUTE' LIMIT 1",
                (person_id,))
    return cur.fetchone() is not None


def create_dispatch(cur, person_id: int, place_name: str, point: GeoPoint):
    """Assign the nearest available team. Returns (team, km, eta) or None."""
    if has_open_dispatch(cur, person_id):
        return None
    found = nearest_team(available_teams(cur), point)
    if not found:
        return None
    team, km = found
    eta = eta_minutes(km)
    cur.execute("""INSERT INTO rescue_dispatches
                   (missing_person_id, rescue_team_id, sighting_location, distance_km, estimated_eta_minutes)
                   VALUES (%s,%s,%s,%s,%s)""", (person_id, team.id, place_name, round(km, 2), eta))
    cur.execute("UPDATE rescue_teams SET is_available = FALSE WHERE id = %s", (team.id,))
    return team, km, eta


def list_active(cur):
    cur.execute("""SELECT d.id, m.name, r.name, d.sighting_location, d.dispatched_at
                   FROM rescue_dispatches d
                   JOIN missing_persons m ON d.missing_person_id = m.id
                   JOIN rescue_teams r ON d.rescue_team_id = r.id
                   WHERE d.status='EN_ROUTE' ORDER BY d.dispatched_at DESC""")
    return cur.fetchall()


def resolve(cur, dispatch_id: int, outcome: str, notes: str = "") -> str:
    """outcome: found | not-found | false-alarm. Frees the team in all cases."""
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {list(OUTCOMES)}")
    cur.execute("""SELECT missing_person_id, rescue_team_id, sighting_location
                   FROM rescue_dispatches WHERE id=%s""", (dispatch_id,))
    row = cur.fetchone()
    if not row:
        raise LookupError(f"Dispatch {dispatch_id} not found")
    person_id, team_id, place = row
    cur.execute("""UPDATE rescue_dispatches SET status=%s, responder_notes=%s,
                   resolved_at=CURRENT_TIMESTAMP WHERE id=%s""", (OUTCOMES[outcome], notes, dispatch_id))
    if outcome == "found":
        cur.execute("UPDATE missing_persons SET case_status='RESCUED' WHERE id=%s", (person_id,))
    elif outcome == "not-found":
        cur.execute("UPDATE missing_persons SET last_seen_location=%s WHERE id=%s",
                    (f"Last CCTV Sighting: {place}", person_id))
    cur.execute("UPDATE rescue_teams SET is_available=TRUE WHERE id=%s", (team_id,))
    return OUTCOMES[outcome]
