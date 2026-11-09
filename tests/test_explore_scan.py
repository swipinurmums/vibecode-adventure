import unittest
from unittest.mock import patch

from explore_scan import fetch_explore


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class EmptyRegionalResultsTests(unittest.TestCase):
    def test_known_empty_region_response_is_a_valid_empty_scan(self):
        payload = {
            "error": 'Empty results for departure_id: "LBA" and arrival_area_id: "/m/0j0k".'
        }
        config = {
            "localisation": {"gl": "uk", "hl": "en", "currency": "GBP"},
            "flight": {},
        }
        with patch("explore_scan.requests.get", return_value=FakeResponse(payload)):
            result = fetch_explore("key", "LBA", config, "/m/0j0k")
        self.assertEqual(result["destinations"], [])
        self.assertIn("_empty_results_reason", result)

    def test_real_api_errors_still_raise(self):
        payload = {"error": "Invalid API key"}
        config = {
            "localisation": {"gl": "uk", "hl": "en", "currency": "GBP"},
            "flight": {},
        }
        with patch("explore_scan.requests.get", return_value=FakeResponse(payload)):
            with self.assertRaises(RuntimeError):
                fetch_explore("key", "LBA", config, "/m/0j0k")


if __name__ == "__main__":
    unittest.main()
