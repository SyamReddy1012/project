"""Self-contained demo (no database / no face model needed)."""
from __future__ import annotations

from datetime import datetime, timedelta

from .graph import SightingGraph
from .models import GeoPoint, Location, Person, Sighting

# Illustrative, approximate coordinates around Kurnool.
PLACES = [
    (1, "Kurnool Bus Stand",     15.8281, 78.0373),
    (2, "Kurnool City Railway",  15.8310, 78.0420),
    (3, "Konda Reddy Fort",      15.8340, 78.0560),
    (4, "Collectorate",          15.8200, 78.0450),
    (5, "Budhwarpet Market",     15.8350, 78.0450),
    (6, "Government Hospital",   15.8150, 78.0300),
    (7, "Nandyal Road Junction", 15.8100, 78.0600),
    (8, "Tungabhadra Bridge",    15.8420, 78.0300),
]


def build_demo():
    graph = SightingGraph()
    for i, name, lat, lon in PLACES:
        graph.add_location(Location(i, name, GeoPoint(lat, lon)))
    graph.connect_nearby(2.0)

    now = datetime.now()
    person = Person(id=1, name="Demo Person", age=10, gender="Male", clothes="Blue shirt, black shorts")
    for loc_id, mins_ago in [(1, 150), (2, 120), (5, 90)]:
        person.add_sighting(Sighting(1, graph.location(loc_id), now - timedelta(minutes=mins_ago),
                                     0.31, "demo-cctv"))
    graph.ingest_person(person)
    return graph, person, now
