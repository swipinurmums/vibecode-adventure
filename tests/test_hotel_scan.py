import unittest
from hotel_scan import normalise, days
class Tests(unittest.TestCase):
 def test_date(self):
  self.assertEqual(days("2027-01-10","2027-01-17"),7)
  with self.assertRaises(ValueError): days("2027-01-17","2027-01-17")
 def test_after_tax_total(self):
  p={"properties":[{"name":"Test","rate_per_night":{"extracted_display_price":80},"total_rate":{"extracted_display_price":560,"extracted_after_taxes_fees":610}}]}
  r=normalise(p,"City","Country","2027-01-10","2027-01-17",1)[0]
  self.assertEqual(r["total_price_gbp"],610)
  self.assertEqual(r["nightly_price_gbp"],80)
 def test_no_invented_total(self):
  p={"properties":[{"name":"Test","rate_per_night":{"extracted_display_price":80}}]}
  r=normalise(p,"City","Country","2027-01-10","2027-01-12",1)[0]
  self.assertIsNone(r["total_price_gbp"])
if __name__=="__main__": unittest.main()
