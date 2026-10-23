from __future__ import annotations

from dataclasses import asdict, dataclass, field
from functools import lru_cache
import gzip
import json
import math
from pathlib import Path
import random
import time
from typing import Callable

import numpy as np

POLICIES = ("S1", "S2", "S3", "S4-T", "S4-P")
# 0: no previous heading; 1 east, 2 north, 3 west, 4 south.
VECTORS = {1: (1, 0), 2: (0, 1), 3: (-1, 0), 4: (0, -1)}


@dataclass(frozen=True)
class Config:
    width: int = 20
    height: int = 12
    cell_m: float = 20.0
    speed_mps: float = 2.0
    turn_s: float = 5.0
    dt_s: int = 1
    exchange_s: int = 10
    timeout_s: int = 7200
    short_queue: int = 3
    long_queue: int = 12
    p0_dbm: float = -40.0
    path_exponent: float = 2.0
    d0_m: float = 1.0
    fade_db: float = -10.0
    threshold_dbm: float = -90.0
    fade_fraction: float = 0.2
    window: int = 5
    horizon: int = 3
    max_datagrams: int = 4
    max_bytes: int = 8192
    slowdown_factor: float = 0.5
    slowdown_s: int = 300
    slowdown_earliest: int = 600
    slowdown_latest: int = 900

    def __post_init__(self):
        if self.width < 2 or self.height < 1:
            raise ValueError("Need at least two columns and one row")
        if self.dt_s != 1 or self.exchange_s < 1 or self.timeout_s < 1:
            raise ValueError("The validated tick is one second; durations must be positive")
        if min(self.speed_mps, self.cell_m, self.d0_m) <= 0 or self.turn_s < 0:
            raise ValueError("Invalid motion or reference distance")
        if self.short_queue < 1 or self.long_queue < self.short_queue:
            raise ValueError("Invalid queue capacities")
        if not 0 < self.fade_fraction < 1 or not 0 < self.slowdown_factor <= 1:
            raise ValueError("Invalid disturbance parameters")
        if self.window < 2 or self.horizon < 1:
            raise ValueError("Invalid forecast window/horizon")

    @property
    def cells(self):
        return self.width * self.height

    def xy(self, cell):
        return (cell % self.width, cell // self.width)

    def centre(self, cell):
        x, y = self.xy(cell)
        return ((x + 0.5) * self.cell_m, (y + 0.5) * self.cell_m)


@dataclass
class Work:
    arithmetic: int = 0
    comparisons: int = 0
    logarithms: int = 0
    square_roots: int = 0
    decisions: int = 0
    cpu_ns: int = 0


@dataclass(frozen=True)
class Scenario:
    seed: int
    fade_length: int
    slowdown: bool
    onset_s: int
    fades: tuple[bool, ...]


def make_scenario(c: Config, seed: int, fade_length: int, slowdown: bool):
    if fade_length < 1 or c.fade_fraction / (fade_length * (1-c.fade_fraction)) > 1:
        raise ValueError("Invalid Markov transition probabilities")
    # Streams do not depend on policies, execution order, or number of decisions.
    fade_rng = random.Random(f"fade:{seed}:{fade_length}")
    slow_rng = random.Random(f"slow:{seed}")
    state = fade_rng.random() < c.fade_fraction
    fades = []
    for _ in range(c.timeout_s // c.exchange_s + 1):
        fades.append(state)
        probability = 1 / fade_length if state else c.fade_fraction / (fade_length * (1-c.fade_fraction))
        if fade_rng.random() < probability:
            state = not state
    return Scenario(seed, fade_length, slowdown,
                    slow_rng.randint(c.slowdown_earliest, c.slowdown_latest), tuple(fades))


def route(c: Config, start: int, target: int, heading: int):
    """Shortest Manhattan route; minimize turns, then prefer x before y."""
    sx, sy = c.xy(start)
    tx, ty = c.xy(target)
    horizontal = [1 if tx > sx else 3] * abs(tx-sx)
    vertical = [2 if ty > sy else 4] * abs(ty-sy)
    candidates = (horizontal + vertical, vertical + horizontal)
    def turns(directions):
        previous = heading
        count = 0
        for direction in directions:
            count += int(previous != 0 and previous != direction)
            previous = direction
        return count
    return min(candidates, key=turns)


@lru_cache(maxsize=8)
def geometry(width: int, height: int):
    # Integer grid geometry is policy-independent; no motion/prediction work here.
    c = Config(width=width, height=height)
    steps = np.empty((5, c.cells, c.cells), dtype=np.float64)
    turns = np.empty_like(steps)
    last = np.empty_like(steps, dtype=np.int8)
    for h in range(5):
        for s in range(c.cells):
            for t in range(c.cells):
                directions = route(c, s, t, h)
                steps[h,s,t] = len(directions)
                prev, count = h, 0
                for d in directions:
                    count += int(prev != 0 and prev != d)
                    prev = d
                turns[h,s,t] = count
                last[h,s,t] = prev
    return steps, turns, last


@dataclass
class Boat:
    id: int
    cell: int
    x: float
    y: float
    known: set[int]
    heading: int = 0
    target: int | None = None
    queue: list[int] = field(default_factory=list)
    directions: list[int] = field(default_factory=list)
    edge_target: int | None = None
    edge_remaining: float = 0.0
    turn_remaining: float = 0.0
    distance: float = 0.0
    idle: float = 0.0

    def start(self, c):
        while self.target is None and self.queue:
            candidate = self.queue.pop(0)
            if candidate in self.known:
                continue
            self.target = candidate
            self.directions = route(c, self.cell, candidate, self.heading)

    def tick(self, c: Config, speed: float, observe: Callable):
        self.start(c)
        budget = float(c.dt_s)
        while budget > 1e-9:
            if self.target is None:
                self.idle += budget
                break
            if self.edge_target is None:
                if not self.directions:
                    self.target = None
                    self.start(c)
                    continue
                direction = self.directions.pop(0)
                dx, dy = VECTORS[direction]
                self.edge_target = self.cell + dx + dy*c.width
                self.edge_remaining = c.cell_m
                self.turn_remaining = c.turn_s if self.heading and self.heading != direction else 0.0
                self.heading = direction
            if self.turn_remaining > 0:
                used = min(budget, self.turn_remaining)
                self.turn_remaining -= used
                budget -= used
                continue
            used = min(budget, self.edge_remaining/speed)
            travelled = used*speed
            dx,dy = VECTORS[self.heading]
            self.x += dx*travelled
            self.y += dy*travelled
            self.distance += travelled
            self.edge_remaining -= travelled
            budget -= used
            if self.edge_remaining < 1e-8:
                self.cell = self.edge_target
                self.x,self.y = c.centre(self.cell)
                self.edge_target = None
                observe(self.id, self.cell)
                if self.cell == self.target:
                    self.target = None
                    self.start(c)


def remaining(c: Config, b: Boat, speed: float, work: Work):
    if b.target is None:
        return 0.0,b.cell,b.heading
    total = b.turn_remaining + b.edge_remaining/speed
    work.arithmetic += 2
    heading = b.heading
    for direction in b.directions:
        total += c.cell_m/speed
        work.arithmetic += 2
        work.comparisons += 1
        if heading and direction != heading:
            total += c.turn_s
            work.arithmetic += 1
        heading = direction
    return total,b.target,heading


def allocate(c: Config, boats: list[Boat], known: set[int], speeds, capacity: int, work: Work):
    """All online policies use this exact greedy projected-finish-time rule."""
    started = time.process_time_ns()
    work.decisions += 1
    steps,turns,last = geometry(c.width,c.height)
    available = np.ones(c.cells,dtype=bool)
    available[list(known)] = False
    for b in boats:
        if b.target is not None:
            available[b.target] = False
    queues = [[],[]]
    endpoints = [remaining(c,b,speeds[b.id],work) for b in boats]
    seconds_per_cell = [c.cell_m/v for v in speeds]
    work.arithmetic += len(speeds)
    while available.any() and any(len(q)<capacity for q in queues):
        ids = np.flatnonzero(available)
        best = None
        for i in range(2):
            if len(queues[i]) >= capacity:
                continue
            elapsed,cell,heading = endpoints[i]
            scores = elapsed + steps[heading,cell,ids]*seconds_per_cell[i] + turns[heading,cell,ids]*c.turn_s
            work.arithmetic += 4*len(ids)
            work.comparisons += max(0,len(ids)-1)
            index = int(np.argmin(scores))
            task = int(ids[index])
            candidate = (float(scores[index]), task, i)
            work.comparisons += int(best is not None)
            if best is None or candidate < best:
                best = candidate
        if best is None:
            break
        score,task,i = best
        _,cell,heading = endpoints[i]
        endpoints[i] = score,task,int(last[heading,cell,task])
        queues[i].append(task)
        available[task] = False
    work.cpu_ns += time.process_time_ns()-started
    return queues


def signal(c: Config, positions, faded):
    d=math.hypot(positions[1][0]-positions[0][0],positions[1][1]-positions[0][1])
    r=c.p0_dbm-10*c.path_exponent*math.log10(max(d,c.d0_m)/c.d0_m)+(c.fade_db if faded else 0)
    return r,d


def forecast(c: Config, history: list[dict], method: str, margin: float, work: Work):
    """Input is successful past/current samples only; no Scenario is accessible."""
    started=time.process_time_ns()
    work.decisions += 1
    if not history:
        projected=[]
    elif method == "persistence" or len(history) < c.window:
        projected=[history[-1]["r"]]*(c.horizon+1)
    else:
        rows=history[-c.window:]
        now=rows[-1]["t"]
        xs=[float(s["t"]-now) for s in rows]
        residual=[]
        for s in rows:
            residual.append(s["r"]-(c.p0_dbm-10*c.path_exponent*math.log10(max(s["d"],c.d0_m)/c.d0_m)))
        # Center time to avoid subtracting large, almost-equal normal equations.
        xm=sum(xs)/len(xs); ym=sum(residual)/len(residual)
        numerator=sum((x-xm)*(y-ym) for x,y in zip(xs,residual))
        denominator=sum((x-xm)**2 for x in xs)
        slope=numerator/denominator
        intercept=ym-slope*xm
        prev,cur=rows[-2:]
        elapsed=cur["t"]-prev["t"]
        velocity=[(cur["u"][j]-prev["u"][j])/elapsed for j in range(2)]
        projected=[]
        for h in range(1,c.horizon+2):
            dt=h*c.exchange_s
            ux=cur["u"][0]+dt*velocity[0]; uy=cur["u"][1]+dt*velocity[1]
            distance=math.sqrt(ux*ux+uy*uy)
            projected.append(c.p0_dbm-10*c.path_exponent*math.log10(max(distance,c.d0_m)/c.d0_m)+intercept+slope*dt)
        n=len(rows); hcount=c.horizon+1
        # See operation-counts.md; integer loop/index/shape arithmetic excluded.
        work.arithmetic += 15*n + 9 + 14*hcount
        work.logarithms += n+hcount
        work.square_roots += hcount
        work.comparisons += n+hcount
    threshold=c.threshold_dbm+margin
    work.arithmetic += 1
    positive=False
    # Count executed comparisons, including short circuit behavior.
    for a,b in zip(projected,projected[1:]):
        work.comparisons += 1
        if a < threshold:
            work.comparisons += 1
            if b < threshold:
                positive=True
                break
    work.cpu_ns += time.process_time_ns()-started
    return positive,projected


def encode(payload):
    return json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")


class Log:
    def __init__(self,path=None):
        self.stream=None
        if path:
            Path(path).parent.mkdir(parents=True,exist_ok=True)
            self.stream=gzip.open(path,"wt",encoding="utf-8",compresslevel=1)
    def write(self,event):
        if self.stream:
            self.stream.write(json.dumps(event,separators=(",",":"),allow_nan=False)+"\n")
    def close(self):
        if self.stream:
            self.stream.close()


def fixed_queues(c):
    split=(c.width+1)//2
    queues=[]
    for columns in (range(split),range(split,c.width)):
        cells=[]
        for j,x in enumerate(columns):
            ys=range(c.height) if j%2==0 else range(c.height-1,-1,-1)
            cells.extend(y*c.width+x for y in ys)
        queues.append(cells)
    return queues


def run(c: Config, scenario: Scenario, policy: str, margins=None, log_path=None,
        forced_radio: Callable[[int],bool] | None=None):
    if policy not in POLICIES:
        raise ValueError(policy)
    geometry(c.width,c.height)  # Warm integer lookup tables outside component timing.
    margins=margins or {"trend":0,"persistence":0}
    method="trend" if policy=="S4-T" else "persistence"
    log=Log(log_path)
    coordinates=[0,c.width//2]
    # Odd grids use the first column in the right-hand partition.
    coordinates[1]=(c.width+1)//2
    initial=set(coordinates)
    boats=[Boat(i,cell,*c.centre(cell),set(initial)) for i,cell in enumerate(coordinates)]
    covered=set(); observations=0
    work={name:Work() for name in ("forecast","allocation","resync")}
    sessions=[]; history=[]; version=0; reservations=0
    attempted=delivered=bytes_attempted=bytes_delivered=budget_failures=0
    missing_sum=[0.0,0.0]; missing_n=0
    log.write({"event":"start","config":asdict(c),"scenario":asdict(scenario),"policy":policy,"margins":margins})
    t=0
    def observe(i,cell):
        nonlocal observations
        observations+=1; covered.add(cell); boats[i].known.add(cell)
        log.write({"event":"observe","t":t,"boat":i,"cell":cell})
    for b in boats:
        observe(b.id,b.cell)
    if policy=="S1":
        queues=fixed_queues(c)
        for b,q in zip(boats,queues):
            b.queue=[cell for cell in q if cell not in b.known]
    else:
        capacity=c.long_queue if policy=="S3" else c.short_queue
        queues=allocate(c,boats,initial,[c.speed_mps]*2,capacity,work["allocation"])
        for b,q in zip(boats,queues): b.queue=q
    log.write({"event":"initial_allocation","queues":[b.queue for b in boats]})
    complete=len(covered)==c.cells
    try:
        for t in range(1,c.timeout_s+1):
            if complete: t-=1; break
            speeds=[c.speed_mps]*2
            if scenario.slowdown and scenario.onset_s <= t < scenario.onset_s+c.slowdown_s:
                speeds[0]*=c.slowdown_factor
            for b in boats: b.tick(c,speeds[b.id],observe)
            log.write({"event":"tick","t":t,"xy":[[b.x,b.y] for b in boats],"idle":[b.idle for b in boats]})
            complete=len(covered)==c.cells
            if t%c.exchange_s==0:
                k=t//c.exchange_s
                positions=[[b.x,b.y] for b in boats]
                r,d=signal(c,positions,scenario.fades[k])
                radio=r>=c.threshold_dbm if forced_radio is None else forced_radio(k)
                missing=[len(covered-b.known)/c.cells for b in boats]
                missing_sum=[a+b for a,b in zip(missing_sum,missing)]; missing_n+=1
                entry={"event":"session","t":t,"k":k,"r":r,"d":d,"u":[positions[1][j]-positions[0][j] for j in range(2)],
                       "fade":scenario.fades[k],"radio":bool(radio),"distance_failure":bool(not radio and r-(c.fade_db if scenario.fades[k] else 0)<c.threshold_dbm),
                       "missing":missing,"warning":False,"projected":[],"committed":False,"budget_failure":False,
                       "attempted":0,"delivered":0,"bytes_attempted":0,"bytes_delivered":0}
                if policy!="S1" and not complete:
                    state=[{"type":"state","v":version,"t":t,"id":b.id,"xy":[b.x,b.y],"speed":speeds[b.id],
                            "known":hex(sum(1<<cell for cell in b.known)),"target":b.target,"queue":b.queue,
                            "edge_remaining":b.edge_remaining,"turn_remaining":b.turn_remaining,"heading":b.heading} for b in boats]
                    payloads=[encode(s) for s in state]
                    entry["attempted"]=2; entry["bytes_attempted"]=sum(map(len,payloads))
                    if radio:
                        start=time.process_time_ns()
                        merged=boats[0].known|boats[1].known
                        work["resync"].decisions+=1
                        work["resync"].comparisons+=len(boats[0].known)+len(boats[1].known)
                        work["resync"].cpu_ns+=time.process_time_ns()-start
                        trial_history=history+[entry]
                        warning=False; projected=[]
                        if policy.startswith("S4"):
                            warning,projected=forecast(c,trial_history,method,margins[method],work["forecast"])
                        capacity=c.long_queue if policy=="S3" or warning else c.short_queue
                        proposal=allocate(c,boats,merged,speeds,capacity,work["allocation"])
                        payloads += [encode({"type":"proposal","v":version+1,"queues":proposal}),encode({"type":"ack","v":version+1,"ids":[0,1]})]
                        entry.update(attempted=4,bytes_attempted=sum(map(len,payloads)))
                        fits=len(payloads)<=c.max_datagrams and sum(map(len,payloads))<=c.max_bytes
                        if fits:
                            version+=1; history.append(entry)
                            for b,q in zip(boats,proposal): b.known=set(merged); b.queue=q
                            extra=sum(max(0,len(q)-c.short_queue) for q in proposal) if warning else 0
                            reservations+=int(extra>0)
                            entry.update(committed=True,delivered=4,bytes_delivered=entry["bytes_attempted"],
                                         warning=warning,projected=projected,extra_reserved=extra)
                        else:
                            entry["budget_failure"]=True; budget_failures+=1
                    elif entry["bytes_attempted"]>c.max_bytes or c.max_datagrams<2:
                        entry["budget_failure"]=True; budget_failures+=1
                    # A budget rejection records the offered batch; transmitted bytes are zero.
                    if entry["budget_failure"]:
                        entry["offered_bytes"]=entry["bytes_attempted"]; entry["offered_datagrams"]=entry["attempted"]
                        entry["attempted"]=0; entry["bytes_attempted"]=0
                    attempted+=entry["attempted"]; delivered+=entry["delivered"]
                    bytes_attempted+=entry["bytes_attempted"]; bytes_delivered+=entry["bytes_delivered"]
                    entry["payloads"]=[p.decode("utf-8") for p in payloads]
                claims=[b.target for b in boats if b.target is not None]+[cell for b in boats for cell in b.queue]
                assert len(claims)==len(set(claims)),"Multiple owners"
                assert all(b.known<=covered for b in boats),"Invented coverage"
                assert entry["attempted"]<=c.max_datagrams and entry["bytes_attempted"]<=c.max_bytes
                entry.update(queues=[list(b.queue) for b in boats],targets=[b.target for b in boats],
                             known=[sorted(b.known) for b in boats],version=version,
                             work={name:asdict(w) for name,w in work.items()})
                sessions.append({key:entry[key] for key in ("t","k","r","d","u","radio","committed","warning","distance_failure","budget_failure")})
                log.write(entry)
            if complete: break
        result={"policy":policy,"seed":scenario.seed,"fade_length":scenario.fade_length,"slowdown":scenario.slowdown,
                "path_exponent":c.path_exponent,"complete":complete,"stop_s":t,"completion_s":t if complete else None,
                "restricted_s":t if complete else c.timeout_s,"coverage":len(covered)/c.cells,
                "observations":observations,"redundant":observations-len(covered),"distance_m":sum(b.distance for b in boats),
                "idle_s":[b.idle for b in boats],"attempted_messages":attempted,"delivered_messages":delivered,
                "attempted_bytes":bytes_attempted,"delivered_bytes":bytes_delivered,"budget_failures":budget_failures,
                "reservations":reservations,"conflicts":0,"missing_mean":[x/missing_n if missing_n else None for x in missing_sum],
                "missing_stop":[len(covered-b.known)/c.cells for b in boats],
                "link_availability":sum(s["radio"] for s in sessions)/len(sessions) if sessions else None,
                "distance_failures":sum(s["distance_failure"] for s in sessions),"work":{name:asdict(w) for name,w in work.items()}}
        log.write({"event":"stop","result":result,"known":[sorted(b.known) for b in boats]})
        return result,sessions
    finally:
        log.close()
