from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .events import outage_events, warning_scores
from .experiment import dump
from .model import Config, POLICIES, Work, forecast


def read_events(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for line in f: yield json.loads(line)


def reconstruct(path):
    """Independent totals from observation, movement, session and stop records."""
    covered=set(); known=None; observations=0; distance=0.0; previous=None
    totals={k:0 for k in ("attempted_messages","delivered_messages","attempted_bytes","delivered_bytes","budget_failures","reservations")}
    missing=[0.0,0.0]; ns=0; result=None; sessions=[]; idle=[0,0]
    local=None; first_complete=None; last_tick=0
    for e in read_events(path):
        kind=e["event"]
        if kind=="start":
            c=Config(**e["config"])
            previous=[list(c.centre(0)),list(c.centre((c.width+1)//2))]
            initial={0,(c.width+1)//2}; local=[set(initial),set(initial)]
        elif kind=="observe":
            covered.add(e["cell"]); observations+=1; local[e["boat"]].add(e["cell"])
            if len(covered)==c.cells and first_complete is None: first_complete=e["t"]
        elif kind=="tick":
            assert e["t"]==last_tick+1
            last_tick=e["t"]
            distance+=sum(math.hypot(now[0]-old[0],now[1]-old[1]) for now,old in zip(e["xy"],previous))
            previous=e["xy"]; idle=e["idle"]
        elif kind=="session":
            assert e["missing"]==[len(covered-k)/c.cells for k in local]
            if e["committed"]:
                merged=local[0]|local[1]; local=[set(merged),set(merged)]
            assert e["known"]==[sorted(k) for k in local]
            ns+=1; missing=[x+y for x,y in zip(missing,e["missing"])]
            known=e["known"]
            for field,key in (("attempted_messages","attempted"),("delivered_messages","delivered"),
                              ("attempted_bytes","bytes_attempted"),("delivered_bytes","bytes_delivered"),
                              ("budget_failures","budget_failure")):
                totals[field]+=e[key]
            totals["reservations"]+=int(e.get("extra_reserved",0)>0)
            if e["attempted"]:
                assert sum(len(s.encode("utf-8")) for s in e["payloads"])==e["bytes_attempted"]
            claims=[v for v in e["targets"] if v is not None]+[x for q in e["queues"] for x in q]
            assert len(claims)==len(set(claims))
            assert all(set(k)<=covered for k in known)
            assert e["bytes_attempted"]<=c.max_bytes and e["attempted"]<=c.max_datagrams
            sessions.append(e)
        elif kind=="stop": result=e["result"]; known=e["known"]
    if result is None: raise ValueError(f"Incomplete log: {path}")
    assert result["completion_s"]==first_complete
    assert result["stop_s"]==last_tick
    assert known==[sorted(k) for k in local]
    rebuilt={**totals,"observations":observations,"redundant":observations-len(covered),"distance_m":distance,
             "coverage":len(covered)/c.cells,"idle_s":idle,"complete":len(covered)==c.cells,
             "missing_mean":[x/ns if ns else None for x in missing],
             "missing_stop":[len(covered-set(k))/c.cells for k in known]}
    for key,value in rebuilt.items():
        if isinstance(value,float): assert math.isclose(value,result[key],rel_tol=1e-10,abs_tol=1e-8),(key,path,value,result[key])
        else: assert value==result[key],(key,path,value,result[key])
    if not result["complete"]: assert result["completion_s"] is None and result["restricted_s"]==c.timeout_s
    return result,sessions


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
    expected=len(freeze["evaluation_seeds"])*len(freeze["fade_lengths"])*len(freeze["slowdown"])*len(POLICIES)
    if len(rows)!=expected: raise ValueError("Incomplete evaluation matrix")
    keys=[(r["seed"],r["slowdown"],r["fade_length"],r["policy"]) for r in rows]
    if len(set(keys))!=len(keys): raise ValueError("Duplicate scenario-policy rows")
    hashes={}; replay_rows=[]; mechanisms=[]
    for i,r in enumerate(rows,1):
        path=root/"raw"/f"{r['seed']}-{int(r['slowdown'])}-{r['fade_length']}-{r['policy']}.jsonl.gz"
        rebuilt,samples=reconstruct(path)
        assert {k:v for k,v in r.items() if k not in ("warnings","wall_s")}==rebuilt
        scores=warning_scores(samples,freeze["config"]["horizon"])
        assert r["warnings"]==scores
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
                assert [r["seed"] for r in a]==[r["seed"] for r in b]
                delta=[x["restricted_s"]-y["restricted_s"] for x,y in zip(a,b)]
                mean,lo,hi=interval(delta,rng)
                reference=np.mean([r["restricted_s"] for r in b])
                contrasts.append({"slowdown":slowdown,"fade_length":length,"comparison":f"S4-T minus {comparator}",
                    "n_pairs":len(delta),"mean_difference_s":mean,"ci_low_s":lo,"ci_high_s":hi,"relative_percent":100*mean/reference,
                    "role":"primary" if comparator=="S2" else "secondary"})
    write_csv(root/"condition-summary.csv",summaries); write_csv(root/"paired-contrasts.csv",contrasts)
    write_csv(args.paper/"condition-summary.csv",summaries); write_csv(args.paper/"paired-contrasts.csv",contrasts)
    colors=["#475569","#ca5038","#b68b22","#007c83","#6b58a6"]
    plt.rcParams.update({"font.size":11,"axes.spines.top":False,"axes.spines.right":False,"svg.fonttype":"none"})
    fig,axs=plt.subplots(1,2,figsize=(6.3,3.3),sharey=True)
    for ax,slow in zip(axs,(False,True)):
        for p,color in zip(POLICIES,colors):
            g=[r for r in summaries if r["slowdown"]==slow and r["policy"]==p]
            ax.errorbar([r["fade_length"] for r in g],[r["restricted_mean_s"] for r in g],
                        yerr=[[r["restricted_mean_s"]-r["ci_low_s"] for r in g],[r["ci_high_s"]-r["restricted_mean_s"] for r in g]],label=p,color=color,marker="o",capsize=3)
        ax.set_title("Temporary slowdown" if slow else "Balanced progress"); ax.set_xticks([2,5,10]); ax.set_xlabel("Mean fade [exchanges]")
        ax.grid(alpha=.15); ax.set_ylim(0,7500)
    axs[0].set_ylabel("Restricted mean time [s]"); axs[1].legend(ncol=3,fontsize=11,loc="upper center",bbox_to_anchor=(.5,.84),columnspacing=.5,handlelength=1)
    fig.tight_layout(); fig.savefig(args.paper/"mission-time.png",dpi=200); fig.savefig(args.paper/"mission-time.pdf"); plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(6.3,3.3),sharey=True)
    for ax,slow in zip(axs,(False,True)):
        for p,color in zip(POLICIES,colors):
            g=[r for r in summaries if r["slowdown"]==slow and r["policy"]==p]
            ax.scatter([r["attempted_bytes"]/1000 for r in g],[r["restricted_mean_s"] for r in g],color=color,label=p,s=35)
        ax.set_title("Temporary slowdown" if slow else "Balanced progress"); ax.set_xlabel("Attempted data [kB]"); ax.grid(alpha=.15)
    axs[0].set_ylabel("Restricted mean time [s]"); axs[1].legend(ncol=2,fontsize=11,columnspacing=.5,handlelength=1); fig.tight_layout()
    fig.savefig(args.paper/"resource-tradeoff.png",dpi=200); fig.savefig(args.paper/"resource-tradeoff.pdf"); plt.close(fig)
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
