# Problem Statement 112: Missing Person Search-and-Track System

**Registered Numbers:** `25091A32M7`, `25091A3222`  
**Problem Statement:** No. 112  
**Database:** PostgreSQL with `pgvector` extension  
**Language & Framework:** Python 3.11, OpenCV, DeepFace, Network Graph Analysis  

---

## 1. Project Overview
The **Missing Person Search-and-Track System** is an intelligent investigation and disaster-response decision support tool. It models reported sighting locations as connected nodes in a dynamic graph network. By combining:
- **Facial feature vector embeddings (ArcFace)** stored in **PostgreSQL (`pgvector`)**,
- **Geographic and temporal movement models** (speed based on age/profile, elapsed time, road connectivity), and
- **Dijkstra reachability + decaying random-walk transition probabilities**,

the system automatically computes and ranks high-probability **Search Zones** for police and rescue units, replacing ad-hoc search operations with systematic, data-driven response.

---

## 2. Object-Oriented Programming (OOP) Architecture

The project strictly follows OOP principles:

| Class / Model | File | Description |
|---|---|---|
| `GeoPoint` | `mptracker/models.py` | Encapsulates latitude/longitude with Haversine spherical distance calculation. |
| `Location` | `mptracker/models.py` | Represents a geographical node (camera, bus stand, railway station, landmark). |
| `Person` | `mptracker/models.py` | Models a missing individual with age, gender, clothing description, and face embeddings. Calculates profile-based walking speed. |
| `Sighting` | `mptracker/models.py` | Represents an event node when a face is detected at a specific camera location and timestamp. |
| `SearchZone` | `mptracker/models.py` | Represents a prioritized search perimeter with probability score, distance, and radius. |
| `RescueTeam` | `mptracker/models.py` | Models available police/NGO/volunteer dispatch teams with ETA and real-time status. |
| `SightingGraph` | `mptracker/graph.py` | Graph data structure modeling locations as vertices and movement/routes as weighted edges. Executes Dijkstra reachability and transition probabilities. |
| `SearchZoneAnalyzer`| `mptracker/zones.py` | Coordinates graph traversals and formats ranked output as tables and GeoJSON. |
| `Repository` | `mptracker/repository.py` | Data Access Object (DAO) interfacing directly with PostgreSQL. |

---

## 3. Database Design (PostgreSQL + pgvector)

The system exclusively utilizes **PostgreSQL** with the **`vector`** extension (`pgvector`):

- **`missing_persons`**: Stores person bio, clothing details, status, and 512-dimensional vector embedding indexed using HNSW (`missing_persons_face_idx USING hnsw (face_embedding vector_cosine_ops)`).
- **`camera_locations`**: Graph nodes representing fixed cameras or landmarks with geographic coordinates.
- **`person_sightings`**: Graph event sightings recording camera ID, frame number, confidence distance, snapshot path, and timestamp.
- **`rescue_teams`**: Registry of police, NGO, and volunteer teams with their coordinates and availability.
- **`rescue_dispatches`**: Real-time dispatch records linking missing persons, sightings, ETA, and field resolution status.
- **`case_assignments`**: Tracking investigative ownership of active cases.

---

## 4. How to Run in VS Code

1. Open the project folder in VS Code:
   ```powershell
   code "c:\Users\Syam Sundar\OneDrive\Desktop\missing-person-tracker"
   ```
2. When prompted by VS Code, click **Install All** to install the recommended extensions (`Python`, `PostgreSQL`, `Jupyter`, `Pylance`, `GeoData Viewer`).
3. Open the integrated terminal (`Ctrl + ~`) and activate the virtual environment:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
4. Run commands:
   - **Demo Graph Search**:
     ```powershell
     python -m mptracker demo --geojson zones.geojson
     ```
   - **Run Unit Tests**:
     ```powershell
     python -m unittest discover -s tests -v
     ```
   - **View Rescue Dispatches**:
     ```powershell
     python -m mptracker dispatches
     ```
   - **Jupyter Notebooks**: Open any notebook in `notebooks/` (`enroll_person.ipynb`, `search_crowd.ipynb`, `SQL.ipynb`) and click **Run All**.
