from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from math import log
from statistics import mean, pstdev
from typing import Iterable

from .models import Trade
from .research import ResearchCandle
from .trajectory import DEFAULT_SAMPLE_POINTS, analyze_trajectory_families

TRANSITION_MODEL_VERSION = "0.9.0"


def _entropy(counter: Counter[str]) -> float:
    total=sum(counter.values()); kinds=len(counter)
    if total<=0 or kinds<=1:return 0.0
    value=-sum((n/total)*log(n/total) for n in counter.values() if n)
    return value/log(kinds)


def _daypart(start: datetime)->str:
    if start.hour<11:return "MANHA_INICIAL"
    if start.hour<14:return "MEIO_DO_DIA"
    if start.hour<17:return "TARDE"
    return "FECHAMENTO"


def _transition_rows(rows:list[dict[str,object]],key:str,interval_seconds:int):
    by_session=defaultdict(list)
    for row in rows:
        start=datetime.fromisoformat(str(row["start"]))
        by_session[start.date().isoformat()].append(row)
    transitions=Counter(); triplets=Counter()
    for session_rows in by_session.values():
        session_rows.sort(key=lambda x:str(x["start"]))
        pairs=[]
        for left,right in zip(session_rows,session_rows[1:]):
            a=datetime.fromisoformat(str(left["start"])); b=datetime.fromisoformat(str(right["start"]))
            if abs((b-a).total_seconds()-interval_seconds)<=1e-6:
                pairs.append((left,right)); transitions[(str(left[key]),str(right[key]))]+=1
        for first,second in zip(pairs,pairs[1:]):
            a,b=first; b2,c=second
            if str(b["start"])==str(b2["start"]):
                triplets[(str(a[key]),str(b[key]),str(c[key]))]+=1
    outgoing=Counter()
    for (source,_),count in transitions.items():outgoing[source]+=count
    rows_out=[{"from":s,"to":t,"count":n,"probability":round(n/outgoing[s],4) if outgoing[s] else 0.0}
              for (s,t),n in transitions.items()]
    rows_out.sort(key=lambda x:(-int(x["count"]),str(x["from"]),str(x["to"])))
    motifs=[{"sequence":list(seq),"count":n} for seq,n in triplets.most_common(12)]
    return rows_out,motifs


def _stability(assignments:list[dict[str,object]],features_by_start:dict[datetime,ResearchCandle])->list[dict[str,object]]:
    sessions_all={datetime.fromisoformat(str(r["start"])).date().isoformat() for r in assignments}
    by_family=defaultdict(list)
    for row in assignments:by_family[str(row["rule_family"])].append(row)
    result=[]
    for family,rows in by_family.items():
        sessions=Counter(); hours=Counter(); dayparts=Counter(); months=Counter()
        volatility=Counter(); contexts=Counter(); final_regimes=Counter()
        for row in rows:
            start=datetime.fromisoformat(str(row["start"])); session=start.date().isoformat()
            sessions[session]+=1; hours[f"{start.hour:02d}h"]+=1; dayparts[_daypart(start)]+=1; months[start.strftime("%Y-%m")]+=1
            feature=features_by_start.get(start)
            if feature:
                volatility[feature.volatility_bucket]+=1; contexts[feature.regime_medium]+=1; final_regimes[feature.session_regime]+=1
        prevalence=len(sessions)/max(len(sessions_all),1)
        per_session=[]
        for session in sessions_all:
            total=sum(1 for r in assignments if datetime.fromisoformat(str(r["start"])).date().isoformat()==session)
            per_session.append(sessions.get(session,0)/max(total,1))
        avg=mean(per_session) if per_session else 0.0
        std=pstdev(per_session) if len(per_session)>1 else 0.0
        consistency=max(0.0,1.0-min(std/max(avg,.05),1.0))
        spread=mean([_entropy(dayparts),_entropy(volatility) if volatility else 0.0,_entropy(contexts) if contexts else 0.0])
        score=round(100*(.45*prevalence+.35*consistency+.20*spread),1)
        if len(rows)<5:label="AMOSTRA_PEQUENA"
        elif score>=70:label="DISTRIBUIDA"
        elif score>=45:label="MODERADA"
        else:label="CONCENTRADA"
        result.append({"family":family,"count":len(rows),"share":round(len(rows)/max(len(assignments),1),4),
            "sessions":len(sessions),"session_prevalence":round(prevalence,4),"mean_session_share":round(avg,4),
            "session_share_std":round(std,4),"consistency":round(consistency,4),"context_spread":round(spread,4),
            "stability_score":score,"stability_label":label,"hour_distribution":dict(sorted(hours.items())),
            "daypart_distribution":dict(sorted(dayparts.items())),"month_distribution":dict(sorted(months.items())),
            "volatility_distribution":dict(sorted(volatility.items())),"context_regime_distribution":dict(sorted(contexts.items())),
            "session_regime_distribution":dict(sorted(final_regimes.items()))})
    result.sort(key=lambda r:(-float(r["stability_score"]),-int(r["count"]),str(r["family"])))
    return result


def analyze_stability_and_transitions(trades: Iterable[Trade], *, interval_seconds:int,
    research_features:Iterable[ResearchCandle]|None=None, quality_only:bool=True, clusters:int|None=None,
    sample_points:int=DEFAULT_SAMPLE_POINTS,target_start:datetime|None=None)->dict[str,object]:
    trades=list(trades); features=list(research_features or [])
    trajectory=analyze_trajectory_families(trades,interval_seconds=interval_seconds,research_features=features,
        quality_only=quality_only,clusters=clusters,sample_points=sample_points)
    assignments=list(trajectory.get("assignments") or [])
    family_transitions,family_motifs=_transition_rows(assignments,"rule_family",interval_seconds)
    cluster_transitions,cluster_motifs=_transition_rows(assignments,"cluster_label",interval_seconds)
    selected=None
    if target_start is not None:
        ordered=sorted(assignments,key=lambda r:str(r["start"])); target_iso=target_start.isoformat()
        for i,row in enumerate(ordered):
            if str(row["start"])!=target_iso:continue
            current=datetime.fromisoformat(str(row["start"])); previous=ordered[i-1] if i>0 else None; following=ordered[i+1] if i+1<len(ordered) else None
            if previous:
                p=datetime.fromisoformat(str(previous["start"]))
                if p.date()!=current.date() or (current-p).total_seconds()!=interval_seconds:previous=None
            if following:
                n=datetime.fromisoformat(str(following["start"]))
                if n.date()!=current.date() or (n-current).total_seconds()!=interval_seconds:following=None
            selected={"previous":previous,"current":row,"next":following}; break
    return {"model_version":TRANSITION_MODEL_VERSION,"trajectory_model_version":trajectory.get("model_version"),
        "method":"v0.9: estabilidade descritiva por contexto + transições observadas entre candles consecutivos",
        "interval_seconds":interval_seconds,"quality_only":quality_only,"candles":trajectory.get("candles",0),
        "eligible_candles":trajectory.get("eligible_candles",0),"excluded_low_quality":trajectory.get("excluded_low_quality",0),
        "cluster_count":trajectory.get("cluster_count",0),
        "stability":_stability(assignments,{f.candle.start:f for f in features}),
        "family_transitions":family_transitions,"family_motifs":family_motifs,
        "cluster_transitions":cluster_transitions,"cluster_motifs":cluster_motifs,
        "selected_sequence":selected,
        "note":"Transições e escores de estabilidade são descritivos do histórico carregado. Probabilidade de transição é frequência condicional observada, não previsão de mercado."}
