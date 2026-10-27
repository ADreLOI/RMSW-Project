"""Outage-warning predictors for the extension study (persistence, trend and five comparators).

Every predictor answers the frozen question: will at least two consecutive scheduled
exchanges fail, starting within the next H intervals? Inputs are successful past samples
only, except FadeOracle, which reads future fade states and is a non-deployable bound.
Instances keep recursive state, so build one per run with make().

Work counts follow operation-counts.md: binary64 add/sub/mul/div count one each;
log10, sqrt, exp and tanh are counted separately as transcendental calls; comparisons
are logical tests. Counts are algorithmic, not processor instructions or energy.
"""
from __future__ import annotations

import itertools
import math
import time

import numpy as np

from .events import outage_events
from .model import Config, Work, forecast

BYTES = 8  # binary64 parameters and state


def pathloss(c: Config, d: float):
    return c.p0_dbm-10*c.path_exponent*math.log10(max(d,c.d0_m)/c.d0_m)


def motion(c: Config, history, work: Work):
    """Constant relative velocity from the latest two successful samples, as in trend."""
    cur=history[-1]
    if len(history)<2:
        return [cur["d"]]*(c.horizon+1)
    prev=history[-2]
    elapsed=cur["t"]-prev["t"]
    velocity=[(cur["u"][j]-prev["u"][j])/elapsed for j in range(2)]
    out=[]
    for h in range(1,c.horizon+2):
        dt=h*c.exchange_s
        ux=cur["u"][0]+dt*velocity[0]; uy=cur["u"][1]+dt*velocity[1]
        out.append(math.sqrt(ux*ux+uy*uy))
    k=c.horizon+1
    work.arithmetic += 4+8*k; work.square_roots += k
    return out


def project(c: Config, distances, residuals, work: Work):
    out=[pathloss(c,d)+e for d,e in zip(distances,residuals)]
    k=len(out)
    work.arithmetic += 4*k; work.logarithms += k; work.comparisons += k
    return out


def rule(c: Config, projected, threshold, work: Work):
    """Shared warning rule: an onset within H followed by a second projected miss."""
    for a,b in zip(projected,projected[1:]):
        work.comparisons += 1
        if a < threshold:
            work.comparisons += 1
            if b < threshold:
                return True
    return False


def residual(c: Config, sample, work: Work):
    work.arithmetic += 4; work.logarithms += 1; work.comparisons += 1
    return sample["r"]-pathloss(c,sample["d"])


class Predictor:
    name="base"; deployable=True
    def __init__(self, **params):
        self.params=params; self.seen=0
    def memory_bytes(self):
        """Parameters plus retained state, binary64; excludes interpreter overhead."""
        return BYTES*(self.n_params()+self.n_state())
    def n_params(self): return len(self.params)
    def n_state(self): return 0
    def update(self, c, sample, work): pass
    def decide(self, c, history, work): raise NotImplementedError
    def __call__(self, c: Config, history, work: Work):
        started=time.process_time_ns(); work.decisions += 1
        if not history:
            work.cpu_ns += time.process_time_ns()-started
            return False,[]
        while self.seen < len(history):
            self.update(c,history[self.seen],work); self.seen += 1
        warning,projected=self.decide(c,history,work)
        work.cpu_ns += time.process_time_ns()-started
        return warning,projected


class Frozen(Predictor):
    """The frozen persistence/trend forecasts, wrapped without changing their counts."""
    def __init__(self, method, margin):
        super().__init__(margin=margin); self.method=method; self.name=method
    def n_state(self): return 5*5 if self.method=="trend" else 1  # W samples of t, r, d, ux, uy
    def __call__(self, c, history, work):
        return forecast(c,history,self.method,self.params["margin"],work)


class EWMA(Predictor):
    """Exponentially weighted residual level plus the relative-motion distance forecast."""
    name="ewma"
    def __init__(self, alpha, margin):
        super().__init__(alpha=alpha,margin=margin); self.level=None
    def n_state(self): return 1+5  # level and two motion samples
    def update(self, c, sample, work):
        e=residual(c,sample,work)
        if self.level is None: self.level=e
        else:
            self.level=self.params["alpha"]*e+(1-self.params["alpha"])*self.level; work.arithmetic += 4
    def decide(self, c, history, work):
        projected=project(c,motion(c,history,work),[self.level]*(c.horizon+1),work)
        work.arithmetic += 1
        return rule(c,projected,c.threshold_dbm+self.params["margin"],work),projected


class Kalman(Predictor):
    """Two-state (level, slope) Kalman filter on the residual with irregular time steps."""
    name="kalman"
    def __init__(self, q, r, margin):
        super().__init__(q=q,r=r,margin=margin); self.x=None; self.P=None; self.t=None
    def n_state(self): return 2+4+1+5
    def update(self, c, sample, work):
        z=residual(c,sample,work)
        if self.x is None:
            self.x=[z,0.0]; self.P=[[self.params["r"],0.0],[0.0,1.0]]; self.t=sample["t"]; return
        dt=sample["t"]-self.t; self.t=sample["t"]; q=self.params["q"]
        x0=self.x[0]+dt*self.x[1]; x1=self.x[1]
        (a,b),(_,d)=self.P
        # P' = F P F^T + Q with F=[[1,dt],[0,1]], Q=q*[[dt^3/3,dt^2/2],[dt^2/2,dt]]
        p00=a+2*dt*b+dt*dt*d+q*dt**3/3; p01=b+dt*d+q*dt*dt/2; p11=d+q*dt
        s=p00+self.params["r"]; k0=p00/s; k1=p01/s; innovation=z-x0
        self.x=[x0+k0*innovation,x1+k1*innovation]
        self.P=[[(1-k0)*p00,(1-k0)*p01],[(1-k0)*p01,p11-k1*p01]]
        work.arithmetic += 2+9+5+3+4+1+4+6
    def decide(self, c, history, work):
        residuals=[self.x[0]+self.x[1]*h*c.exchange_s for h in range(1,c.horizon+2)]
        work.arithmetic += 3*(c.horizon+1)+1
        projected=project(c,motion(c,history,work),residuals,work)
        return rule(c,projected,c.threshold_dbm+self.params["margin"],work),projected


class GilbertHMM(Predictor):
    """Bayesian two-state burst model: P(two consecutive misses starting within H).

    The fade state is read from the latest successful residual; transitions were fitted
    on pilot traces. Each of the 2^(H+1) future fade paths is weighted and checked.
    """
    name="gilbert"
    def __init__(self, p_cf, p_fc, fade_db, tau, margin):
        super().__init__(p_cf=p_cf,p_fc=p_fc,fade_db=fade_db,tau=tau,margin=margin); self.state=0
    def n_state(self): return 1+5+2**4
    def update(self, c, sample, work):
        self.state=int(residual(c,sample,work) < self.params["fade_db"]/2); work.arithmetic += 1; work.comparisons += 1
    def decide(self, c, history, work):
        distances=motion(c,history,work)
        clear=project(c,distances,[0.0]*len(distances),work)
        threshold=c.threshold_dbm+self.params["margin"]; work.arithmetic += 1
        p=self.params; probability=0.0; state=self.state
        for path in itertools.product((0,1),repeat=c.horizon+1):
            weight=1.0; previous=state
            for s in path:
                stay=(1-p["p_cf"]) if previous==0 else (1-p["p_fc"])
                weight*=stay if s==previous else 1-stay; previous=s
            misses=[r+(p["fade_db"] if s else 0.0) < threshold for r,s in zip(clear,path)]
            if any(a and b for a,b in zip(misses,misses[1:])): probability+=weight
        n=2**(c.horizon+1); k=c.horizon+1
        work.arithmetic += n*(3*k+1); work.comparisons += n*(3*k)
        work.comparisons += 1
        return probability > p["tau"],clear


FEATURES=("r_margin","clear_h1","clear_h2","clear_h3","clear_h4","residual","residual_slope","gap","range_rate")


def features(c: Config, history, work: Work):
    """Nine causal features from successful samples; scaled to O(1) by fixed constants."""
    cur=history[-1]
    distances=motion(c,history,work)
    e=residual(c,cur,work)
    clear=project(c,distances,[e]*len(distances),work)
    slope=0.0; gap=c.exchange_s; rate=0.0
    if len(history)>=2:
        prev=history[-2]; gap=cur["t"]-prev["t"]
        slope=(e-residual(c,prev,work))/gap; rate=(cur["d"]-prev["d"])/gap
        work.arithmetic += 5
    x=[(cur["r"]-c.threshold_dbm)/10,*[(r-c.threshold_dbm)/10 for r in clear],e/10,slope,gap/c.exchange_s,rate/c.speed_mps]
    work.arithmetic += 2+2*len(clear)+1+1+1
    return x


class Logistic(Predictor):
    name="logistic"
    def __init__(self, weights, bias, mean, scale, tau):
        super().__init__(tau=tau); self.w=list(weights); self.b=bias; self.mean=list(mean); self.scale=list(scale)
    def n_params(self): return len(self.w)+1+len(self.mean)+len(self.scale)+1
    def n_state(self): return 5
    def decide(self, c, history, work):
        x=features(c,history,work)
        z=self.b+sum(w*(v-m)/s for w,v,m,s in zip(self.w,x,self.mean,self.scale))
        probability=1/(1+math.exp(-z))
        work.arithmetic += 4*len(x)+3; work.logarithms += 1; work.comparisons += 1
        return probability > self.params["tau"],[probability]


class MLP(Predictor):
    """One hidden tanh layer; weights trained on pilot replay features."""
    name="mlp"
    def __init__(self, w1, b1, w2, b2, mean, scale, tau):
        super().__init__(tau=tau)
        self.w1=np.asarray(w1); self.b1=np.asarray(b1); self.w2=np.asarray(w2); self.b2=float(b2)
        self.mean=np.asarray(mean); self.scale=np.asarray(scale)
    def n_params(self): return self.w1.size+self.b1.size+self.w2.size+1+self.mean.size+self.scale.size+1
    def n_state(self): return 5+self.b1.size
    def decide(self, c, history, work):
        x=(np.asarray(features(c,history,work))-self.mean)/self.scale
        hidden=np.tanh(x@self.w1+self.b1)
        z=float(hidden@self.w2+self.b2); probability=1/(1+math.exp(-z))
        f,h=self.w1.shape
        work.arithmetic += 2*f+2*f*h+2*h+3; work.logarithms += h+1; work.comparisons += 1
        return probability > self.params["tau"],[probability]


class FadeOracle(Predictor):
    """Non-deployable bound: true future fade states with the same motion projection."""
    name="fade-oracle"; deployable=False
    def __init__(self, fades, margin):
        super().__init__(margin=margin); self.fades=fades
    def decide(self, c, history, work):
        k=history[-1]["k"]
        future=[c.fade_db if self.fades[min(k+h,len(self.fades)-1)] else 0.0 for h in range(1,c.horizon+2)]
        projected=project(c,motion(c,history,work),future,work)
        work.arithmetic += 1
        return rule(c,projected,c.threshold_dbm+self.params["margin"],work),projected


def make(spec, fades=None):
    """Build a fresh predictor from a JSON specification {"kind":..., **params}."""
    kind=spec["kind"]; params={k:v for k,v in spec.items() if k not in ("kind","label")}
    if kind in ("trend","persistence"): return Frozen(kind,params["margin"])
    if kind=="fade-oracle": return FadeOracle(fades,params["margin"])
    return {"ewma":EWMA,"kalman":Kalman,"gilbert":GilbertHMM,"logistic":Logistic,"mlp":MLP}[kind](**params)


def labels(samples, horizon):
    """1 when an eligible outage onset follows a successful sample by 1..H exchanges."""
    onsets=[a for a,b in outage_events(samples) if a>=horizon]
    return [int(s["radio"] and any(1<=onset-i<=horizon for onset in onsets)) for i,s in enumerate(samples)]


def training_rows(c: Config, traces):
    rows=[]; targets=[]
    for trace in traces:
        samples=trace["samples"]; y=labels(samples,c.horizon); history=[]
        for s,label in zip(samples,y):
            if not s["radio"]: continue
            history.append(s)
            rows.append(features(c,history,Work())); targets.append(label)
    return np.asarray(rows,dtype=float),np.asarray(targets,dtype=float)


def fit_logistic(x, y, l2=1e-2, steps=3000, rate=0.2):
    mean=x.mean(0); scale=x.std(0); scale[scale==0]=1
    z=(x-mean)/scale; w=np.zeros(z.shape[1]); b=0.0
    weight=np.where(y==1,0.5/max(y.mean(),1e-9),0.5/max(1-y.mean(),1e-9))
    for _ in range(steps):
        p=1/(1+np.exp(-(z@w+b)))
        g=weight*(p-y)
        w-=rate*(z.T@g/len(y)+l2*w); b-=rate*g.mean()
    return {"weights":w.tolist(),"bias":float(b),"mean":mean.tolist(),"scale":scale.tolist()}


def fit_mlp(x, y, hidden=16, steps=4000, rate=0.01, l2=1e-3, seed=20261027):
    rng=np.random.default_rng(seed)
    mean=x.mean(0); scale=x.std(0); scale[scale==0]=1
    z=(x-mean)/scale; f=z.shape[1]
    w1=rng.normal(0,1/math.sqrt(f),(f,hidden)); b1=np.zeros(hidden); w2=rng.normal(0,1/math.sqrt(hidden),hidden); b2=0.0
    weight=np.where(y==1,0.5/max(y.mean(),1e-9),0.5/max(1-y.mean(),1e-9))
    params=[w1,b1,w2,np.array([b2])]; m=[np.zeros_like(p) for p in params]; v=[np.zeros_like(p) for p in params]
    for step in range(1,steps+1):
        h=np.tanh(z@params[0]+params[1]); p=1/(1+np.exp(-(h@params[2]+params[3][0])))
        g=weight*(p-y)/len(y)
        gw2=h.T@g+l2*params[2]; gb2=np.array([g.sum()])
        gh=np.outer(g,params[2])*(1-h*h)
        gw1=z.T@gh+l2*params[0]; gb1=gh.sum(0)
        for i,grad in enumerate((gw1,gb1,gw2,gb2)):
            m[i]=0.9*m[i]+0.1*grad; v[i]=0.999*v[i]+0.001*grad*grad
            params[i]-=rate*(m[i]/(1-0.9**step))/(np.sqrt(v[i]/(1-0.999**step))+1e-8)
    return {"w1":params[0].tolist(),"b1":params[1].tolist(),"w2":params[2].tolist(),"b2":float(params[3][0]),
            "mean":mean.tolist(),"scale":scale.tolist()}


def fit_gilbert(c: Config, traces):
    """Pooled fade-state transition frequencies from labelled pilot traces.

    Along fixed routes a faded exchange almost never succeeds, so the fade state is not
    observable from successful samples alone. The pilot therefore acts as a labelled
    calibration campaign: its recorded fade sequence (disjoint from evaluation seeds)
    supplies the transitions, pooled over all three mean fade durations.
    """
    counts={(0,0):0,(0,1):0,(1,0):0,(1,1):0}
    for trace in traces:
        fades=[int(f) for f in trace["fades"][:len(trace["samples"])]]
        for a,b in zip(fades,fades[1:]): counts[(a,b)]+=1
    p_cf=counts[(0,1)]/max(1,counts[(0,0)]+counts[(0,1)])
    p_fc=counts[(1,0)]/max(1,counts[(1,0)]+counts[(1,1)])
    return {"p_cf":p_cf,"p_fc":p_fc,"fade_db":c.fade_db,"transition_counts":{f"{a}{b}":n for (a,b),n in counts.items()}}
