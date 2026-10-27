"""Post-hoc bathymetric map-accuracy diagnostic computed from recorded observation events.

The coordination model is unchanged. Each logged cell observation is replayed as a
swath of soundings over a synthetic analytic seabed. Vertical noise follows the IHO
S-44 total vertical uncertainty form TVU(d)=sqrt(a^2+(b d)^2) at 95 % confidence
(sigma=TVU/1.96); a per-observation horizontal offset converts slope into depth error.
Repeated observations are averaged; unobserved cells are filled from the nearest
observed cells by inverse-distance weighting. The seabed, noise orders and filling rule
are synthetic choices, so results describe relative map quality between policies in
this model, not real survey accuracy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np

from .analysis import read_events
from .model import Config

# IHO S-44 (6th ed.) TVU coefficients (a [m], b [-]) for selected survey orders.
S44 = {"special": (0.25, 0.0075), "1a": (0.5, 0.013), "2": (1.0, 0.023)}


@dataclass(frozen=True)
class SurveyModel:
    seabed_seed: int = 7
    points_per_side: int = 10      # 2 m sounding spacing inside a 20 m cell
    order: str = "1a"
    horizontal_sigma_m: float = 1.0
    base_depth_m: float = 18.0
    slope: float = 0.04            # depth gain per metre eastward
    relief_m: float = 2.0          # random-mode amplitude scale
    sand_wave_m: float = 0.4
    idw_neighbours: int = 4
    checkpoint_s: int = 300


class Seabed:
    """Smooth analytic depth field: plane + random cosine modes + sand waves (metres, positive down)."""
    def __init__(self, c: Config, m: SurveyModel):
        rng=np.random.default_rng(m.seabed_seed)
        n=24
        wavelength=rng.uniform(40,220,n); angle=rng.uniform(0,np.pi,n)
        self.k=np.stack([np.cos(angle),np.sin(angle)],1)*(2*np.pi/wavelength)[:,None]
        self.phase=rng.uniform(0,2*np.pi,n); self.amp=m.relief_m*rng.uniform(.3,1,n)/math.sqrt(n/4)
        self.m=m
    def depth(self, x, y):
        x=np.asarray(x,float); y=np.asarray(y,float)
        modes=np.cos(np.multiply.outer(x,self.k[:,0])+np.multiply.outer(y,self.k[:,1])+self.phase)@self.amp
        return self.m.base_depth_m+self.m.slope*x+modes+self.m.sand_wave_m*np.sin(2*np.pi*(x+.3*y)/25)


def tvu(depth, order="1a"):
    a,b=S44[order]
    return np.sqrt(a*a+(b*depth)**2)


class Survey:
    def __init__(self, c: Config, m: SurveyModel = SurveyModel()):
        self.c=c; self.m=m; self.seabed=Seabed(c,m)
        offsets=(np.arange(m.points_per_side)+.5)/m.points_per_side*c.cell_m
        ox,oy=np.meshgrid(offsets,offsets)
        self.local=np.stack([ox.ravel(),oy.ravel()],1)
        corners=np.array([[c.xy(cell)[0]*c.cell_m,c.xy(cell)[1]*c.cell_m] for cell in range(c.cells)])
        self.points=corners[:,None,:]+self.local[None]           # cells x points x 2
        self.truth=self.seabed.depth(self.points[...,0],self.points[...,1])
        self.limit=tvu(self.truth,m.order)
        centres=np.array([c.centre(cell) for cell in range(c.cells)])
        self.distance=np.hypot(*(centres[:,None,:]-centres[None]).transpose(2,0,1))

    def sounding(self, cell, rng):
        shift=rng.normal(0,self.m.horizontal_sigma_m,2)
        p=self.points[cell]+shift
        true=self.seabed.depth(p[:,0],p[:,1])
        return true+rng.normal(0,1,len(true))*tvu(true,self.m.order)/1.96

    def metrics(self, sums, counts):
        observed=counts>0
        estimate=np.zeros_like(self.truth)
        estimate[observed]=sums[observed]/counts[observed][:,None]
        if observed.any() and not observed.all():
            seen=np.flatnonzero(observed); k=min(self.m.idw_neighbours,len(seen))
            for cell in np.flatnonzero(~observed):
                d=self.distance[cell,seen]; nearest=np.argsort(d)[:k]
                w=1/d[nearest]**2
                estimate[cell]=(w[:,None]*estimate[seen[nearest]]).sum(0)/w.sum()
        error=estimate-self.truth
        if not observed.any():
            return {"coverage":0.0,"rmse_m":None,"rmse_observed_m":None,"s44_compliant_fraction":0.0,"redundant_cells":0}
        return {"coverage":float(observed.mean()),"rmse_m":float(np.sqrt(np.mean(error**2))),
                "rmse_observed_m":float(np.sqrt(np.mean(error[observed]**2))),
                "s44_compliant_fraction":float(np.mean(np.abs(error)<=self.limit)),
                "redundant_cells":int(np.sum(counts>1))}


def evaluate_log(path, survey: Survey, key: str):
    """Replay observations in log order; return checkpoints and the stopping-state map."""
    c=survey.c; m=survey.m
    rng=np.random.default_rng([m.seabed_seed,*key.encode()])
    sums=np.zeros_like(survey.truth); counts=np.zeros(c.cells,dtype=int)
    curve=[]; next_check=m.checkpoint_s; stop=None
    for e in read_events(path):
        if e["event"]=="observe":
            while e["t"]>next_check:
                curve.append({"t":next_check,**survey.metrics(sums,counts)}); next_check+=m.checkpoint_s
            sums[e["cell"]]+=survey.sounding(e["cell"],rng); counts[e["cell"]]+=1
        elif e["event"]=="stop":
            stop=e["result"]["stop_s"]
    if stop is None:
        raise ValueError(f"Incomplete log: {path}")
    final=survey.metrics(sums,counts)
    while next_check<=c.timeout_s:
        # After stopping, the map is frozen; checkpoints keep a common time axis.
        curve.append({"t":next_check,**final}); next_check+=m.checkpoint_s
    return {"stop_s":stop,"final":final,"curve":curve,"model":asdict(m)}
