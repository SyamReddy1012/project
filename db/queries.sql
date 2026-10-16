-- Dispatch overview
SELECT d.id AS dispatch_id, m.name AS person_name, r.name AS assigned_team,
       r.organization_type, r.contact_phone, d.sighting_location,
       d.distance_km, d.estimated_eta_minutes, d.status, d.dispatched_at
FROM rescue_dispatches d
JOIN missing_persons m ON d.missing_person_id = m.id
JOIN rescue_teams   r ON d.rescue_team_id = r.id
ORDER BY d.dispatched_at DESC;

-- Sighting history
SELECT s.id, m.name, c.name AS camera, s.confidence_distance, s.spotted_at
FROM person_sightings s
JOIN missing_persons m ON s.missing_person_id = m.id
LEFT JOIN camera_locations c ON s.camera_id = c.id
ORDER BY s.spotted_at DESC;
