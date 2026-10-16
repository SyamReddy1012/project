"""Search-zone analysis: rank where investigators should look next."""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from .graph import SightingGraph
from .models import Person, SearchZone


class SearchZoneAnalyzer:
    def __init__(self, graph: SightingGraph, steps: int = 4, stay: float = 0.25,
                 decay: float = 0.8, min_reach_km: float = 0.5, max_reach_km: float = 30.0):
        self.graph = graph
        self.steps = steps
        self.stay = stay
        self.decay = decay
        self.min_reach_km = min_reach_km
        self.max_reach_km = max_reach_km

    def reach_km(self, person: Person, now: datetime, speed_kmph: Optional[float] = None) -> float:
        last = person.last_sighting
        hours = max(0.0, (now - last.timestamp).total_seconds() / 3600.0)
        speed = speed_kmph if speed_kmph is not None else person.speed_kmph
        return min(self.max_reach_km, max(self.min_reach_km, speed * hours))

    def analyze(self, person: Person, now: Optional[datetime] = None, top_k: int = 5,
                speed_kmph: Optional[float] = None) -> List[SearchZone]:
        last = person.last_sighting
        if last is None:
            raise ValueError(f"Person {person.id} has no sightings to analyze")
        now = now or datetime.now()
        reach = self.reach_km(person, now, speed_kmph)
        dist = self.graph.shortest_distances(last.location.id, max_km=reach)
        allowed = set(dist)
        probs = self.graph.spread(last.location.id, allowed, self.steps, self.stay, self.decay)

        zones: List[SearchZone] = []
        for node_id, score in probs.items():
            d = dist.get(node_id, 0.0)
            loc = self.graph.location(node_id)
            reason = ("last confirmed sighting" if node_id == last.location.id
                      else f"{d:.1f} km from last sighting, reachable in "
                           f"{d / (speed_kmph or person.speed_kmph) * 60:.0f} min")
            zones.append(SearchZone(
                location=loc, score=score, distance_km=d,
                radius_km=min(3.0, max(0.25, 0.5 * (reach - d))), reason=reason))
        zones.sort(key=lambda z: z.score, reverse=True)
        zones = zones[:top_k]
        for i, z in enumerate(zones, 1):
            z.rank = i
        return zones


def zones_to_geojson(zones: List[SearchZone]) -> str:
    """GeoJSON for dropping onto geojson.io / QGIS / Leaflet."""
    feats = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [z.location.point.lon, z.location.point.lat]},
        "properties": z.to_dict(),
    } for z in zones]
    return json.dumps({"type": "FeatureCollection", "features": feats}, indent=2)
