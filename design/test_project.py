import unittest
from urllib.parse import parse_qs, urlparse

import app as backend
import risk_engine as re
from distance import haversine, nearest_shelter

SCENARIOS = backend.load_json(backend.DEMO_FILE)["scenarios"]


def run_scenario(name):
    s = SCENARIOS[name]
    return re.assess_risk(s["weather"]["rainfall"], s["weather"]["wind_speed"], s["flood_level"])


class TestScenarios(unittest.TestCase):
    def test_low_risk(self):
        r = run_scenario("low")
        self.assertEqual(r["score"], 13)
        self.assertEqual(r["level"], "SAFE")

    def test_moderate_risk(self):
        r = run_scenario("moderate")
        self.assertEqual(r["score"], 43)
        self.assertEqual(r["level"], "EVACUATE")

    def test_high_risk(self):
        r = run_scenario("high")
        self.assertEqual(r["score"], 73)
        self.assertEqual(r["level"], "EVACUATE IMMEDIATELY")
        self.assertEqual(r["reasons"], [
            "Heavy rainfall detected (20 mm)",
            "Strong wind detected (50 km/h)",
            "Elevated demo flood level (0.8 m)",
        ])

    def test_extremes(self):
        self.assertEqual(re.assess_risk(0, 0, 0)["score"], 7)
        self.assertEqual(re.assess_risk(52, 64, 1.2)["score"], 100)

    def test_deterministic(self):
        results = {str(re.assess_risk(12.3, 45.6, 0.7)) for _ in range(20)}
        self.assertEqual(len(results), 1)


class TestBoundaries(unittest.TestCase):
    def test_classification_thresholds(self):
        cases = {0: "SAFE", 30: "SAFE", 31: "EVACUATE", 60: "EVACUATE",
                 61: "EVACUATE IMMEDIATELY", 100: "EVACUATE IMMEDIATELY"}
        for score, level in cases.items():
            self.assertEqual(re.classify_score(score), level, score)

    def test_band_edges(self):
        self.assertEqual(re.band_score(2.5, re.RAINFALL_BANDS)[0], 50)
        self.assertEqual(re.band_score(2.4, re.RAINFALL_BANDS)[0], 20)
        self.assertEqual(re.band_score(62, re.WIND_BANDS)[0], 100)
        self.assertEqual(re.band_score(61.9, re.WIND_BANDS)[0], 70)
        self.assertEqual(re.band_score(1.0, re.FLOOD_BANDS)[0], 100)
        self.assertEqual(re.band_score(0.99, re.FLOOD_BANDS)[0], 70)

    def test_real_inputs_hit_both_sides_of_thresholds(self):
        self.assertEqual(re.assess_risk(7.6, 40, 0.3)["score"], 58)
        self.assertEqual(re.assess_risk(7.6, 40, 0.6)["score"], 73)


class TestMissingAndInvalid(unittest.TestCase):
    def test_missing_rain_and_wind_treated_as_zero(self):
        r = re.assess_risk(None, None, 0.4)
        self.assertEqual(r["score"], 22)
        self.assertIn("Rainfall data unavailable (treated as 0 mm)", r["reasons"])
        self.assertIn("Wind speed data unavailable (treated as 0 km/h)", r["reasons"])

    def test_missing_flood_uses_demo_value(self):
        r = re.assess_risk(0, 0)
        self.assertEqual(r["components"]["flood_level"]["value"], re.DEMO_FLOOD_LEVEL)

    def test_invalid_values(self):
        for bad in ("abc", -1, True, [1]):
            with self.assertRaises(ValueError):
                re.assess_risk(bad, 10, 0.5)


class TestDistance(unittest.TestCase):
    def test_same_point_is_zero(self):
        self.assertAlmostEqual(haversine(18.5204, 73.8567, 18.5204, 73.8567), 0)

    def test_known_distance_pune_mumbai(self):
        self.assertAlmostEqual(haversine(18.5204, 73.8567, 19.0760, 72.8777), 119.9, delta=1)

    def test_nearest_of_multiple(self):
        shelters = [
            {"name": "Far", "latitude": 19.0, "longitude": 73.0},
            {"name": "Near", "latitude": 18.53, "longitude": 73.86},
            {"name": "Middle", "latitude": 18.6, "longitude": 73.9},
        ]
        best, d = nearest_shelter(18.5204, 73.8567, shelters)
        self.assertEqual(best["name"], "Near")
        self.assertLess(d, 1.2)

    def test_nearest_matches_brute_force_on_real_file(self):
        shelters = backend.load_shelters()
        self.assertGreaterEqual(len(shelters), 5)
        for lat, lng in [(22.5726, 88.3639), (22.59, 88.28), (22.47, 88.39), (22.63, 88.43)]:
            best, d = nearest_shelter(lat, lng, shelters)
            expected = min(shelters, key=lambda s: haversine(lat, lng, s["latitude"], s["longitude"]))
            self.assertEqual(best["id"], expected["id"])
            self.assertIn("Kolkata", best["address"])
            self.assertLess(d, 5)

    def test_empty_list(self):
        self.assertEqual(nearest_shelter(18.5, 73.8, []), (None, None))


class TestApi(unittest.TestCase):
    def setUp(self):
        self.c = backend.app.test_client()

    def post(self, body):
        return self.c.post("/api/assess-risk", json=body)

    def test_full_request(self):
        r = self.post({"latitude": 22.5726, "longitude": 88.3639,
                       "rainfall": 20, "wind_speed": 50, "flood_level": 0.8})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["risk"]["score"], 73)
        self.assertEqual(data["flood_level"]["label"], "DEMO FLOOD DATA")
        self.assertEqual(set(data["shelter"]), {"name", "address", "latitude", "longitude", "capacity"})
        self.assertIsInstance(data["distance_km"], float)

    def test_route_goes_from_user_to_nearest_shelter(self):
        data = self.post({"latitude": 22.5726, "longitude": 88.3639,
                          "rainfall": 5, "wind_speed": 30, "flood_level": 0.4}).get_json()
        url = urlparse(data["route"]["url"])
        q = parse_qs(url.query)
        self.assertEqual(f"{url.scheme}://{url.netloc}{url.path}", "https://www.google.com/maps/dir/")
        self.assertEqual(q["api"], ["1"])
        self.assertEqual(q["origin"], ["22.5726,88.3639"])
        self.assertEqual(q["destination"], [f"{data['shelter']['latitude']},{data['shelter']['longitude']}"])
        self.assertEqual(q["travelmode"], ["driving"])
        self.assertEqual(data["route"]["label"], "Suggested Evacuation Route")

    def test_demo_mode_all_scenarios(self):
        expected = {"low": "SAFE", "moderate": "EVACUATE", "high": "EVACUATE IMMEDIATELY"}
        for name, level in expected.items():
            r = self.c.get(f"/api/demo/{name}")
            self.assertEqual(r.status_code, 200)
            data = r.get_json()
            self.assertTrue(data["demo"])
            self.assertEqual(data["risk"]["level"], level)
            for key in ("location", "weather", "flood_level", "shelter", "distance_km", "route"):
                self.assertIn(key, data)
        self.assertEqual(self.c.get("/api/demo/extreme").status_code, 404)

    def test_no_shelter(self):
        original = backend.load_shelters
        backend.load_shelters = lambda: []
        try:
            r = self.post({"latitude": 18.52, "longitude": 73.85, "rainfall": 1})
            self.assertEqual(r.status_code, 500)
            self.assertIn("No emergency shelter", r.get_json()["error"])
        finally:
            backend.load_shelters = original

    def test_missing_values(self):
        r = self.post({"latitude": 18.5204, "longitude": 73.8567})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["flood_level"]["value"], re.DEMO_FLOOD_LEVEL)

    def test_invalid_coordinates(self):
        for body in ({"latitude": 91, "longitude": 73}, {"latitude": 18, "longitude": 181},
                     {"latitude": "x", "longitude": 73}, {"rainfall": 5}):
            self.assertEqual(self.post(body).status_code, 400, body)

    def test_invalid_weather_value(self):
        r = self.post({"latitude": 18.52, "longitude": 73.85, "rainfall": -5})
        self.assertEqual(r.status_code, 400)
        self.assertIn("rainfall cannot be negative", r.get_json()["error"])

    def test_not_json(self):
        self.assertEqual(self.c.post("/api/assess-risk", data="x").status_code, 400)


if __name__ == "__main__":
    unittest.main()