"""Critical-window analysis: derived window, rule on frozen runs, theory, intervention."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from usv_sim import critical
from usv_sim.model import Config, make_scenario

CORE = Path(__file__).resolve().parents[1] / "results" / "core"
FREEZE = json.loads((CORE / "frozen-design.json").read_text(encoding="utf-8"))
C = Config(**FREEZE["config"])


class CriticalWindowTests(unittest.TestCase):
    def test_window_is_the_two_exchanges_before_the_first_split(self):
        for policy in critical.ONLINE:
            self.assertEqual(critical.critical_window(C, FREEZE["margins"], policy), ((24, 25), 26))
        self.assertAlmostEqual(critical.range_m(C), 316.227766, places=5)
        self.assertAlmostEqual(critical.fade_range_m(C), 100.0)

    def test_rule_explains_every_frozen_s3_run(self):
        runs = json.loads((CORE / "runs.json").read_text(encoding="utf-8"))
        rows = critical.rule_table(runs, C, (24, 25))
        s3 = next(r for r in critical.confusion(rows) if r["policy"] == "S3")
        self.assertEqual((s3["window_faded_and_stalled"], s3["window_clear_and_completed"]), (22, 158))
        self.assertEqual(s3["agreement"], 1.0)

    def test_theory_matches_the_stream_generator(self):
        self.assertAlmostEqual(critical.theory_probability(C, 5), 0.16)
        seeds = range(10**6, 10**6 + 2000)
        hits = sum(all(make_scenario(C, s, 5, False).fades[k] for k in (24, 25)) for s in seeds)
        self.assertLess(abs(hits / len(seeds) - 0.16), 0.03)

    def test_wilson_interval(self):
        low, high = critical.wilson(0, 30)
        self.assertEqual(low, 0.0)
        self.assertAlmostEqual(high, 0.1135, places=3)

    def test_intervention_flips_the_outcome(self):
        task = (FREEZE["config"], FREEZE["margins"], "S3", 1000, 5, False, (24, 25))
        out = critical._intervention(task)
        self.assertFalse(out["forced_fade_complete"])
        self.assertTrue(out["forced_clear_complete"])

    def test_cli_refuses_core_and_leaves_it_untouched(self):
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in CORE.iterdir() if p.is_file()}
        with self.assertRaises(SystemExit):
            critical.main(["--output", str(CORE / "x"), "--no-new-runs", "--no-figures"])
        with tempfile.TemporaryDirectory() as folder:
            critical.THEORY_SEEDS, saved = range(10**6, 10**6 + 50), critical.THEORY_SEEDS
            try:
                critical.main(["--output", folder, "--no-new-runs", "--no-figures"])
            finally:
                critical.THEORY_SEEDS = saved
            self.assertTrue((Path(folder) / "rule-confusion.csv").exists())
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in CORE.iterdir() if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
