# Missing Person Search-and-Track System

**Problem Statement 112** – Build a missing-person tracking system that uses **graph-based last-seen
network analysis** to model reported sighting locations as connected nodes, helping investigators
identify likely **search zones** from movement patterns. Persons, sightings and search zones are
modelled with **OOP**, so police and disaster-response teams can organise searches systematically
instead of ad hoc.

## How it works

```
 photo ──► ArcFace embedding ──► pgvector (PostgreSQL)
 CCTV / crowd photo / video ──► face match ──► Sighting (camera = graph node)
                                      │
                                      ├─► nearest rescue team dispatched (ETA)
                                      ▼
              Sighting graph (nodes = locations, edges = roads + observed movement)
                                      ▼
        Dijkstra reach (speed × elapsed time) + random-walk likelihood
                                      ▼
                     Ranked SearchZones  ─► table / GeoJSON map
```

| Module | Responsibility |
|---|---|
| `mptracker/models.py` | OOP model: `GeoPoint`, `Location`, `Person`, `Sighting`, `SearchZone`, `RescueTeam` |
| `mptracker/graph.py` | `SightingGraph`: nodes/edges, Dijkstra, transition probabilities, random-walk spread |
| `mptracker/zones.py` | `SearchZoneAnalyzer`: ranks likely zones; GeoJSON export |
| `mptracker/face.py` | DeepFace ArcFace embedding, crowd photo/video scan |
| `mptracker/repository.py` | SQL access, builds graph and persons from DB |
| `mptracker/dispatch.py` | Nearest-available-team dispatch, resolve outcomes |
| `mptracker/cli.py` | Command line entry point |
| `db/schema.sql` | Single consolidated schema |

### The algorithm
1. **Nodes**: every camera/landmark with coordinates. **Edges**: locations within `--connect-km`
   (geographic links) plus *observed movement* – each time a person is seen at A then B, the A→B edge
   `traversals` count goes up.
2. **Reachability**: `reach = speed × hours since last sighting` (children/elderly 3 km/h, others
   4.5 km/h; override with `--speed`). Dijkstra finds all nodes within reach.
3. **Likelihood**: a decaying random walk from the last-seen node. Transition weight
   `(1 + traversals) / (0.5 + distance_km)` favours near nodes and routes people have really used.
4. **Output**: top-K `SearchZone`s with score, distance, suggested radius and reason.

## Quick start (no database needed)

```bash
git clone <your-repo-url> && cd missing-person-tracker
python -m mptracker demo --geojson zones.geojson     # drop zones.geojson on https://geojson.io
python -m mptracker web                             # interactive web dashboard (http://localhost:10000)
python -m unittest discover -s tests -v
```

## Full setup

```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # then edit DB_PASSWORD
python -m mptracker init-db                           # needs PostgreSQL + pgvector extension
psql -d FACEPROJECT -f db/sample_teams.sql            # optional sample rescue teams
```

### Usage

```bash
# 1. enroll a missing person
python -m mptracker enroll --name "Ravi" --age 10 --gender Male \
       --clothes "Blue shirt" --last-seen "Bus Stand" --photo photos/ravi.jpg

# 2. scan footage from a camera (creates a graph node, logs sighting, auto-dispatches nearest team)
python -m mptracker scan-photo crowd.jpg --camera "Kurnool Bus Stand" --lat 15.8281 --lon 78.0373 --dispatch
python -m mptracker scan-video cctv.mp4  --camera "Railway Station"   --lat 15.8310 --lon 78.0420 --dispatch

# 3. where should we search next?
python -m mptracker analyze 1 --top 5 --geojson zones.geojson

# 4. field team feedback
python -m mptracker dispatches
python -m mptracker resolve 1 --outcome found --notes "Reunited with family"
#   outcomes: found | not-found | false-alarm
```

## Security & ethics
* Credentials live in `.env` (git-ignored) – never commit them.
* Face data of real people is sensitive. Don't commit photos or embeddings; follow local law and
  keep access restricted to authorised agencies.
* A face match is a **lead, not proof** – always verify in person (hence `false-alarm` outcome).
  Tune `COSINE_THRESHOLD` (lower = fewer false positives).

## Roadmap
Real road-network distances (OSRM), live camera streams, web map dashboard, multi-person graph learning.

## License
MIT
