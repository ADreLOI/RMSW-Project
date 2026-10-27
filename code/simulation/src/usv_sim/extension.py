"""Extension study E1-E3, kept separate from the frozen 900-run core evidence.

E1 recovery: every online policy may send idle, disconnected boats to pre-agreed
   meeting cells, so the reactive control no longer stalls by construction.
E2 predictors: five further warning models (EWMA, Kalman, Gilbert burst HMM,
   logistic regression, small MLP) and a non-deployable fade oracle share the S4
   reservation action, with algorithmic work, memory and hardware projections.
E3 map accuracy: post-hoc synthetic bathymetry error from observation events.

Stages: tune (pilot seeds 0-9 only, then freeze), evaluate (fresh seeds 2000-2029),
analyze (log reconstruction, replay, bootstrap, mapping, tables, figures).
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import multiprocessing
from pathlib import Path
import time

import numpy as np

from . import figures as fig
from . import hardware, predictors
from .analysis import interval, reconstruct, require, write_csv
from .events import warning_scores
from .experiment import digest, dump, environment
from .mapping import Survey, SurveyModel, evaluate_log
from .model import Config, POLICIES, Work, geometry, make_scenario, run
from .plotstyle import save

ROOT=Path(__file__).resolve().parents[2]
CORE=ROOT/"results/core"
EXTRA={"S4-E":"ewma","S4-K":"kalman","S4-G":"gilbert","S4-L":"logistic","S4-M":"mlp","S4-O":"fade-oracle"}
ALL_POLICIES=(*POLICIES,*EXTRA)
LABELS={"trend":"Trend (frozen)","persistence":"Persistence (frozen)","ewma":"EWMA residual","kalman":"Kalman level/slope",
        "gilbert":"Gilbert burst HMM","logistic":"Logistic regression","mlp":"MLP (16 tanh)","fade-oracle":"Fade oracle (bound)"}
CONDITIONS=[(slowdown,length) for slowdown in (False,True) for length in (2,5,10)]


def traces(c: Config, seeds):
    """Fixed-route S1 radio samples with their pre-generated fades (no logging)."""
    out=[]
    for seed in seeds:
        for slowdown,length in CONDITIONS:
            scenario=make_scenario(c,seed,length,slowdown)
            _,samples=run(c,scenario,"S1")
            out.append({"seed":seed,"slowdown":slowdown,"length":length,"samples":samples,"fades":scenario.fades})
    return out


def replay(c: Config, spec, trace, work=None):
    model=predictors.make(spec,trace["fades"]); work=work or Work()
    history=[]; evaluated=[]
    for s in trace["samples"]:
        item={key:s[key] for key in ("t","k","r","d","u","radio")}
        item["warning"]=False; item["committed"]=bool(s["radio"])
        if s["radio"]:
            history.append(item)
            item["warning"],_=model(c,history,work)
        evaluated.append(item)
    return evaluated,model


def pooled(c: Config, spec, group):
    counts={k:0 for k in ("true_positives","false_positives","false_negatives","eligible_outages","alerts")}
    leads=[]; work=Work(); model=None
    for trace in group:
        evaluated,model=replay(c,spec,trace,work)
        scores=warning_scores(evaluated,c.horizon)
        for k in counts: counts[k]+=scores[k]
        leads+=scores["lead_s"]
    tp,fp,fn=(counts[k] for k in ("true_positives","false_positives","false_negatives"))
    return {**counts,"precision":tp/(tp+fp) if tp+fp else None,"recall":tp/(tp+fn) if tp+fn else None,
            "f1":2*tp/(2*tp+fp+fn) if counts["eligible_outages"] else None,"mean_lead_s":float(np.mean(leads)) if leads else None,
            "work":asdict(work),"memory_bytes":model.memory_bytes() if model else None}


def select(c, candidates, group):
    """Highest pilot F1; ties keep the earlier (simpler / smaller-margin) candidate."""
    rows=[{"spec":spec,**pooled(c,spec,group)} for spec in candidates]
    best=max(rows,key=lambda r:(r["f1"] or 0,-rows.index(r)))
    return best["spec"],[{"spec":r["spec"],"f1":r["f1"],"precision":r["precision"],"recall":r["recall"]} for r in rows]


def tune(c: Config, out: Path):
    pilot=traces(c,range(10))
    fit=[t for t in pilot if t["seed"]<7]; hold=[t for t in pilot if t["seed"]>=7]
    frozen=json.loads((CORE/"frozen-design.json").read_text())["margins"]
    specs={"trend":{"kind":"trend","margin":frozen["trend"]},"persistence":{"kind":"persistence","margin":frozen["persistence"]}}
    log={}
    margins=(0,2,4)
    specs["ewma"],log["ewma"]=select(c,[{"kind":"ewma","alpha":a,"margin":m} for a in (.3,.6) for m in margins],pilot)
    specs["kalman"],log["kalman"]=select(c,[{"kind":"kalman","q":q,"r":r,"margin":m} for q in (1e-3,1e-2) for r in (1.0,25.0) for m in margins],pilot)
    g=predictors.fit_gilbert(c,pilot); counts=g.pop("transition_counts")
    specs["gilbert"],log["gilbert"]=select(c,[{"kind":"gilbert",**g,"tau":tau,"margin":m} for tau in (.1,.2,.3,.5) for m in (0,2)],pilot)
    log["gilbert_transition_counts"]=counts
    x,y=predictors.training_rows(c,fit)
    taus=[round(.1*i,1) for i in range(1,10)]
    lr=predictors.fit_logistic(x,y)
    specs["logistic"],log["logistic"]=select(c,[{"kind":"logistic",**lr,"tau":t} for t in taus],hold)
    mlp=predictors.fit_mlp(x,y)
    specs["mlp"],log["mlp"]=select(c,[{"kind":"mlp",**mlp,"tau":t} for t in taus],hold)
    specs["fade-oracle"],log["fade-oracle"]=select(c,[{"kind":"fade-oracle","margin":m} for m in margins],pilot)
    for name,spec in specs.items(): spec["label"]=LABELS[name]
    design={"schema":1,"study":"extension E1-E3 (post-core, separately frozen)","config":asdict(c),
            "core_design_sha256":json.loads((CORE/"frozen-design.json").read_text())["sha256"],
            "pilot_seeds":list(range(10)),"learned_fit_seeds":list(range(7)),"learned_threshold_seeds":[7,8,9],
            "evaluation_seeds":list(range(2000,2030)),"fade_lengths":[2,5,10],"slowdown":[False,True],
            "policies":list(ALL_POLICIES),"policy_predictors":{**{"S4-T":"trend","S4-P":"persistence"},**EXTRA},
            "recovery":True,"recovery_rule":"idle, empty-queue online boat with no committed exchange for >= one exchange interval "
            "travels to a pre-agreed centre cell; travel is not a claim; on any successful exchange it stops after the current edge",
            "predictors":specs,"tuning":log,"training_rows":int(len(y)),"positive_rate":float(y.mean()),
            "bootstrap_resamples":2000,"bootstrap_seed":20261027,
            "primary":"S4-T minus S2 (with recovery)","secondary":["S4-T minus S3","S4-T minus S4-P","S4-X minus S3 for each extra predictor"],
            "map_model":asdict(SurveyModel()),"frozen_before_evaluation":True}
    design["sha256"]=digest(design)
    dump(out/"extension-design.json",design)
    print(json.dumps({"design_sha256":design["sha256"],"selected":{k:{q:v for q,v in s.items() if q in ("margin","alpha","q","r","tau")} for k,s in specs.items()}},indent=1))
    return design


def load(out: Path):
    design=json.loads((out/"extension-design.json").read_text())
    require(digest({k:v for k,v in design.items() if k!="sha256"})==design["sha256"],"Extension design hash mismatch")
    return design


def worker(task):
    cdata,seed,length,slowdown,policy,spec,margins,path=task
    c=Config(**cdata); scenario=make_scenario(c,seed,length,slowdown)
    model=predictors.make(spec,scenario.fades) if spec and spec["kind"] not in ("trend","persistence") else None
    start=time.perf_counter()
    result,samples=run(c,scenario,policy,margins,path,predictor=model,recovery=True)
    result["warnings"]=warning_scores(samples,c.horizon); result["wall_s"]=time.perf_counter()-start
    return result


def evaluate(out: Path, workers: int):
    design=load(out); c=Config(**design["config"])
    margins={"trend":design["predictors"]["trend"]["margin"],"persistence":design["predictors"]["persistence"]["margin"]}
    tasks=[]
    for seed in design["evaluation_seeds"]:
        for slowdown in design["slowdown"]:
            for length in design["fade_lengths"]:
                for policy in design["policies"]:
                    name=design["policy_predictors"].get(policy)
                    spec=design["predictors"][name] if name else None
                    tasks.append((asdict(c),seed,length,slowdown,policy,spec,margins,out/"raw"/f"{seed}-{int(slowdown)}-{length}-{policy}.jsonl.gz"))
    start=time.perf_counter(); rows=[]
    with multiprocessing.Pool(workers) as pool:
        for i,row in enumerate(pool.imap_unordered(worker,tasks,chunksize=5),1):
            rows.append(row)
            if i%200==0: print(f"{i}/{len(tasks)} runs, {time.perf_counter()-start:.1f}s",flush=True)
    rows.sort(key=lambda r:(r["seed"],r["slowdown"],r["fade_length"],ALL_POLICIES.index(r["policy"])))
    dump(out/"runs.json",rows)
    dump(out/"evaluation-manifest.json",{"runs":len(rows),"design_sha256":design["sha256"],"elapsed_s":time.perf_counter()-start,
         "source_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob("*.py")}})


def per_decision(w):
    d=max(1,w["decisions"])
    return {"arithmetic":w["arithmetic"]/d,"transcendental":(w["logarithms"]+w["square_roots"])/d,"comparisons":w["comparisons"]/d,
            "cpu_us":w["cpu_ns"]/d/1e3}


def map_rows(c, root, rows, study):
    survey=Survey(c); out=[]
    for r in rows:
        key=f"{r['seed']}-{int(r['slowdown'])}-{r['fade_length']}-{r['policy']}"
        m=evaluate_log(root/"raw"/f"{key}.jsonl.gz",survey,key)
        curve={p["t"]:p for p in m["curve"]}
        reach=next((p["t"] for p in m["curve"] if p["rmse_m"] is not None and p["rmse_m"]<=0.5),None)
        out.append({"study":study,"seed":r["seed"],"slowdown":r["slowdown"],"fade_length":r["fade_length"],"policy":r["policy"],
                    "complete":r["complete"],"final_rmse_m":m["final"]["rmse_m"],"final_s44_fraction":m["final"]["s44_compliant_fraction"],
                    "rmse_900_m":curve[900]["rmse_m"],"rmse_1800_m":curve[1800]["rmse_m"],
                    "redundant_cells":m["final"]["redundant_cells"],"time_to_rmse_0_5_s":reach,
                    "curve":[[p["t"],p["rmse_m"]] for p in m["curve"]]})
    return out


def analyze(out: Path, paper: Path):
    design=load(out); c=Config(**design["config"]); paper.mkdir(parents=True,exist_ok=True)
    rows=json.loads((out/"runs.json").read_text())
    expected={(s,sl,l,p) for s in design["evaluation_seeds"] for sl in design["slowdown"] for l in design["fade_lengths"] for p in design["policies"]}
    require({(r["seed"],r["slowdown"],r["fade_length"],r["policy"]) for r in rows}==expected and len(rows)==len(expected),"Extension matrix incomplete")
    for i,r in enumerate(rows,1):
        path=out/"raw"/f"{r['seed']}-{int(r['slowdown'])}-{r['fade_length']}-{r['policy']}.jsonl.gz"
        rebuilt,samples=reconstruct(path)
        require({k:v for k,v in r.items() if k not in ("warnings","wall_s")}==rebuilt,f"Run differs from raw log: {path}")
        require(r["warnings"]==warning_scores(samples,c.horizon),f"Warning mismatch: {path}")
        if i%400==0: print(f"Reconstructed {i}/{len(rows)}",flush=True)
    rng=np.random.default_rng(design["bootstrap_seed"]); summary=[]; contrasts=[]
    for slowdown,length in CONDITIONS:
        group={p:sorted([r for r in rows if r["slowdown"]==slowdown and r["fade_length"]==length and r["policy"]==p],key=lambda r:r["seed"]) for p in ALL_POLICIES}
        for p,g in group.items():
            mean,lo,hi=interval([r["restricted_s"] for r in g],rng)
            summary.append({"slowdown":slowdown,"fade_length":length,"policy":p,"n":len(g),"restricted_mean_s":mean,"ci_low_s":lo,"ci_high_s":hi,
                "completion_proportion":sum(r["complete"] for r in g)/len(g),
                **{k:float(np.mean([r[k] for r in g])) for k in ("coverage","redundant","distance_m","attempted_bytes","reservations","link_availability")},
                "recovery_trips":float(np.mean([r.get("recovery_trips",0) for r in g])),
                "idle_s":float(np.mean([sum(r["idle_s"]) for r in g])),
                "forecast_arithmetic":float(np.mean([r["work"]["forecast"]["arithmetic"] for r in g])),
                "coordination_arithmetic":float(np.mean([sum(w["arithmetic"] for w in r["work"].values()) for r in g]))})
        pairs=[("S4-T","S2","primary"),("S4-T","S3","secondary"),("S4-T","S4-P","secondary"),("S2","S1","context"),("S3","S1","context")]
        pairs+=[(p,"S3","predictor") for p in EXTRA]+[(p,"S2","predictor") for p in EXTRA]
        for a,b,role in pairs:
            require([r["seed"] for r in group[a]]==[r["seed"] for r in group[b]],"Unpaired comparison")
            delta=[x["restricted_s"]-y["restricted_s"] for x,y in zip(group[a],group[b])]
            mean,lo,hi=interval(delta,rng)
            contrasts.append({"slowdown":slowdown,"fade_length":length,"comparison":f"{a} minus {b}","role":role,"n_pairs":len(delta),
                "mean_difference_s":mean,"ci_low_s":lo,"ci_high_s":hi,"relative_percent":100*mean/np.mean([r["restricted_s"] for r in group[b]])})
    write_csv(out/"condition-summary.csv",summary); write_csv(out/"paired-contrasts.csv",contrasts)
    # E2 warning quality on held-out fixed routes, with work, memory and hardware projections.
    held={"core-1000":traces(c,range(1000,1030)),"extension-2000":traces(c,design["evaluation_seeds"])}
    warning=[]; projection=[]
    for name,spec in design["predictors"].items():
        for split,group in held.items():
            score=pooled(c,spec,group); pd=per_decision(score["work"])
            warning.append({"predictor":name,"label":spec["label"],"split":split,
                **{k:score[k] for k in ("eligible_outages","alerts","true_positives","false_positives","false_negatives","precision","recall","f1","mean_lead_s","memory_bytes")},
                **{f"{k}_per_decision":v for k,v in pd.items()}})
            if split=="extension-2000":
                for profile in hardware.PROFILES:
                    projection.append({"predictor":name,**hardware.project(pd,score["memory_bytes"],c.exchange_s,profile)})
    write_csv(out/"predictor-warning-quality.csv",warning); write_csv(out/"hardware-projection.csv",projection)
    # E3 map accuracy for the frozen core logs (post hoc) and the extension logs.
    core_rows=json.loads((CORE/"runs.json").read_text())
    maps=map_rows(c,CORE,core_rows,"core")+map_rows(c,out,rows,"extension")
    dump(out/"map-accuracy-runs.json",maps)
    map_summary=[]
    for study,policies in (("core",POLICIES),("extension",ALL_POLICIES)):
        for p in policies:
            g=[m for m in maps if m["study"]==study and m["policy"]==p]
            reach=[m["time_to_rmse_0_5_s"] for m in g]
            map_summary.append({"study":study,"policy":p,"runs":len(g),"final_rmse_m":float(np.mean([m["final_rmse_m"] for m in g])),
                "final_s44_fraction":float(np.mean([m["final_s44_fraction"] for m in g])),"rmse_900_m":float(np.mean([m["rmse_900_m"] for m in g])),
                "rmse_1800_m":float(np.mean([m["rmse_1800_m"] for m in g])),"reached_0_5_m":sum(x is not None for x in reach),
                "median_time_to_0_5_m_s":float(np.median([x for x in reach if x is not None])) if any(x is not None for x in reach) else None,
                "redundant_cells":float(np.mean([m["redundant_cells"] for m in g]))})
    write_csv(out/"map-accuracy-summary.csv",map_summary)
    figures(out,paper,design,summary,warning,maps)
    tables(paper,design,summary,contrasts,warning,projection,map_summary)
    dump(out/"analysis-manifest.json",{"design_sha256":design["sha256"],"runs_reconstructed":len(rows),"core_runs_mapped":len(core_rows),
         "environment":environment(),"source_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob("*.py")},
         "note":"Host CPU timings vary between machines; deterministic mission, warning and map metrics should reproduce exactly."})
    print(json.dumps({"summary":[{k:s[k] for k in ("slowdown","fade_length","policy","restricted_mean_s","completion_proportion")} for s in summary],
                      "map":map_summary},indent=1))


def figures(out,paper,design,summary,warning,maps):
    save(fig.mission_time(summary,ALL_POLICIES,offset=0.08,ymax=None),paper,"extension-mission-time")
    save(fig.predictor_cost(warning,design["policy_predictors"]),paper,"predictor-cost-quality")
    save(fig.map_rmse(fig.map_curves(maps)),paper,"map-rmse-time")


def tables(paper,design,summary,contrasts,warning,projection,map_summary):
    def fmt(x,p=0): return "--" if x is None else f"{x:.{p}f}"
    with (paper/"extension-mission-table.tex").open("w",encoding="utf-8") as f:
        f.write("\\begin{tabular}{ll"+"r"*len(ALL_POLICIES)+"}\\toprule\nProgress & $L$ & "+" & ".join(ALL_POLICIES)+"\\\\\\midrule\n")
        for slow,length in CONDITIONS:
            g=[next(r for r in summary if r["slowdown"]==slow and r["fade_length"]==length and r["policy"]==p) for p in ALL_POLICIES]
            f.write(("Unequal" if slow else "Balanced")+f" & {length} & "+" & ".join(fmt(r["restricted_mean_s"]) for r in g)+"\\\\\n")
        f.write("\\midrule\nCompleted & all & "+" & ".join(str(round(sum(r["completion_proportion"]*r["n"] for r in summary if r["policy"]==p))) for p in ALL_POLICIES)+"\\\\\n")
        f.write("\\bottomrule\\end{tabular}\n")
    with (paper/"extension-contrasts.tex").open("w",encoding="utf-8") as f:
        f.write("\\begin{tabular}{llrrr}\\toprule\nContrast & Condition & Mean [s] & 95\\% CI [s] & Rel. [\\%]\\\\\\midrule\n")
        for r in contrasts:
            if r["role"] in ("primary","secondary") or r["comparison"] in ("S4-G minus S3","S4-O minus S3"):
                cond=("U" if r["slowdown"] else "B")+f", L={r['fade_length']}"
                f.write(f"{r['comparison']} & {cond} & {r['mean_difference_s']:.0f} & [{r['ci_low_s']:.0f}, {r['ci_high_s']:.0f}] & {r['relative_percent']:.1f}\\\\\n")
        f.write("\\bottomrule\\end{tabular}\n")
    with (paper/"predictor-table.tex").open("w",encoding="utf-8") as f:
        f.write("\\begin{tabular}{lrrrrrrr}\\toprule\nPredictor & Prec. & Recall & F1 & Lead [s] & Ops/dec. & Transc./dec. & Memory [B]\\\\\\midrule\n")
        for w in warning:
            if w["split"]!="extension-2000": continue
            f.write(f"{w['label']} & {fmt(w['precision'],2)} & {fmt(w['recall'],2)} & {fmt(w['f1'],3)} & {fmt(w['mean_lead_s'],1)} & "
                    f"{w['arithmetic_per_decision']:.0f} & {w['transcendental_per_decision']:.1f} & {w['memory_bytes']}\\\\\n")
        f.write("\\bottomrule\\end{tabular}\n")
    with (paper/"hardware-table.tex").open("w",encoding="utf-8") as f:
        ids=[p["id"] for p in hardware.PROFILES]
        f.write("\\begin{tabular}{l"+"r"*len(ids)+"}\\toprule\nPredictor & "+" & ".join(p["name"].split(" (")[0] for p in hardware.PROFILES)+"\\\\\\midrule\n")
        for name,spec in design["predictors"].items():
            cells=[]
            for pid in ids:
                r=next(x for x in projection if x["predictor"]==name and x["profile"]==pid)
                cells.append(f"{r['latency_us_low']:.1f}--{r['latency_us_high']:.1f}")
            f.write(f"{spec['label']} & "+" & ".join(cells)+"\\\\\n")
        f.write("\\bottomrule\\end{tabular}\n")
    with (paper/"map-table.tex").open("w",encoding="utf-8") as f:
        f.write("\\begin{tabular}{llrrrrr}\\toprule\nStudy & Policy & RMSE 900 s & RMSE 1800 s & Final RMSE & S-44 1a [\\%] & $\\le$0.5 m runs\\\\\\midrule\n")
        for m in map_summary:
            f.write(f"{m['study']} & {m['policy']} & {m['rmse_900_m']:.2f} & {m['rmse_1800_m']:.2f} & {m['final_rmse_m']:.2f} & {100*m['final_s44_fraction']:.1f} & {m['reached_0_5_m']}/{m['runs']}\\\\\n")
        f.write("\\bottomrule\\end{tabular}\n")


def main():
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("stage",choices=("tune","evaluate","analyze","all"))
    parser.add_argument("--output",type=Path,default=ROOT/"results/extension")
    parser.add_argument("--paper",type=Path,default=ROOT.parents[1]/"paper/Final_Report/generated/extension")
    parser.add_argument("--workers",type=int,default=4)
    args=parser.parse_args(); c=Config(); geometry(c.width,c.height)
    if args.stage in ("tune","all"):
        if (args.output/"extension-design.json").exists():
            parser.error("Extension design is already frozen; use a fresh --output directory")
        tune(c,args.output)
    if args.stage in ("evaluate","all"): evaluate(args.output,args.workers)
    if args.stage in ("analyze","all"): analyze(args.output,args.paper)


if __name__=="__main__": main()
