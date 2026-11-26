"""Post-hoc link-loss analysis: reads the frozen core, never writes to it."""
import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from usv_sim import linkloss

CORE = Path(__file__).resolve().parents[1] / "results" / "core"


class LinkLossTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resamples, linkloss.BOOTSTRAP = linkloss.BOOTSTRAP, 20  # intervals are not under test
        cls.tables = linkloss.analyse(CORE, with_ideal=False)

    @classmethod
    def tearDownClass(cls):
        linkloss.BOOTSTRAP = cls.resamples

    def test_spearman_handles_ties_and_constants(self):
        self.assertAlmostEqual(linkloss.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(linkloss.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertAlmostEqual(linkloss.spearman([1, 2, 2, 3], [1, 2, 3, 4]), 0.9486832980505138)
        self.assertIsNone(linkloss.spearman([1, 1, 1], [1, 2, 3]))

    def test_outage_counts_match_frozen_diagnostics(self):
        with (CORE / "outage-diagnostics.csv").open(encoding="utf-8", newline="") as stream:
            frozen = {(r["slowdown"], r["fade_length"], r["policy"]): int(r["outage_events"]) for r in csv.DictReader(stream)}
        derived = {(str(r["slowdown"]), str(r["fade_length"]), r["policy"]): r["outages"] for r in self.tables["per-100-outages"]}
        self.assertEqual(derived, frozen)

    def test_one_row_per_frozen_run_and_exposure_is_policy_independent(self):
        rows = self.tables["per-run"]
        self.assertEqual(len(rows), 900)
        exposure = {}
        for r in rows:
            self.assertGreaterEqual(r["fade_failures"], 0)
            self.assertEqual(exposure.setdefault((r["seed"], r["fade_length"]), r["fade_exposure"]), r["fade_exposure"])

    def test_balanced_fixed_partition_exposure_equals_its_unavailability(self):
        # At a constant 200 m only fades break the S1 link, so the exogenous covariate is checkable.
        for r in self.tables["per-run"]:
            if r["policy"] == "S1" and not r["slowdown"]:
                self.assertAlmostEqual(r["fade_exposure"], 1 - r["link_availability"])

    def test_cli_refuses_core_and_leaves_it_untouched(self):
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in CORE.iterdir() if p.is_file()}
        with self.assertRaises(SystemExit):
            linkloss.main(["--output", str(CORE / "posthoc"), "--no-ideal", "--no-figures"])
        with tempfile.TemporaryDirectory() as folder:
            linkloss.main(["--output", folder, "--no-ideal", "--no-figures"])
            self.assertTrue((Path(folder) / "manifest.json").exists())
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in CORE.iterdir() if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
