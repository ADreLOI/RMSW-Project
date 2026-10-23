from dataclasses import replace
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from usv_sim.events import outage_events, warning_scores
from usv_sim.model import Boat, Config, Work, allocate, forecast, make_scenario, route, run, signal


class MotionTests(unittest.TestCase):
    def test_fixed_hand_computed_time_and_link_invariance(self):
        # Each boat visits 2 columns x 3 rows: 5 edges x 20/2 + two turns x 5.
        c=Config(width=4,height=3,timeout_s=200)
        s=make_scenario(c,7,2,False)
        a,_=run(c,s,"S1",forced_radio=lambda k:True)
        b,_=run(c,s,"S1",forced_radio=lambda k:False)
        for r in (a,b):
            self.assertEqual(r["completion_s"],60)
            self.assertEqual(r["redundant"],0)
            self.assertEqual(r["distance_m"],200)
            self.assertEqual(r["attempted_messages"],0)
        self.assertEqual(a["completion_s"],b["completion_s"])

    def test_one_boat_finite_speed_turn_and_no_tick_reobservation(self):
        c=Config(width=2,height=2)
        b=Boat(0,0,*c.centre(0),{0},queue=[1,3])
        visits=[]
        for _ in range(25): b.tick(c,2,lambda i,cell:visits.append(cell))
        self.assertEqual(visits,[1,3])
        self.assertEqual(b.distance,40)
        self.assertEqual(b.idle,0)

    def test_slowdown_moves_half_distance(self):
        c=Config(width=4,height=1)
        b=Boat(0,0,*c.centre(0),{0},queue=[3])
        for _ in range(10): b.tick(c,1,lambda *_:None)
        self.assertEqual(b.distance,10)

    def test_shortest_route_minimizes_turns(self):
        c=Config(width=3,height=3)
        self.assertEqual(route(c,0,8,2),[2,2,1,1])


class CoordinationTests(unittest.TestCase):
    def test_disconnected_queues_exhaust_without_stealing(self):
        c=Config(width=8,height=4,timeout_s=400)
        r,s=run(c,make_scenario(c,1,5,False),"S2",forced_radio=lambda k:False)
        self.assertFalse(r["complete"])
        self.assertEqual(r["restricted_s"],400)
        self.assertIsNone(r["completion_s"])
        self.assertEqual(r["conflicts"],0)
        self.assertEqual(r["delivered_messages"],0)
        self.assertGreater(sum(r["idle_s"]),0)

    def test_reconnection_resumes_coverage(self):
        c=Config(width=6,height=4,timeout_s=1500)
        r,_=run(c,make_scenario(c,1,5,False),"S2",forced_radio=lambda k:k<2 or k>12)
        self.assertTrue(r["complete"])
        self.assertGreater(r["delivered_messages"],0)
        self.assertGreater(sum(r["idle_s"]),0)

    def test_budget_failure_is_atomic(self):
        c=Config(width=6,height=3,timeout_s=200,max_bytes=1)
        r,s=run(c,make_scenario(c,1,5,False),"S4-T",forced_radio=lambda k:True)
        self.assertGreater(r["budget_failures"],0)
        self.assertFalse(any(row["committed"] for row in s))
        self.assertEqual(r["attempted_bytes"],0)

    def test_exact_serialized_bytes_and_log_reconstruction(self):
        c=Config(width=4,height=3,timeout_s=300)
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as d:
            path=Path(d)/"run.gz"
            r,_=run(c,make_scenario(c,2,2,False),"S4-T",log_path=path,forced_radio=lambda k:True)
            with gzip.open(path,"rt") as f: events=[json.loads(line) for line in f]
        sessions=[e for e in events if e["event"]=="session"]
        observations=[e for e in events if e["event"]=="observe"]
        self.assertEqual(len(observations)-len({e["cell"] for e in observations}),r["redundant"])
        self.assertEqual(sum(s["bytes_attempted"] for s in sessions),r["attempted_bytes"])
        for s in sessions:
            if s["attempted"]:
                self.assertEqual(sum(len(p.encode()) for p in s["payloads"]),s["bytes_attempted"])
                self.assertLessEqual(s["bytes_attempted"],8192)

    def test_allocation_tie_rule(self):
        c=Config(width=4,height=1)
        boats=[Boat(0,0,*c.centre(0),{0,3}),Boat(1,3,*c.centre(3),{0,3})]
        w=Work(); q=allocate(c,boats,{0,3},[2,2],1,w)
        self.assertEqual(q,[[1],[2]])
        self.assertEqual(w.arithmetic,22) # two divisions + 4*(2+2+1) eligible scores


class ForecastTests(unittest.TestCase):
    def test_fourth_projection_checks_third_onset(self):
        c=Config()
        rows=[]
        for t,x in enumerate((100,120,140,160,180)):
            r,d=signal(c,[[0,0],[x,0]],False)
            rows.append({"t":t*10,"u":[x,0],"r":r,"d":d})
        work=Work()
        positive,projected=forecast(c,rows,"trend",0,work)
        self.assertEqual(work.arithmetic,141)
        self.assertEqual(work.logarithms,9)
        self.assertEqual(work.square_roots,4)
        self.assertEqual(len(projected),4)
        self.assertFalse(positive)
        self.assertAlmostEqual(projected[-1],c.p0_dbm-20*__import__('math').log10(260))

    def test_persistence_and_warmup(self):
        c=Config(); row={"t":10,"r":-89,"d":200,"u":[200,0]}
        a=forecast(c,[row],"trend",2,Work())
        b=forecast(c,[row],"persistence",2,Work())
        self.assertEqual(a,b); self.assertTrue(a[0])
        self.assertEqual(forecast(c,[],"trend",2,Work())[0],False)

    def test_predictor_is_independent_of_future_and_inputs_unchanged(self):
        rows=[{"t":i*20,"r":-85+i,"d":100+i*2,"u":[100+i*2,0]} for i in range(5)]
        before=json.dumps(rows)
        a=forecast(Config(),rows,"trend",0,Work())
        make_scenario(Config(),99,10,True)
        b=forecast(Config(),rows,"trend",0,Work())
        self.assertEqual(a,b); self.assertEqual(json.dumps(rows),before)

    def test_disturbances_repeat_and_do_not_depend_on_slowdown(self):
        c=Config()
        a=make_scenario(c,5,10,False); b=make_scenario(c,5,10,True)
        self.assertEqual(a.fades,b.fades); self.assertEqual(a.onset_s,b.onset_s)

    def test_event_matching_and_boundaries(self):
        samples=[{"t":i*10,"radio":i not in (0,1,6,7,12,13),"warning":i in (4,5,10),"committed":True} for i in range(18)]
        r=warning_scores(samples)
        self.assertEqual(r["true_positives"],2)
        self.assertEqual(r["false_positives"],0)
        self.assertEqual(r["excluded_onsets"],1)
        self.assertEqual(r["lead_s"],[20,20])

    def test_undefined_warning_metrics(self):
        r=warning_scores([{"t":i,"radio":True} for i in range(10)])
        self.assertIsNone(r["precision"]); self.assertIsNone(r["recall"]); self.assertIsNone(r["f1"])


if __name__=="__main__": unittest.main()
