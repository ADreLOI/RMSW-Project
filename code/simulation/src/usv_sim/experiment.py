from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

import numpy as np

from .events import warning_scores
from .model import Config, POLICIES, Work, forecast, geometry, make_scenario, run


def dump(path,data):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+".tmp")
    temporary.write_text(json.dumps(data,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    temporary.replace(path)


def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


def tune(c: Config, destination: Path):
    """Pilot fixed-route replay only; never use evaluation mission outcomes."""
    rows=[]; traces=[]
    for seed in range(10):
        for slowdown in (False,True):
            for length in (2,5,10):
                scenario=make_scenario(c,seed,length,slowdown)
                result,samples=run(c,scenario,"S1",log_path=destination/"raw"/f"pilot-reference-{seed}-{int(slowdown)}-{length}.jsonl.gz")
                traces.append({"seed":seed,"slowdown":slowdown,"length":length,"samples":samples})
    for method in ("trend","persistence"):
        for margin in (0,2,4):
            counts={k:0 for k in ("true_positives","false_positives","false_negatives","eligible_outages","alerts")}
            for trace in traces:
                history=[]; evaluated=[]
                for s in trace["samples"]:
                    item=dict(s)
                    if s["radio"]:
                        history.append(s)
                        item["warning"],_=forecast(c,history,method,margin,Work())
                        item["committed"]=True
                    evaluated.append(item)
                scores=warning_scores(evaluated,c.horizon)
                for k in counts: counts[k]+=scores[k]
            tp,fp,fn=(counts[k] for k in ("true_positives","false_positives","false_negatives"))
            rows.append({"method":method,"margin_db":margin,**counts,"f1":2*tp/(2*tp+fp+fn) if counts["eligible_outages"] else None})
    if not any(row["eligible_outages"] for row in rows):
        raise RuntimeError("Pilot has no eligible outages; expand pilot, never tune on evaluation")
    margins={method:min((r for r in rows if r["method"]==method),key=lambda r:(-r["f1"],r["margin_db"]))["margin_db"] for method in ("trend","persistence")}
    pilot=[]
    for trace in traces:
        for policy in POLICIES[1:]:
            seed,length,slowdown=trace["seed"],trace["length"],trace["slowdown"]
            result,samples=run(c,make_scenario(c,seed,length,slowdown),policy,margins,
                              destination/"raw"/f"pilot-{seed}-{int(slowdown)}-{length}-{policy}.jsonl.gz")
            result["warnings"]=warning_scores(samples,c.horizon)
            pilot.append(result)
    dump(destination/"pilot-online-runs.json",pilot)
    freeze={"schema":1,"config":asdict(c),"pilot_seeds":list(range(10)),"evaluation_seeds":list(range(1000,1030)),
            "fade_lengths":[2,5,10],"slowdown":[False,True],"policies":list(POLICIES),"margins":margins,
            "bootstrap_resamples":2000,"bootstrap_seed":20261023,"primary":"S4-T minus S2",
            "secondary":["S4-T minus S3","S4-T minus S4-P"],"event_rule":"events.py; exclude first H onsets and last H+1 alert slots",
            "tuning":rows,"frozen_before_evaluation":True}
    freeze["sha256"]=digest(freeze)
    dump(destination/"frozen-design.json",freeze)
    dump(destination/"pilot-replay-traces.json",traces)
    print(json.dumps({"pilot_reference_runs":len(traces),"margins":margins,"freeze_sha256":freeze["sha256"]}),flush=True)
    return freeze


def worker(task):
    cdata,seed,length,slowdown,policy,margins,path=task
    c=Config(**cdata)
    start=time.perf_counter()
    result,samples=run(c,make_scenario(c,seed,length,slowdown),policy,margins,path)
    result["warnings"]=warning_scores(samples,c.horizon)
    result["wall_s"]=time.perf_counter()-start
    return result


def environment():
    import matplotlib, psutil
    try: revision=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
    except (OSError,subprocess.CalledProcessError): revision=None
    return {"python":sys.version,"platform":platform.platform(),"processor":platform.processor(),
            "logical_cpus":os.cpu_count(),"physical_cpus":psutil.cpu_count(logical=False),
            "ram_bytes":psutil.virtual_memory().total,"numpy":np.__version__,"matplotlib":matplotlib.__version__,
            "psutil":psutil.__version__,"git_base":revision,"numerics":"IEEE 754 binary64; no BLAS in forecast/allocator",
            "timing":"process_time_ns per component; excludes logging and plotting; benchmark.py separately repeats saved inputs"}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("stage",choices=("pilot","evaluate","single"))
    parser.add_argument("--output",type=Path)
    parser.add_argument("--workers",type=int,default=1)
    parser.add_argument("--policy",choices=POLICIES,default="S4-T")
    parser.add_argument("--seed",type=int,default=1000)
    parser.add_argument("--length",type=int,default=5)
    parser.add_argument("--slowdown",action="store_true")
    parser.add_argument("--exponent",type=float)
    parser.add_argument("--design",type=Path,default=Path(__file__).resolve().parents[2]/"results/core/frozen-design.json")
    parser.add_argument("--overwrite",action="store_true",help="Explicitly replace existing CLI outputs; prefer fresh workflow bundles")
    args=parser.parse_args(); c=Config()
    args.output=args.output or Path("results/single" if args.stage=="single" else "results/core")
    if args.stage=="single" and args.output.resolve()==(Path(__file__).resolve().parents[2]/"results/core").resolve():
        parser.error("Single runs must use a separate output directory, outside the frozen core")
    if args.stage=="evaluate" and args.exponent is not None:
        parser.error("Evaluation uses the frozen config. For sensitivity, create a separate design or use the exploratory dashboard.")
    target={"pilot":"frozen-design.json","evaluate":"runs.json","single":"single.json"}[args.stage]
    if (args.output/target).exists() and not args.overwrite:
        parser.error(f"{args.output/target} already exists; use a fresh output directory or explicit --overwrite")
    args.output.mkdir(parents=True,exist_ok=True)
    if args.exponent is not None: c=replace(c,path_exponent=args.exponent)
    dump(args.output/"environment.json",environment())
    geometry(c.width,c.height)
    if args.stage=="pilot": tune(c,args.output); return
    if args.stage=="single":
        from .evidence import load_design
        design=load_design(args.design)
        c=Config(**design["config"])
        if args.exponent is not None: c=replace(c,path_exponent=args.exponent)
        r=worker((asdict(c),args.seed,args.length,args.slowdown,args.policy,design["margins"],args.output/"single.jsonl.gz"))
        dump(args.output/"single-settings.json",{"config":asdict(c),"margins":design["margins"],"design_sha256":design["sha256"],"classification":"separate single-run reproduction / exploration"})
        dump(args.output/"single.json",r); print(json.dumps(r)); return
    freeze=json.loads((args.output/"frozen-design.json").read_text())
    expected=freeze.pop("sha256")
    if digest(freeze)!=expected: raise RuntimeError("Frozen design hash mismatch")
    freeze["sha256"]=expected
    c=Config(**freeze["config"])
    if args.exponent is not None: c=replace(c,path_exponent=args.exponent)
    tasks=[]
    for seed in freeze["evaluation_seeds"]:
        for slowdown in freeze["slowdown"]:
            for length in freeze["fade_lengths"]:
                for policy in freeze["policies"]:
                    name=f"{seed}-{int(slowdown)}-{length}-{policy}"
                    tasks.append((asdict(c),seed,length,slowdown,policy,freeze["margins"],args.output/"raw"/f"{name}.jsonl.gz"))
    # Any failure propagates as a software error. No exception is recoded as a timeout.
    start=time.perf_counter(); rows=[]
    with multiprocessing.Pool(args.workers) as pool:
        for i,row in enumerate(pool.imap_unordered(worker,tasks,chunksize=5),1):
            rows.append(row)
            if i%25==0: print(f"{i}/{len(tasks)} runs, {time.perf_counter()-start:.1f}s",flush=True)
    rows.sort(key=lambda r:(r["seed"],r["slowdown"],r["fade_length"],r["policy"]))
    dump(args.output/"runs.json",rows)
    dump(args.output/"evaluation-manifest.json",{"runs":len(rows),"design_sha256":expected,"elapsed_s":time.perf_counter()-start,
         "path_exponent":c.path_exponent,"completed":True,"source_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob("*.py")}})
    print(f"Saved {len(rows)} runs",flush=True)


if __name__=="__main__": main()
