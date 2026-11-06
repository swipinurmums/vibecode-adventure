import unittest
from flight_insights import classify_price_insight, normalise


class FlightInsightTests(unittest.TestCase):
    def test_strong_discount_uses_typical_range_lower_bound(self):
        result = classify_price_insight(80, [100, 150])
        self.assertEqual(result["benchmark_status"], "strong_deal")
        self.assertEqual(result["discount_vs_typical_low_percent"], 20.0)

    def test_small_discount_is_below_typical(self):
        self.assertEqual(classify_price_insight(95, [100, 150])["benchmark_status"], "below_typical")

    def test_price_inside_range_is_typical(self):
        self.assertEqual(classify_price_insight(120, [100, 150])["benchmark_status"], "typical")

    def test_price_above_range_is_above_typical(self):
        self.assertEqual(classify_price_insight(180, [100, 150])["benchmark_status"], "above_typical")

    def test_missing_or_invalid_insights_do_not_invent_a_benchmark(self):
        result = classify_price_insight(None, [])
        self.assertEqual(result["benchmark_status"], "insufficient_price_insights")
        self.assertIsNone(result["discount_vs_typical_low_percent"])

    def test_normalise_preserves_trip_identity_and_price_history(self):
        row = normalise({"price_insights": {
            "lowest_price": 80, "price_level": "low",
            "typical_price_range": [100, 150], "price_history": [[1, 110]]
        }}, {"origin": "MAN", "destination": "Rome", "country": "Italy",
             "departure_date": "2027-05-01", "return_date": "2027-05-08",
             "flight_price_gbp": 90})
        self.assertEqual(row["origin"], "MAN")
        self.assertEqual(row["typical_price_low_gbp"], 100)
        self.assertEqual(row["benchmark_status"], "strong_deal")
        self.assertEqual(row["price_history"], [[1, 110]])


if __name__ == "__main__":
    unittest.main()
