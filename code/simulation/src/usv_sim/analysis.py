from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from . import figures
from .events import outage_events, warning_scores
from .experiment import digest, dump
from .model import Config, POLICIES, Work, forecast
from .plotstyle import save


def read_events(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for line in f: yield json.loads(line)


def require(condition, message):
    """Evidence checks must also execute under python -O (unlike assert)."""
    if not condition:
        raise ValueError(message)


def validate_snapshot(event, config, positions, scenario=None, t=0):
    """Check additive schema-2 state against separately recorded geometry."""
    states = event.get("boats")
    if states is None:
        return  # Original retained logs predate exact task snapshots.
    require(len(states) == 2 and len(positions) == 2 and all(len(xy)==2 for xy in positions),
            "Task snapshot must contain two two-dimensional boat positions")
    claims = []
    for i, (state, xy) in enumerate(zip(states, positions)):
        require(state["id"] == i, "Task snapshot boat order mismatch")
        require(0 <= state["cell"] < config.cells, "Task snapshot cell outside grid")
        commanded=config.speed_mps
        if (t and scenario and scenario["slowdown"] and i==0
                and scenario["onset_s"] <= t < scenario["onset_s"]+config.slowdown_s):
            commanded*=config.slowdown_factor
        require(state["speed_mps"]==commanded, "Task snapshot commanded speed mismatch")
        mode=("ready" if state["target"] is None and state["queue"] else "idle" if state["target"] is None
              else "rendezvous" if state.get("transit")
              else "turning" if state["turn_remaining_s"]>0
              else "in_transit" if state["edge_target"] is not None else "ready")
        require(state["mode"]==mode, "Task snapshot movement phase mismatch")
        claims.extend(state["queue"])
        if state["target"] is not None and not state.get("transit"):
            claims.append(state["target"])
        require(0 <= state["turn_remaining_s"] <= config.turn_s,
                "Task snapshot turn remainder outside bounds")
        require(-1e-8 <= state["edge_remaining_m"] <= config.cell_m,
                "Task snapshot edge remainder outside bounds")
        origin = config.centre(state["cell"])
        edge = state["edge_target"]
        if edge is None:
            expected = origin
        else:
            require(0 <= edge < config.cells, "Task snapshot edge outside grid")
            target = config.centre(edge)
            require(math.isclose(abs(target[0]-origin[0])+abs(target[1]-origin[1]), config.cell_m),
                    "Task snapshot edge is not adjacent")
            fraction = 1-state["edge_remaining_m"]/config.cell_m
            expected = [a+(b-a)*fraction for a,b in zip(origin,target)]
        require(all(math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-8) for a,b in zip(expected,xy)),
                "Task snapshot disagrees with recorded position")
    require(all(0 <= task < config.cells for task in claims), "Claim outside grid")
    require(len(claims) == len(set(claims)), "Multiple owners in task snapshot")
    if "queues" in event:
        require(event["queues"] == [s["queue"] for s in states], "Snapshot queues disagree")
    if "targets" in event:
        require(event["targets"] == [s["target"] for s in states], "Snapshot targets disagree")


def reconstruct(path):
    """Independent totals from observation, movement, session and stop records."""
    covered=set(); known=None; observations=0; distance=0.0; previous=None
    totals={k:0 for k in ("attempted_messages","delivered_messages","attempted_bytes","delivered_bytes","budget_failures","reservations")}
    missing=[0.0,0.0]; ns=0; result=None; sessions=[]; idle=[0,0]
    local=None; first_complete=None; last_tick=0; started=False; stopped=False; schema=1
    allocated=False; pending_observations={}
    for e in read_events(path):
        kind=e["event"]
        require(not stopped, "Events after terminal state")
        if kind=="start":
            require(not started, "Multiple start events")
            started=True; schema=e.get("schema",1)
            require(schema in (1,2), "Unsupported event schema")
            c=Config(**e["config"])
            scenario=e["scenario"]
            previous=[list(c.centre(0)),list(c.centre((c.width+1)//2))]
            initial={0,(c.width+1)//2}; local=[set(initial),set(initial)]
        elif kind=="observe":
            require(started, "Observation before start")
            require(e["t"]==(last_tick+1 if allocated else 0), "Observation timestamp disagrees with tick order")
            require(0 <= e["cell"] < c.cells and e["boat"] in (0,1), "Invalid observation")
            pending_observations[e["boat"]]=e["cell"]
            covered.add(e["cell"]); observations+=1; local[e["boat"]].add(e["cell"])
            if len(covered)==c.cells and first_complete is None: first_complete=e["t"]
        elif kind=="initial_allocation":
            require(not allocated and last_tick==0, "Invalid initial allocation order")
            allocated=True; pending_observations={}
            if schema>=2: require("boats" in e, "Missing initial task snapshot")
            validate_snapshot(e,c,previous,scenario)
        elif kind=="tick":
            require(allocated, "Motion before initial allocation")
            require(e["t"]==last_tick+1, "Nonconsecutive motion timestamps")
            if schema>=2: require("boats" in e, "Missing one-second task snapshot")
            validate_snapshot(e,c,e["xy"],scenario,e["t"])
            if "boats" in e:
                require(all(e["boats"][i]["cell"]==cell for i,cell in pending_observations.items()),
                        "Observation cell disagrees with recorded arrival")
            pending_observations={}
            last_tick=e["t"]
            distance+=sum(math.hypot(now[0]-old[0],now[1]-old[1]) for now,old in zip(e["xy"],previous))
            previous=e["xy"]; idle=e["idle"]
        elif kind=="session":
            require(e["t"]==last_tick and e["t"]%c.exchange_s==0, "Invalid session timestamp")
            require(e["missing"]==[len(covered-k)/c.cells for k in local], "Pre-sync knowledge gap mismatch")
            if e["committed"]:
                merged=local[0]|local[1]; local=[set(merged),set(merged)]
            require(e["known"]==[sorted(k) for k in local], "Session local knowledge mismatch")
            ns+=1; missing=[x+y for x,y in zip(missing,e["missing"])]
            known=e["known"]
            for field,key in (("attempted_messages","attempted"),("delivered_messages","delivered"),
                              ("attempted_bytes","bytes_attempted"),("delivered_bytes","bytes_delivered"),
                              ("budget_failures","budget_failure")):
                totals[field]+=e[key]
            totals["reservations"]+=int(e.get("extra_reserved",0)>0)
            if e["attempted"]:
                require(sum(len(s.encode("utf-8")) for s in e["payloads"])==e["bytes_attempted"], "Serialized byte mismatch")
            transit=[bool(b.get("transit")) for b in e.get("boats") or ({},{})]
            claims=[v for v,moving in zip(e["targets"],transit) if v is not None and not moving]+[x for q in e["queues"] for x in q]
            require(len(claims)==len(set(claims)), "Multiple committed task owners")
            require(all(set(k)<=covered for k in known), "Invented local coverage")
            require(e["bytes_attempted"]<=c.max_bytes and e["attempted"]<=c.max_datagrams, "Message budget exceeded")
            if schema>=2: require("boats" in e, "Missing session task snapshot")
            validate_snapshot(e,c,previous,scenario,e["t"])
            sessions.append(e)
        elif kind=="stop":
            result=e["result"]; known=e["known"]; stopped=True
            if schema>=2: require("boats" in e and "queues" in e and "targets" in e, "Missing terminal task snapshot")
            validate_snapshot(e,c,previous,scenario,result["stop_s"])
        else:
            raise ValueError(f"Unknown event kind: {kind}")
    if result is None: raise ValueError(f"Incomplete log: {path}")
    require(result["completion_s"]==first_complete, "First full-coverage time mismatch")
    require(result["stop_s"]==last_tick, "Terminal time mismatch")
    require(known==[sorted(k) for k in local], "Terminal local knowledge mismatch")
    rebuilt={**totals,"observations":observations,"redundant":observations-len(covered),"distance_m":distance,
             "coverage":len(covered)/c.cells,"idle_s":idle,"complete":len(covered)==c.cells,
             "missing_mean":[x/ns if ns else None for x in missing],
             "missing_stop":[len(covered-set(k))/c.cells for k in known]}
    for key,value in rebuilt.items():
        matches = (math.isclose(value,result[key],rel_tol=1e-10,abs_tol=1e-8)
                   if isinstance(value,float) else value==result[key])
        require(matches, f"Reconstructed {key} mismatch: {path}: {value!r} != {result[key]!r}")
    if not result["complete"]:
        require(result["completion_s"] is None and result["restricted_s"]==c.timeout_s and result["stop_s"]==c.timeout_s,
                "Incomplete mission censoring mismatch")
    else:
        require(result["restricted_s"]==result["completion_s"], "Complete mission restricted time mismatch")
    return result,sessions


def validate_evaluation(freeze, rows):
    """Require the exact frozen scenario-policy matrix, not only its length."""
    require(digest({k:v for k,v in freeze.items() if k!="sha256"})==freeze.get("sha256"),
            "Frozen design hash mismatch")
    require(tuple(freeze["policies"])==POLICIES, "Analysis requires the five reviewed policies")
    expected={(seed,slowdown,length,policy) for seed in freeze["evaluation_seeds"]
              for slowdown in freeze["slowdown"] for length in freeze["fade_lengths"] for policy in freeze["policies"]}
    keys=[(r["seed"],r["slowdown"],r["fade_length"],r["policy"]) for r in rows]
    require(len(keys)==len(set(keys)), "Duplicate scenario-policy rows")
    require(set(keys)==expected, "Evaluation rows do not match the frozen matrix")


def interval(values,rng,repeats=2000):
    values=np.asarray(values,dtype=float)
    means=np.mean(values[rng.integers(0,len(values),size=(repeats,len(values)))],axis=1)
    lo,hi=np.quantile(means,[.025,.975])
    return float(np.mean(values)),float(lo),float(hi)


def write_csv(path,rows):
    if not rows: return
    with Path(path).open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def replay(c,reference,margins):
    rows=[]
    for method in ("trend","persistence"):
        history=[]; samples=[]
        for old in reference:
            s={key:old[key] for key in ("t","k","r","d","u","radio")}
            s["warning"]=False; s["committed"]=bool(s["radio"])
            if s["radio"]:
                history.append(s)
                s["warning"],_=forecast(c,history,method,margins[method],Work())
            samples.append(s)
        rows.append({"method":method,**warning_scores(samples,c.horizon)})
    return rows


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--input",type=Path,default=Path("results/core"))
    parser.add_argument("--paper",type=Path,default=Path("../../paper/Final_Report/generated"))
    args=parser.parse_args(); root=args.input; args.paper.mkdir(parents=True,exist_ok=True)
    freeze=json.loads((root/"frozen-design.json").read_text()); rows=json.loads((root/"runs.json").read_text())
    validate_evaluation(freeze,rows)
    hashes={}; replay_rows=[]; mechanisms=[]
    for i,r in enumerate(rows,1):
        path=root/"raw"/f"{r['seed']}-{int(r['slowdown'])}-{r['fade_length']}-{r['policy']}.jsonl.gz"
        rebuilt,samples=reconstruct(path)
        require({k:v for k,v in r.items() if k not in ("warnings","wall_s")}==rebuilt,
                f"Run table differs from verified raw log: {path}")
        scores=warning_scores(samples,freeze["config"]["horizon"])
        require(r["warnings"]==scores, f"Warning table differs from raw log: {path}")
        onsets=[start for start,end in outage_events(samples) if start>=freeze["config"]["horizon"]]
        reserved=[j for j,s in enumerate(samples) if s.get("committed") and s.get("extra_reserved",0)>0]
        useful=[j for j in reserved if any(1<=onset-j<=freeze["config"]["horizon"] for onset in onsets)]
        mechanisms.append({"seed":r["seed"],"slowdown":r["slowdown"],"fade_length":r["fade_length"],"policy":r["policy"],
            "committed_reservation_actions":len(reserved),"pre_outage_reservation_actions":len(useful),
            "outages_with_prior_reservation":sum(any(1<=onset-j<=freeze["config"]["horizon"] for j in reserved) for onset in onsets),
            "eligible_outages":len(onsets),"distance_failures":r["distance_failures"],"idle_s":sum(r["idle_s"]),"conflicts":r["conflicts"]})
        hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
        if r["policy"]=="S1":
            for score in replay(Config(**freeze["config"]),samples,freeze["margins"]):
                replay_rows.append({"seed":r["seed"],"slowdown":r["slowdown"],"fade_length":r["fade_length"],**score})
        if i%150==0: print(f"Reconstructed {i}/{len(rows)} raw logs",flush=True)
    dump(root/"raw-log-sha256.json",hashes)
    dump(root/"held-out-warning-replay.json",replay_rows)
    write_csv(root/"mechanism-diagnostics.csv",mechanisms)
    rng=np.random.default_rng(freeze["bootstrap_seed"]); summaries=[]; contrasts=[]
    for slowdown in (False,True):
        for length in (2,5,10):
            condition=[r for r in rows if r["slowdown"]==slowdown and r["fade_length"]==length]
            lookup={p:sorted([r for r in condition if r["policy"]==p],key=lambda r:r["seed"]) for p in POLICIES}
            for p,group in lookup.items():
                mean,lo,hi=interval([r["restricted_s"] for r in group],rng)
                summaries.append({"slowdown":slowdown,"fade_length":length,"policy":p,"n":len(group),"restricted_mean_s":mean,
                    "ci_low_s":lo,"ci_high_s":hi,"completion_proportion":sum(r["complete"] for r in group)/len(group),
                    **{key:float(np.mean([r[key] for r in group])) for key in ("coverage","redundant","distance_m","attempted_bytes","delivered_bytes","attempted_messages","reservations","link_availability","distance_failures","budget_failures")},
                    "idle_s":float(np.mean([sum(r["idle_s"]) for r in group])),
                    "missing_mean":float(np.mean([sum(r["missing_mean"])/2 for r in group])),
                    "arithmetic":float(np.mean([sum(w["arithmetic"] for w in r["work"].values()) for r in group])),
                    "coordination_cpu_s":float(np.mean([sum(w["cpu_ns"] for w in r["work"].values())/1e9 for r in group]))})
            for comparator in ("S2","S3","S4-P"):
                a,b=lookup["S4-T"],lookup[comparator]
                require([r["seed"] for r in a]==[r["seed"] for r in b], "Unpaired seed comparison")
                delta=[x["restricted_s"]-y["restricted_s"] for x,y in zip(a,b)]
                mean,lo,hi=interval(delta,rng)
                reference=np.mean([r["restricted_s"] for r in b])
                contrasts.append({"slowdown":slowdown,"fade_length":length,"comparison":f"S4-T minus {comparator}",
                    "n_pairs":len(delta),"mean_difference_s":mean,"ci_low_s":lo,"ci_high_s":hi,"relative_percent":100*mean/reference,
                    "role":"primary" if comparator=="S2" else "secondary"})
    write_csv(root/"condition-summary.csv",summaries); write_csv(root/"paired-contrasts.csv",contrasts)
    write_csv(args.paper/"condition-summary.csv",summaries); write_csv(args.paper/"paired-contrasts.csv",contrasts)
    save(figures.mission_time(summaries,POLICIES),args.paper,"mission-time")
    save(figures.resource_tradeoff(summaries,POLICIES),args.paper,"resource-tradeoff")
    pooled=[]
    for method in ("trend","persistence"):
        g=[r for r in replay_rows if r["method"]==method]
        counts={k:sum(r[k] for r in g) for k in ("true_positives","false_positives","false_negatives","eligible_outages","alerts","excluded_onsets","excluded_alerts")}
        tp,fp,fn=[counts[k] for k in ("true_positives","false_positives","false_negatives")]
        pooled.append({"method":method,**counts,"precision":tp/(tp+fp) if tp+fp else None,"recall":tp/(tp+fn) if tp+fn else None,
                       "f1":2*tp/(2*tp+fp+fn) if counts["eligible_outages"] else None,"lead_s":[x for r in g for x in r["lead_s"]]})
    dump(root/"warning-summary.json",pooled)
    resources=[]
    for p in POLICIES:
        group=[r for r in rows if r["policy"]==p]
        for component in ("forecast","allocation","resync"):
            works=[r["work"][component] for r in group]
            decisions=sum(w["decisions"] for w in works)
            resources.append({"policy":p,"component":component,"runs":len(group),
                "mean_arithmetic":float(np.mean([w["arithmetic"] for w in works])),
                "mean_gop":float(np.mean([w["arithmetic"] for w in works]))/1e9,
                "arithmetic_per_decision":sum(w["arithmetic"] for w in works)/decisions if decisions else None,
                "mean_logical_tests":float(np.mean([w["comparisons"] for w in works])),
                "mean_logarithms":float(np.mean([w["logarithms"] for w in works])),
                "mean_square_roots":float(np.mean([w["square_roots"] for w in works])),
                "cpu_seconds_per_decision":sum(w["cpu_ns"] for w in works)/1e9/decisions if decisions else None})
    write_csv(root/"component-resources.csv",resources)
    diagnostics=[]
    for slow in (False,True):
        for length in (2,5,10):
            for p in POLICIES:
                group=[r for r in rows if r["slowdown"]==slow and r["fade_length"]==length and r["policy"]==p]
                durations=[n*freeze["config"]["exchange_s"] for r in group for n in r["warnings"]["outage_lengths"]]
                diagnostics.append({"slowdown":slow,"fade_length":length,"policy":p,
                    "outage_events":len(durations),"mean_outage_s":float(np.mean(durations)) if durations else None,
                    "mean_outages_per_active_hour":float(np.mean([len(r["warnings"]["outage_lengths"])*3600/r["stop_s"] for r in group])),
                    "boundary_episodes_may_be_truncated":True})
    write_csv(root/"outage-diagnostics.csv",diagnostics)
    with (args.paper/"resource-table.tex").open("w",encoding="utf-8") as f:
        f.write("\\begin{tabular}{lrrrr}\\toprule\nPolicy & Attempted kB & Arithmetic ops & GOP & Mean gap [\\%]\\\\\\midrule\n")
        for p in POLICIES:
            group=[r for r in rows if r["policy"]==p]
            byte_mean=np.mean([r["attempted_bytes"] for r in group])/1000
            ops=np.mean([sum(w["arithmetic"] for w in r["work"].values()) for r in group])
            gap=np.mean([sum(r["missing_mean"])/2 for r in group])*100
            f.write(f"{p} & {byte_mean:.1f} & {ops:.0f} & {ops/1e9:.6f} & {gap:.2f}\\\\\n")
        f.write("\\bottomrule\\end{tabular}\n")
    with (args.paper/"mission-table.tex").open("w",encoding="utf-8") as f:
        f.write("\\begin{tabular}{llrrrrr}\\toprule\nProgress & $L$ & S1 & S2 & S3 & S4-T & S4-P\\\\\\midrule\n")
        for slow in (False,True):
            for length in (2,5,10):
                g=[next(r for r in summaries if r["slowdown"]==slow and r["fade_length"]==length and r["policy"]==p) for p in POLICIES]
                f.write(("Unequal" if slow else "Balanced")+f" & {length} & "+" & ".join(f"{r['restricted_mean_s']:.0f}" for r in g)+"\\\\\n")
        f.write("\\bottomrule\\end{tabular}\n")
    dump(root/"verification.json",{"raw_runs_reconstructed":len(rows),"all_metrics_match":True,"paired_matrix_complete":True,"raw_sha256_count":len(hashes)})
    dump(root/"analysis-manifest.json",{"design_sha256":freeze["sha256"],"resamples":2000,
         "analysis_source_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob("*.py")},
         "note":"Hashes establish integrity of retained artifacts. CPU timings and gzip headers may differ on regeneration; scientific deterministic metrics should agree."})
    print(json.dumps({"reconstructed":len(rows),"summary":summaries,"contrasts":contrasts,"warning_replay":pooled},indent=2))


if __name__=="__main__": main()
