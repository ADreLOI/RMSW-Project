import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from usv_sim import hardware, predictors
from usv_sim.analysis import reconstruct
from usv_sim.mapping import Survey, SurveyModel, evaluate_log, tvu
from usv_sim.model import Config, Work, make_scenario, rendezvous_cells, run

CORE = Path(__file__).resolve().parents[1]/"results/core"
MARGINS = {"trend": 4, "persistence": 4}


class RecoveryTests(unittest.TestCase):
    def test_hooks_off_reproduce_frozen_runs(self):
        c = Config()
        rows = {(r["seed"], r["slowdown"], r["fade_length"], r["policy"]): r
                for r in json.loads((CORE/"runs.json").read_text())}
        for key in ((1000, False, 5, "S2"), (1007, True, 10, "S4-T")):
            result, _ = run(c, make_scenario(c, key[0], key[2], key[1]), key[3], MARGINS)
            frozen = rows[key]
            for field in ("restricted_s", "coverage", "redundant", "attempted_bytes", "observations", "distance_m"):
                self.assertEqual(result[field], frozen[field], field)
            self.assertNotIn("recovery_trips", result)

    def test_recovery_removes_reactive_stall_and_logs_reconstruct(self):
        c = Config(); scenario = make_scenario(c, 1000, 5, True)
        stalled, _ = run(c, scenario, "S2", MARGINS)
        self.assertFalse(stalled["complete"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"rv.jsonl.gz"
            recovered, _ = run(c, scenario, "S2", MARGINS, path, recovery=True)
            rebuilt, _ = reconstruct(path)
        self.assertTrue(recovered["complete"])
        self.assertGreater(recovered["recovery_trips"], 0)
        self.assertEqual(rebuilt, recovered)

    def test_fixed_partition_ignores_recovery(self):
        c = Config(); scenario = make_scenario(c, 1001, 2, True)
        base, _ = run(c, scenario, "S1"); recovered, _ = run(c, scenario, "S1", recovery=True)
        self.assertEqual(base["restricted_s"], recovered["restricted_s"])
        self.assertEqual(recovered["recovery_trips"], 0)

    def test_meeting_cells_are_adjacent_centre_cells(self):
        c = Config(); a, b = rendezvous_cells(c)
        self.assertEqual(b-a, 1)
        self.assertEqual(c.xy(a), (c.width//2-1, c.height//2))


def trace(seed=3, length=5, slowdown=True):
    c = Config(); scenario = make_scenario(c, seed, length, slowdown)
    _, samples = run(c, scenario, "S1")
    return c, samples, scenario.fades


SPECS = [
    {"kind": "ewma", "alpha": .3, "margin": 4},
    {"kind": "kalman", "q": 1e-3, "r": 1.0, "margin": 4},
    {"kind": "gilbert", "p_cf": .06, "p_fc": .29, "fade_db": -10.0, "tau": .1, "margin": 0},
]


class PredictorTests(unittest.TestCase):
    def test_predictors_are_causal_and_do_not_mutate_history(self):
        c, samples, fades = trace()
        history = [s for s in samples if s["radio"]][:20]
        for spec in SPECS:
            full = predictors.make(spec); prefix = predictors.make(spec)
            before = copy.deepcopy(history)
            outputs = [full(c, history[:n], Work()) for n in range(1, len(history)+1)]
            self.assertEqual(history, before, spec["kind"])
            # A fresh instance given only a prefix must agree with the incremental one.
            self.assertEqual(prefix(c, history[:12], Work()), outputs[11], spec["kind"])

    def test_kalman_tracks_a_constant_residual(self):
        c, samples, _ = trace()
        history = [s for s in samples if s["radio"]][:15]
        model = predictors.make(SPECS[1]); model(c, history, Work())
        self.assertAlmostEqual(model.x[0], 0.0, places=6)
        self.assertAlmostEqual(model.x[1], 0.0, places=6)

    def test_gilbert_without_fades_reduces_to_clear_projection_rule(self):
        c, samples, _ = trace()
        history = [s for s in samples if s["radio"]]
        spec = {**SPECS[2], "p_cf": 0.0, "p_fc": 1.0}
        for n in range(2, len(history), 7):
            warning, clear = predictors.make(spec)(c, history[:n], Work())
            self.assertEqual(warning, predictors.rule(c, clear, c.threshold_dbm, Work()))

    def test_learned_models_fit_and_count_work(self):
        c, samples, fades = trace()
        x, y = predictors.training_rows(c, [{"samples": samples}])
        self.assertEqual(x.shape[1], len(predictors.FEATURES))
        model = predictors.make({"kind": "logistic", **predictors.fit_logistic(x, y, steps=200), "tau": .5})
        work = Work(); model(c, [s for s in samples if s["radio"]][:6], work)
        self.assertGreater(work.arithmetic, 0); self.assertEqual(work.decisions, 1)
        self.assertGreater(model.memory_bytes(), 0)

    def test_fade_oracle_is_flagged_non_deployable(self):
        self.assertFalse(predictors.FadeOracle([False], 0).deployable)


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.c = Config(); self.survey = Survey(self.c)

    def test_tvu_matches_s44_order_1a_form(self):
        self.assertAlmostEqual(float(tvu(np.array(20.0))), (0.5**2+(0.013*20)**2)**.5)

    def test_full_noisy_coverage_is_near_tvu_and_empty_map_is_undefined(self):
        counts = np.zeros(self.c.cells, dtype=int); sums = np.zeros_like(self.survey.truth)
        self.assertIsNone(self.survey.metrics(sums, counts)["rmse_m"])
        rng = np.random.default_rng(1)
        for cell in range(self.c.cells):
            sums[cell] += self.survey.sounding(cell, rng); counts[cell] += 1
        m = self.survey.metrics(sums, counts)
        self.assertEqual(m["coverage"], 1.0)
        self.assertLess(m["rmse_m"], float(self.survey.limit.max()))
        self.assertGreater(m["s44_compliant_fraction"], .8)

    def test_map_replay_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"s1.jsonl.gz"
            run(self.c, make_scenario(self.c, 1000, 5, False), "S1", log_path=path)
            a = evaluate_log(path, self.survey, "k"); b = evaluate_log(path, self.survey, "k")
        self.assertEqual(a, b)
        self.assertEqual(a["final"]["coverage"], 1.0)
        self.assertEqual(len(a["curve"]), self.c.timeout_s//SurveyModel().checkpoint_s)


class HardwareTests(unittest.TestCase):
    def test_projection_scales_with_work_and_clock(self):
        small = {"arithmetic": 100, "transcendental": 5, "comparisons": 10}
        large = {k: 10*v for k, v in small.items()}
        for profile in hardware.PROFILES:
            a = hardware.project(small, 1000, 10, profile); b = hardware.project(large, 1000, 10, profile)
            self.assertAlmostEqual(b["latency_us_high"], 10*a["latency_us_high"])
            self.assertLessEqual(a["latency_us_low"], a["latency_us_high"])
        m4, m7 = (hardware.project(small, 1000, 10, p) for p in hardware.PROFILES[:2])
        self.assertGreater(m4["latency_us_high"], m7["latency_us_high"])


if __name__ == "__main__":
    unittest.main()
