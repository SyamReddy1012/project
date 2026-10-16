-- Consolidated schema for the Missing Person Search-and-Track System.
-- Run:  python -m mptracker init-db      (or psql -f db/schema.sql)

CREATE EXTENSION IF NOT EXISTS vector;

-- Persons -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS missing_persons (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    age INTEGER,
    gender VARCHAR(20),
    photo_path TEXT,
    clothes_description TEXT,
    last_seen_location TEXT,
    last_seen_latitude  DOUBLE PRECISION,
    last_seen_longitude DOUBLE PRECISION,
    case_status VARCHAR(20) DEFAULT 'ACTIVE',      -- ACTIVE | RESCUED | CLOSED
    face_embedding VECTOR(512),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS missing_persons_face_idx
    ON missing_persons USING hnsw (face_embedding vector_cosine_ops);

-- Camera / sighting locations = NODES of the graph -------------------------
CREATE TABLE IF NOT EXISTS camera_locations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) UNIQUE NOT NULL,
    latitude  DOUBLE PRECISION,
    longitude DOUBLE PRECISION
);

-- Sightings = EVENTS that create the EDGES of the graph ----------------------
CREATE TABLE IF NOT EXISTS person_sightings (
    id SERIAL PRIMARY KEY,
    missing_person_id INTEGER REFERENCES missing_persons(id) ON DELETE CASCADE,
    camera_id INTEGER REFERENCES camera_locations(id),
    video_source TEXT NOT NULL,
    video_timestamp_sec NUMERIC(8, 2),
    frame_number INTEGER,
    confidence_distance NUMERIC(5, 4),
    crop_snapshot_path TEXT,
    spotted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sightings_person_id  ON person_sightings(missing_person_id);
CREATE INDEX IF NOT EXISTS idx_sightings_spotted_at ON person_sightings(spotted_at DESC);

-- Response teams & dispatch ------------------------------------------------
CREATE TABLE IF NOT EXISTS rescue_teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    organization_type VARCHAR(50),                  -- NGO | Police | Volunteer
    contact_phone VARCHAR(20) NOT NULL,
    current_location_name VARCHAR(100),
    latitude  NUMERIC(9, 6),
    longitude NUMERIC(9, 6),
    is_available BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS case_assignments (
    id SERIAL PRIMARY KEY,
    missing_person_id INTEGER REFERENCES missing_persons(id) ON DELETE CASCADE,
    rescue_team_id INTEGER REFERENCES rescue_teams(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS rescue_dispatches (
    id SERIAL PRIMARY KEY,
    missing_person_id INTEGER REFERENCES missing_persons(id),
    rescue_team_id INTEGER REFERENCES rescue_teams(id),
    sighting_location VARCHAR(100),
    distance_km NUMERIC(6, 2),
    estimated_eta_minutes NUMERIC(5, 1),
    dispatched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(30) DEFAULT 'EN_ROUTE',          -- EN_ROUTE | VERIFIED_FOUND | NOT_FOUND | FALSE_ALARM
    responder_notes TEXT,
    resolved_at TIMESTAMP
);
