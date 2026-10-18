import json
import unittest
from datetime import timedelta

from mptracker.demo import build_demo
from mptracker.dispatch import eta_minutes, nearest_team
from mptracker.models import GeoPoint, Person, RescueTeam
from mptracker.zones import SearchZoneAnalyzer, zones_to_geojson


class CoreTests(unittest.TestCase):
    def test_haversine_known_distance(self):
        d = GeoPoint(17.385, 78.4867).distance_km(GeoPoint(12.9716, 77.5946))
        self.assertTrue(495 < d < 505)

    def test_speed_by_age(self):
        self.assertEqual(Person(1, "a", age=8).speed_kmph, 3.0)
        self.assertEqual(Person(1, "a", age=30).speed_kmph, 4.5)
        self.assertEqual(Person(1, "a", age=70).speed_kmph, 3.0)

    def test_movement_edges_increment(self):
        g, _, _ = build_demo()
        self.assertEqual(g.neighbors(1)[2].traversals, 1)
        self.assertEqual(g.neighbors(2)[5].traversals, 1)
        self.assertEqual(g.neighbors(2)[1].traversals, 0)

    def test_dijkstra_truncates(self):
        g, _, _ = build_demo()
        self.assertEqual(set(g.shortest_distances(1, max_km=0.1)), {1})
        self.assertEqual(len(g.shortest_distances(1, max_km=50)), len(g))

    def test_probabilities_sum_to_one(self):
        g, _, _ = build_demo()
        probs = g.spread(5, set(g.shortest_distances(5, 5)))
        self.assertAlmostEqual(sum(probs.values()), 1.0)

    def test_zones_ranked_and_bounded_by_reach(self):
        g, person, now = build_demo()
        an = SearchZoneAnalyzer(g)
        zones = an.analyze(person, now=now, top_k=5)
        self.assertEqual([z.rank for z in zones], list(range(1, len(zones) + 1)))
        self.assertTrue(all(a.score >= b.score for a, b in zip(zones, zones[1:])))
        reach = an.reach_km(person, now)
        self.assertTrue(all(z.distance_km <= reach + 1e-9 for z in zones))

    def test_more_elapsed_time_widens_search(self):
        g, person, now = build_demo()
        an = SearchZoneAnalyzer(g)
        early = an.analyze(person, now=now, top_k=50)
        late = an.analyze(person, now=now + timedelta(hours=6), top_k=50)
        self.assertGreaterEqual(len(late), len(early))

    def test_no_sightings_raises(self):
        g, _, _ = build_demo()
        with self.assertRaises(ValueError):
            SearchZoneAnalyzer(g).analyze(Person(9, "x"))

    def test_nearest_available_team(self):
        teams = [RescueTeam(1, "far", "NGO", "1", GeoPoint(16.0, 78.0)),
                 RescueTeam(2, "near", "Police", "2", GeoPoint(15.83, 78.04)),
                 RescueTeam(3, "busy", "Police", "3", GeoPoint(15.8281, 78.0373), available=False)]
        team, km = nearest_team(teams, GeoPoint(15.8281, 78.0373))
        self.assertEqual(team.name, "near")
        self.assertLess(km, 2)
        self.assertIsNone(nearest_team([], GeoPoint(0, 0)))
        self.assertEqual(eta_minutes(30), 60.0)

    def test_geojson_valid(self):
        g, person, now = build_demo()
        data = json.loads(zones_to_geojson(SearchZoneAnalyzer(g).analyze(person, now=now)))
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertTrue(data["features"])

    def test_web_demo_data(self):
        from mptracker.web import _get_demo_data
        data = _get_demo_data(top_k=3, speed=4.0)
        self.assertEqual(len(data["zones"]), 3)
        self.assertEqual(data["person"]["name"], "Demo Person")
        self.assertIn("geojson", data)
        self.assertEqual(data["geojson"]["type"], "FeatureCollection")

    def test_shortest_path_and_stats(self):
        from mptracker.web import _calculate_shortest_route, _get_app_stats
        g, _, _ = build_demo()
        path, dist = g.shortest_path(1, 2)
        self.assertEqual(path[0], 1)
        self.assertEqual(path[-1], 2)
        self.assertGreater(dist, 0.0)

        route = _calculate_shortest_route(15.8310, 78.0420, 15.8350, 78.0450)
        self.assertIn("distance_km", route)
        self.assertIn("eta_minutes", route)
        self.assertGreater(len(route["waypoints"]), 0)
        self.assertIn("street_coordinates", route)
        self.assertIn("engine", route)
        self.assertGreaterEqual(len(route["street_coordinates"]), 2)

        stats = _get_app_stats()
        self.assertIn("total_cases", stats)
        self.assertIn("active_cases", stats)
        self.assertIn("closed_cases", stats)
        self.assertIn("total_teams", stats)

    def test_ngo_teams_and_credentials(self):
        from mptracker.web import APP_STATE
        teams = APP_STATE["teams"]
        self.assertGreaterEqual(len(teams), 3)
        for t in teams:
            self.assertIn("username", t)
            self.assertIn("password", t)
            self.assertIn("base_location", t)
            self.assertIn("lat", t)
            self.assertIn("lon", t)

    def test_case_allotment_notification(self):
        from mptracker.web import _send_case_allotment_notification, APP_STATE
        team = APP_STATE["teams"][0]
        case = APP_STATE["cases"][0]
        notif = _send_case_allotment_notification(case, team, "Immediate deployment test")
        self.assertEqual(notif["team_name"], team["name"])
        self.assertEqual(notif["case_id"], case["id"])
        self.assertIn("🚨 Case Allotment", notif["title"])
        self.assertIn("DELIVERED to", notif["sms_status"])
        self.assertFalse(notif["read"])
        self.assertIn(notif, APP_STATE["notifications"])

    def test_ngo_access_control(self):
        import json
        import threading
        import time
        import urllib.error
        import urllib.request
        from http.server import ThreadingHTTPServer
        from mptracker.web import MPTrackerHandler

        server = ThreadingHTTPServer(("127.0.0.1", 19888), MPTrackerHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        time.sleep(0.3)

        try:
            # NGO trying to add case -> expect 403 Forbidden
            payload = json.dumps({"name": "Unauthorized Case"}).encode("utf-8")
            req = urllib.request.Request(
                "http://127.0.0.1:19888/api/cases/add",
                data=payload,
                headers={"Content-Type": "application/json", "X-User-Role": "ngo"},
            )
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(req)
            self.assertEqual(cm.exception.code, 403)

            # NGO trying to add team -> expect 403 Forbidden
            req_team = urllib.request.Request(
                "http://127.0.0.1:19888/api/teams/add",
                data=payload,
                headers={"Content-Type": "application/json", "X-User-Role": "ngo"},
            )
            with self.assertRaises(urllib.error.HTTPError) as cm_team:
                urllib.request.urlopen(req_team)
            self.assertEqual(cm_team.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()

