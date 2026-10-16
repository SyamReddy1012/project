"""Domain model (OOP): GeoPoint, Location, Person, Sighting, SearchZone, RescueTeam."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lon: float

    def distance_km(self, other: "GeoPoint") -> float:
        """Great-circle (haversine) distance in kilometres."""
        p1, p2 = math.radians(self.lat), math.radians(other.lat)
        dphi = p2 - p1
        dlmb = math.radians(other.lon - self.lon)
        a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
        return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class Location:
    """A named place (camera / landmark). Becomes a NODE in the sighting graph."""
    id: int
    name: str
    point: GeoPoint

    def distance_km(self, other: "Location") -> float:
        return self.point.distance_km(other.point)


@dataclass
class Sighting:
    """A confirmed/probable observation of a person at a location and time."""
    person_id: int
    location: Location
    timestamp: datetime
    confidence_distance: Optional[float] = None  # cosine distance, lower = better
    source: str = ""


@dataclass
class Person:
    id: int
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    clothes: Optional[str] = None
    status: str = "ACTIVE"
    sightings: List[Sighting] = field(default_factory=list)

    def add_sighting(self, sighting: Sighting) -> None:
        self.sightings.append(sighting)
        self.sightings.sort(key=lambda s: s.timestamp)

    @property
    def last_sighting(self) -> Optional[Sighting]:
        return self.sightings[-1] if self.sightings else None

    @property
    def speed_kmph(self) -> float:
        """Assumed walking speed; children and elderly move slower."""
        if self.age is not None and (self.age < 12 or self.age >= 65):
            return 3.0
        return 4.5


@dataclass
class SearchZone:
    """A ranked area investigators should search."""
    location: Location
    score: float          # 0..1 relative likelihood
    distance_km: float    # from last-seen location along the network
    radius_km: float      # suggested search radius
    rank: int = 0
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "location": self.location.name,
            "lat": self.location.point.lat,
            "lon": self.location.point.lon,
            "score": round(self.score, 4),
            "distance_km": round(self.distance_km, 2),
            "radius_km": round(self.radius_km, 2),
            "reason": self.reason,
        }


@dataclass
class RescueTeam:
    id: int
    name: str
    organization_type: str
    phone: str
    point: GeoPoint
    available: bool = True
