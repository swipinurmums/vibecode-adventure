import csv
import tempfile
import unittest
from pathlib import Path
from hotel_scan import (hotel_search_query, load_flight_candidates, normalise, valid_nights,\n                         generate_flexible_stays)


class HotelMatchingTests(unittest.TestCase):
    def test_flexible_month_search_samples_valid_future_date_pairs(self):\n        stays = generate_flexible_stays("2027-06", "2027-06", 5, 7, 4, today=__import__("datetime").date(2026, 11, 9))\n        self.assertEqual(len(stays), 4)\n        for check_in, check_out in stays:\n            self.assertEqual(check_in[:7], "2027-06")\n            self.assertEqual(check_out[:7], "2027-06")\n            self.assertIn(valid_nights(check_in, check_out), (5, 6, 7))\n\n    def test_flexible_month_search_supports_different_months(self):\n        stays = generate_flexible_stays("2027-06", "2027-07", 5, 7, 5, today=__import__("datetime").date(2026, 11, 9))\n        self.assertTrue(stays)\n        self.assertTrue(all(start[:7] == "2027-06" and end[:7] == "2027-07" for start, end in stays))\n\n    def test_flexible_month_search_rejects_impossible_month_and_duration(self):\n        with self.assertRaises(ValueError):\n            generate_flexible_stays("2027-06", "2027-06", 20, 25, 5, today=__import__("datetime").date(2026, 11, 9))\n\n    def test_trip_dates_are_taken_from_flight_row(self):
        self.assertEqual(valid_nights("2027-01-10", "2027-01-17"), 7)
        self.assertEqual(valid_nights("2027-01-17", "2027-01-17"), 0)
        self.assertEqual(valid_nights("bad-date", "2027-01-17"), 0)

    def test_candidate_uses_discovered_dates_and_price_filter(self):
        rows = [
            {"origin":"MAN","destination":"Bangkok","country":"Thailand",
             "departure_date":"2027-01-10","return_date":"2027-01-17",
             "flight_price_gbp":"440","stops":"1","airline":"Example"},
            {"origin":"MAN","destination":"Milan","country":"Italy",
             "departure_date":"2027-02-10","return_date":"2027-02-17",
             "flight_price_gbp":"45","stops":"0","airline":"Example"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "destinations.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            candidates = load_flight_candidates(path, 250)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["destination"], "Milan")
        self.assertEqual(candidates[0]["departure_date"], "2027-02-10")
        self.assertEqual(candidates[0]["return_date"], "2027-02-17")

    def test_prefers_whole_stay_total_after_tax(self):
        flight = {"origin":"MAN","destination":"Milan","country":"Italy",
                  "departure_date":"2027-01-10","return_date":"2027-01-17",
                  "flight_price_gbp":45,"stops":"0","airline":"Example"}
        payload = {"properties":[{"name":"Example Hotel", "type":"hotel", "overall_rating":4.2,
            "rate_per_night":{"extracted_display_price":80},
            "total_rate":{"extracted_display_price":560,
                          "extracted_after_taxes_fees":610}}]}
        row = normalise(payload, flight, 1)[0]
        self.assertEqual(row["total_price_gbp"],610)
        self.assertEqual(row["nights"],7)
        self.assertEqual(row["flight_departure_date"],"2027-01-10")
        self.assertEqual(row["accommodation_type"], "hotel")

    def test_hostels_are_separated_from_regular_hotels(self):
        flight = {"origin":"MAN","destination":"Dublin","country":"Ireland",
                  "departure_date":"2027-01-10","return_date":"2027-01-17",
                  "flight_price_gbp":45}
        payload = {"properties":[
            {"name":"Jacobs Inn Hostel", "type":"hotel", "overall_rating":4.3},
            {"name":"Clink i Lár", "type":"hotel", "overall_rating":4.0},
            {"name":"Example Hotel", "type":"hotel", "overall_rating":4.2},
            {"name":"City Studio Apartment", "type":"vacation rental"}
        ]}
        rows = normalise(payload, flight, 1)
        by_name = {r["property"]: r for r in rows}
        self.assertEqual(by_name["Jacobs Inn Hostel"]["accommodation_type"], "hostel")
        self.assertEqual(by_name["Clink i Lár"]["accommodation_type"], "hostel")
        self.assertEqual(by_name["Example Hotel"]["accommodation_type"], "hotel")
        self.assertEqual(by_name["City Studio Apartment"]["accommodation_type"], "vacation_rental")

    def test_hotel_only_normalisation_has_no_fabricated_flight(self):
        hotel_only = {"origin":"HOTEL_ONLY","destination":"Lisbon","country":"Portugal",
                      "departure_date":"2027-06-01","return_date":"2027-06-05",
                      "flight_price_gbp":None}
        payload = {"properties":[{"name":"Example Hotel",
            "total_rate":{"extracted_after_taxes_fees":320}}]}
        row = normalise(payload, hotel_only, 2)[0]
        self.assertEqual(row["origin"], "HOTEL_ONLY")
        self.assertIsNone(row["flight_price_gbp"])
        self.assertEqual(row["total_price_gbp"], 320)
        self.assertEqual(row["nights"], 4)

    def test_hotel_search_query_supports_continent_country_and_city(self):
        self.assertEqual(hotel_search_query({
            "destination": "Tokyo", "country": "Japan", "continent": "Asia"
        }), "Tokyo, Japan, Asia")
        self.assertEqual(hotel_search_query({
            "destination": "Europe", "country": "", "continent": "Europe"
        }), "Europe")

    def test_does_not_invent_total_from_nightly_price(self):
        flight = {"origin":"MAN","destination":"Milan","country":"Italy",
                  "departure_date":"2027-01-10","return_date":"2027-01-12",
                  "flight_price_gbp":45}
        payload = {"properties":[{"name":"Nightly only",
            "rate_per_night":{"extracted_display_price":80}}]}
        self.assertIsNone(normalise(payload, flight, 1)[0]["total_price_gbp"])


if __name__ == "__main__":
    unittest.main()
