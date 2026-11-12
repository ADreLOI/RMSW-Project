"""Separate host timing, total process RAM, and incremental Python memory."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
import tracemalloc

import psutil

from . import model
from .experiment import dump,environment


def snapshots():
    captured={}
    original_alloc,original_forecast=model.allocate,model.forecast
    counts={"a":0,"f":0}
    def alloc(*args):
        counts["a"]+=1
        if counts["a"]==20: captured["allocation"]=deepcopy(args[:-1])
        return original_alloc(*args)
    def predict(*args):
        counts["f"]+=1
        if counts["f"]==20: captured["forecast"]=deepcopy(args[:-1])
        return original_forecast(*args)
    model.allocate,model.forecast=alloc,predict
    try: model.run(model.Config(),model.make_scenario(model.Config(),0,5,True),"S4-T",{"trend":4,"persistence":4})
    finally: model.allocate,model.forecast=original_alloc,original_forecast
    return captured


def repeated(function,args):
    repetitions=1
    while True:
        start=time.process_time_ns()
        for _ in range(repetitions): function(*args,model.Work())
        cpu=time.process_time_ns()-start
        if cpu>=150_000_000: break
        repetitions*=2
    cpu_rows=[]; wall_rows=[]
    for _ in range(7):
        cpu0=time.process_time_ns(); wall0=time.perf_counter_ns()
        for _ in range(repetitions): function(*args,model.Work())
        wall_rows.append((time.perf_counter_ns()-wall0)/repetitions)
        cpu_rows.append((time.process_time_ns()-cpu0)/repetitions)
    work=model.Work(); function(*args,work)
    tracemalloc.start(); baseline=tracemalloc.get_traced_memory()[0]; tracemalloc.reset_peak()
    function(*args,model.Work()); current,peak=tracemalloc.get_traced_memory(); tracemalloc.stop()
    return {"repetitions_per_batch":repetitions,"batches":7,"median_cpu_ns":statistics.median(cpu_rows),
            "median_wall_ns":statistics.median(wall_rows),"cpu_ns_batches":cpu_rows,"wall_ns_batches":wall_rows,
            "incremental_python_peak_bytes":max(0,peak-baseline),"work":asdict(work)}


def main():
    p=argparse.ArgumentParser(); p.add_argument("--output",type=Path,default=Path("results/core/host-benchmark.json"))
    p.add_argument("--child",choices=model.POLICIES); args=p.parse_args()
    c=model.Config(); model.geometry(c.width,c.height)
    if args.child:
        process=psutil.Process(); baseline=process.memory_info().rss
        result,_=model.run(c,model.make_scenario(c,1000,5,True),args.child,{"trend":4,"persistence":4})
        info=process.memory_info()
        if not hasattr(info,"peak_wset"):
            raise RuntimeError("This host RAM procedure uses Windows peak_wset; implement OS high-water RSS for another OS")
        print(json.dumps({"policy":args.child,"baseline_rss_bytes":baseline,"peak_process_rss_bytes":info.peak_wset,
                          "final_rss_bytes":info.rss,"complete":result["complete"]})); return
    captured=snapshots(); a=captured["allocation"]; f=captured["forecast"]
    serialized_boats=[]
    for b in a[1]:
        data=asdict(b); data["known"]=sorted(data["known"]); serialized_boats.append(data)
    inputs={"config":asdict(c),"allocation":{"boats":serialized_boats,"known":sorted(a[2]),"speeds":a[3],"capacity":a[4]},
            "forecast":{"history":[{k:s[k] for k in ("t","r","d","u")} for s in f[1]],"margin":f[3]}}
    dump(args.output.with_name("benchmark-inputs.json"),inputs)
    timings={"allocation":repeated(model.allocate,a),"trend":repeated(model.forecast,f),
             "persistence":repeated(model.forecast,(f[0],f[1],"persistence",f[3]))}
    rss=[]
    for policy in model.POLICIES:
        text=subprocess.check_output([sys.executable,"-m","usv_sim.benchmark","--child",policy],text=True)
        rss.append(json.loads(text))
    dump(args.output,{"environment":environment(),"timings":timings,"process_memory":rss,
        "procedure":"Pilot seed 0, L=5, slowdown; saved 20th coordination inputs. Warm integer geometry cache. CPU batches exceed 150 ms; seven batches; allocations profiled separately. RAM uses isolated process high-water working set; no raw log buffering.",
        "limits":"Host-specific timing, wrapper/loop overhead included. Incremental tracemalloc excludes native allocations. Total RAM includes Python, NumPy, geometry, and simulation state. No power or device-lifetime estimate."})
    print(json.dumps({"timings":timings,"process_memory":rss},indent=2))


if __name__=="__main__": main()
