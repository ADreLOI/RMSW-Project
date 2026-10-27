"""Pre-specified outage/alert matching, with explicit boundary exclusions."""
from __future__ import annotations


def outage_events(samples):
    events=[]; start=None
    for i,s in enumerate(samples):
        if not s["radio"] and start is None:
            start=i
        if s["radio"] and start is not None:
            if i-start>=2: events.append((start,i))
            start=None
    # A final episode of at least two misses is observed even if recovery is censored.
    if start is not None and len(samples)-start>=2:
        events.append((start,len(samples)))
    return events


def warning_scores(samples,horizon=3):
    events=outage_events(samples)
    onsets=[a for a,b in events if a>=horizon]
    excluded_onsets=len(events)-len(onsets)
    alerts=[]; active=False; excluded_alerts=0
    for i,s in enumerate(samples):
        if not s["radio"]:
            active=False
            continue
        positive=s.get("warning",False) and s.get("committed",True)
        if positive and not active:
            if i<len(samples)-(horizon+1): alerts.append(i)
            else: excluded_alerts+=1
        active=positive
    available=set(onsets); matched=[]
    for alert in alerts:
        eligible=[onset for onset in sorted(available) if 1<=onset-alert<=horizon]
        if eligible:
            onset=eligible[0]; available.remove(onset)
            matched.append(samples[onset]["t"]-samples[alert]["t"])
    tp=len(matched); fp=len(alerts)-tp; fn=len(available)
    precision=tp/(tp+fp) if tp+fp else None
    recall=tp/(tp+fn) if tp+fn else None
    f1=2*tp/(2*tp+fp+fn) if onsets else None
    return {"true_positives":tp,"false_positives":fp,"false_negatives":fn,
            "eligible_outages":len(onsets),"alerts":len(alerts),"precision":precision,
            "recall":recall,"f1":f1,"lead_s":matched,"excluded_onsets":excluded_onsets,
            "excluded_alerts":excluded_alerts,"outage_lengths":[b-a for a,b in events]}
