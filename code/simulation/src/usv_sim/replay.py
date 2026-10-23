"""Offline, dependency-free browser replay of retained simulator evidence."""
import argparse
import json
from pathlib import Path
from .analysis import read_events
from .model import POLICIES


def main():
    p=argparse.ArgumentParser(); p.add_argument("--input",type=Path,default=Path("results/core"))
    p.add_argument("--seed",type=int,default=1000); p.add_argument("--length",type=int,default=5)
    p.add_argument("--output",type=Path,default=Path("results/core/replay.html")); a=p.parse_args()
    data={}
    for policy in POLICIES:
        frames=[]; covered=set(); xy=None; obs=0
        for e in read_events(a.input/"raw"/f"{a.seed}-1-{a.length}-{policy}.jsonl.gz"):
            if e["event"]=="start": config=e["config"]
            elif e["event"]=="observe": covered.add(e["cell"]); obs+=1
            elif e["event"]=="tick": xy=e["xy"]
            elif e["event"]=="session":
                frames.append({"t":e["t"],"xy":xy,"covered":hex(sum(1<<i for i in covered)),
                    "known":[hex(sum(1<<i for i in k)) for k in e["known"]],"queues":e["queues"],"targets":e["targets"],
                    "r":e["r"],"radio":e["radio"],"warning":e["warning"],"coverage":len(covered)/config["width"]/config["height"],
                    "redundant":obs-len(covered),"idle":None})
            elif e["event"]=="stop":
                result=e["result"]
                frames.append({**frames[-1],"t":result["stop_s"],"xy":xy,"covered":hex(sum(1<<i for i in covered)),
                               "coverage":result["coverage"],"redundant":result["redundant"],"complete":result["complete"]})
        data[policy]={"frames":frames,"result":result}
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Two-USV experiment replay</title>
<style>body{margin:0;background:#f4f4ef;color:#172d32;font:16px system-ui,sans-serif}main{max-width:1120px;margin:auto;padding:32px}h1{font-size:32px;margin:6px 0 12px}p{line-height:1.5}.top{font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#54716e}.grid{display:grid;grid-template-columns:3fr 1fr;gap:24px}canvas{background:white;width:100%;border:1px solid #ccd4cd;border-radius:8px}aside{background:white;padding:24px;border-radius:8px}button,select{padding:10px 16px;background:white;border:1px solid #7c9997;border-radius:4px;color:#172d32;font:inherit}button{background:#007c83;color:white;cursor:pointer}input{width:100%;accent-color:#007c83}dt{font-size:12px;color:#54716e;margin-top:20px}dd{font-size:22px;margin:4px 0}.legend{font-size:13px}.controls{display:flex;gap:12px;margin:20px 0}#note{padding:16px;background:#fff3d5;border-radius:6px}a{color:#007c83}@media(max-width:800px){.grid{grid-template-columns:1fr}}</style>
<main><div class="top">II2202 · synthetic experiment · retained raw evidence</div><h1>Two boats, one survey</h1><p>Explore the same pre-generated fade and slowdown scenario under five reservation policies. Cells are observed at arrival at their centres. This is a controlled coverage model, without collision avoidance or calibrated vessel physics.</p>
<div class="controls"><select id="policy" aria-label="Policy"><option>S1</option><option>S2</option><option>S3</option><option selected>S4-T</option><option>S4-P</option></select><button id="play">Play</button><select id="speed" aria-label="Playback speed"><option value="1">1 frame</option><option value="5" selected>5 frames</option><option value="20">20 frames</option></select></div>
<div class="grid"><div><canvas id="map" width="840" height="560"></canvas><input id="time" type="range" min="0" value="0" aria-label="Simulation time"><p class="legend">Pale green: observed by either boat · orange: boat 1 · teal: boat 2 · outlined cells: queued tasks · dashed line: unavailable radio</p></div><aside><div class="top" id="label"></div><dl><dt>Simulation time</dt><dd id="clock"></dd><dt>Observed coverage</dt><dd id="coverage"></dd><dt>Received signal</dt><dd id="signal"></dd><dt>Warning at this session</dt><dd id="warning"></dd><dt>Repeated observations</dt><dd id="redundant"></dd><dt>Queues remaining</dt><dd id="queues"></dd></dl></aside></div>
<p id="note"></p><p>Scenario seed SEED, temporary slowdown, target mean fade duration LENGTH exchanges. Select a policy and move the time slider to inspect the retained trajectory. Final outcomes include timeouts at 7200 s. <a href="https://github.com/ADreLOI/RMSW-Project">Source and reproducibility instructions</a>.</p></main>
<script>const D=DATA,C=CONFIG; const $=id=>document.getElementById(id);let playing=false;const ctx=$('map').getContext('2d');const names={'S1':'Fixed partition','S2':'Reactive, short queue','S3':'Always long queue','S4-T':'Trend warning','S4-P':'Persistence warning'};
function draw(){let p=$('policy').value,run=D[p];$('time').max=run.frames.length-1;let f=run.frames[Math.min(+$('time').value,run.frames.length-1)],covered=BigInt(f.covered),cell=34,ox=75,oy=55;ctx.clearRect(0,0,840,560);ctx.fillStyle='#54716e';ctx.font='14px system-ui';ctx.fillText('400 × 240 m survey · 20 m cells',ox,30);for(let y=0;y<C.height;y++)for(let x=0;x<C.width;x++){let id=y*C.width+x;ctx.fillStyle=covered&(1n<<BigInt(id))?'#dbe9d8':'#fafbf8';ctx.fillRect(ox+x*cell,oy+(C.height-1-y)*cell,cell,cell);ctx.strokeStyle='#d3dbd5';ctx.strokeRect(ox+x*cell,oy+(C.height-1-y)*cell,cell,cell)}let colors=['#c86b35','#007c83'];f.queues.forEach((q,i)=>{ctx.strokeStyle=colors[i];ctx.lineWidth=2;q.forEach(id=>ctx.strokeRect(ox+(id%C.width)*cell+4,oy+(C.height-1-Math.floor(id/C.width))*cell+4,cell-8,cell-8))});let points=f.xy.map(([x,y])=>[ox+x/C.cell_m*cell,oy+(C.height-y/C.cell_m)*cell]);ctx.beginPath();ctx.strokeStyle=f.radio?'#94aaa0':'#ca5038';ctx.setLineDash(f.radio?[]:[8,6]);ctx.moveTo(...points[0]);ctx.lineTo(...points[1]);ctx.stroke();ctx.setLineDash([]);points.forEach(([x,y],i)=>{ctx.beginPath();ctx.fillStyle=colors[i];ctx.arc(x,y,9,0,2*Math.PI);ctx.fill();ctx.fillStyle='white';ctx.font='bold 12px system-ui';ctx.textAlign='center';ctx.fillText(i+1,x,y+4);ctx.textAlign='left'});$('label').textContent=p+' · '+names[p];$('clock').textContent=f.t+' s';$('coverage').textContent=(100*f.coverage).toFixed(1)+'%';$('signal').textContent=f.r.toFixed(1)+' dBm · '+(f.radio?'available':'unavailable');$('warning').textContent=f.warning?'positive':'negative';$('redundant').textContent=f.redundant;$('queues').textContent=f.queues.map(q=>q.length).join(' / ');$('note').textContent=run.result.complete?'Final outcome: full coverage in '+run.result.completion_s+' s. This does not include return or data upload.':'Final outcome: timeout at 7200 s with '+(100*run.result.coverage).toFixed(1)+'% coverage. Empty queues and distance-related disconnection can prevent reconnection; there is no rendezvous controller.'}
$('policy').onchange=()=>{$('time').value=0;draw()};$('time').oninput=draw;$('play').onclick=()=>{playing=!playing;$('play').textContent=playing?'Pause':'Play'};setInterval(()=>{if(playing){$('time').value=Math.min(+$('time').value+ +$('speed').value,+$('time').max);if(+$('time').value===+$('time').max){playing=false;$('play').textContent='Play'}draw()}},80);draw();</script></html>'''
    html=html.replace('DATA',json.dumps(data,separators=(',',':'))).replace('CONFIG',json.dumps(config)).replace('SEED',str(a.seed)).replace('LENGTH',str(a.length))
    a.output.write_text(html,encoding='utf-8')
    print(a.output.resolve())


if __name__=='__main__': main()
