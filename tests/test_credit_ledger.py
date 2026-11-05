import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import credit_ledger

class CreditLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "monthly.json"
        self.patcher = patch.object(credit_ledger, "PATH", self.path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def test_blocks_until_month_is_reconciled(self):
        with self.assertRaises(SystemExit):
            credit_ledger.main_with_args(["reserve", "--category", "flight"])

    def test_reserves_and_enforces_category_cap(self):
        data = {"schema_version":1,"reconciled":True,"months":{
            credit_ledger.month_key():{"baseline_used":0,"reserved":{"flight":119,"personal":0,"hotel":0}}}}
        credit_ledger.save(data)
        with self.assertRaises(SystemExit):
            credit_ledger.reserve("flight", 2)
        credit_ledger.reserve("flight", 1)
        saved = credit_ledger.load()
        self.assertEqual(saved["months"][credit_ledger.month_key()]["reserved"]["flight"],120)

    def test_enforces_global_cap_including_opening_baseline(self):
        data = {"schema_version":1,"reconciled":True,"months":{
            credit_ledger.month_key():{"baseline_used":249,"reserved":{"flight":0,"personal":0,"hotel":0}}}}
        credit_ledger.save(data)
        with self.assertRaises(SystemExit):
            credit_ledger.reserve("hotel", 2)

if __name__ == "__main__":
    unittest.main()
