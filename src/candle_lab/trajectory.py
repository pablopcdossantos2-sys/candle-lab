from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from typing import Iterable

from .candles import build_candles, group_trades_by_candle, trade_sort_key
from .metrics import candle_dna
from .models import Trade
from .research import ResearchCandle

TRAJECTORY_MODEL_VERSION = "0.8.0"
DEFAULT_SAMPLE_POINTS = 25


@dataclass(frozen=True, slots=True)
class TrajectorySignature:
    symbol: str
    start: datetime
    interval_seconds: int
    path: tuple[float, ...]
    vector: tuple[float, ...]
    rule_family: str
    rule_confidence: float


def _interp(points: list[tuple[float,float]], x: float) -> float:
    if x <= points[0][0]: return points[0][1]
    if x >= points[-1][0]: return points[-1][1]
    for (x0,y0),(x1,y1) in zip(points,points[1:]):
        if x0 <= x <= x1:
            if x1 == x0: return y1
            w=(x-x0)/(x1-x0)
            return y0+(y1-y0)*w
    return points[-1][1]


def resample_trajectory(trades: Iterable[Trade], *, start: datetime, interval_seconds: int, points: int=DEFAULT_SAMPLE_POINTS) -> list[float]:
    ordered=sorted(trades,key=trade_sort_key)
    if not ordered: return []
    if points < 3: raise ValueError("points deve ser >= 3")
    prices=[t.price_ticks for t in ordered]
    low,high=min(prices),max(prices); span=high-low
    timeline=[]
    for t in ordered:
        x=min(1.0,max(0.0,(t.ts-start).total_seconds()/interval_seconds if interval_seconds else 0.0))
        y=(t.price_ticks-low)/span if span else 0.5
        timeline.append((x,y))
    # mantém o último preço para timestamps duplicados
    compact=[]
    for x,y in timeline:
        if compact and x==compact[-1][0]: compact[-1]=(x,y)
        else: compact.append((x,y))
    return [_interp(compact,i/(points-1)) for i in range(points)]


def classify_rule_family(trades: Iterable[Trade], interval_seconds: int) -> tuple[str,float]:
    ordered=sorted(trades,key=trade_sort_key)
    if not ordered: return "UNCLASSIFIED",0.0
    prices=[t.price_ticks for t in ordered]
    o,c=prices[0],prices[-1]; hi,lo=max(prices),min(prices); rng=hi-lo
    if rng == 0: return "FLAT",1.0
    net=c-o
    dna=candle_dna(ordered,interval_seconds=interval_seconds)
    low_i=prices.index(lo); high_i=prices.index(hi)
    up_exc=hi-o; down_exc=o-lo
    # varredura exige excursão real além da abertura antes da reversão
    if lo < o and low_i < high_i and c > o and (c-lo)/rng >= .65:
        return "SWEEP_LOW_REVERSAL", min(1.0,.55+.35*(c-lo)/rng)
    if hi > o and high_i < low_i and c < o and (hi-c)/rng >= .65:
        return "SWEEP_HIGH_REVERSAL", min(1.0,.55+.35*(hi-c)/rng)
    if net > 0 and dna.directional_efficiency >= .55 and c >= hi-0.15*rng:
        return "DIRECT_IMPULSE_UP", min(1.0,.55+.45*dna.directional_efficiency)
    if net < 0 and dna.directional_efficiency >= .55 and c <= lo+0.15*rng:
        return "DIRECT_IMPULSE_DOWN", min(1.0,.55+.45*dna.directional_efficiency)
    mid=len(prices)//2
    first_half=prices[:mid+1]; second_half=prices[mid:]
    if min(first_half) <= lo+0.15*rng and c >= o and high_i > low_i:
        return "V_SHAPED", .65
    if max(first_half) >= hi-0.15*rng and c <= o and low_i > high_i:
        return "INVERTED_V", .65
    if hi > o and lo < o and dna.reversal_rate >= .25:
        return "DOUBLE_EXCURSION", min(1.0,.55+dna.reversal_rate/2)
    if net > 0 and down_exc > 0 and c > o:
        return "PULLBACK_CONTINUATION_UP", .58
    if net < 0 and up_exc > 0 and c < o:
        return "PULLBACK_CONTINUATION_DOWN", .58
    if dna.reversal_rate >= .20 or dna.directional_efficiency <= .25:
        return "OSCILLATING_RANGE", min(1.0,.55+(1-dna.directional_efficiency)*.3)
    return "UNCLASSIFIED", .35


def build_signature(trades: Iterable[Trade], interval_seconds: int, sample_points: int=DEFAULT_SAMPLE_POINTS) -> TrajectorySignature:
    ordered=sorted(trades,key=trade_sort_key)
    if not ordered: raise ValueError("Candle sem negócios")
    start=ordered[0].ts.replace(second=(ordered[0].ts.second//interval_seconds)*interval_seconds if interval_seconds<60 else 0,microsecond=0)
    if interval_seconds >= 60:
        from .candles import floor_time
        start=floor_time(ordered[0].ts,interval_seconds)
    path=tuple(resample_trajectory(ordered,start=start,interval_seconds=interval_seconds,points=sample_points))
    family,confidence=classify_rule_family(ordered,interval_seconds)
    dna=candle_dna(ordered,interval_seconds=interval_seconds)
    vector=path+(
        dna.directional_efficiency,
        dna.range_efficiency,
        min(dna.reversal_rate,1.0),
        min(dna.revisit_rate,1.0),
        min(dna.time_to_high_ms/(interval_seconds*1000),1.0),
        min(dna.time_to_low_ms/(interval_seconds*1000),1.0),
    )
    return TrajectorySignature(ordered[0].symbol,start,interval_seconds,path,vector,family,confidence)


def _dist(a: tuple[float,...],b: tuple[float,...])->float:
    return sqrt(sum((x-y)**2 for x,y in zip(a,b))/max(len(a),1))


def deterministic_kmeans(vectors: list[tuple[float,...]], k: int, max_iter: int=80) -> tuple[list[int],list[tuple[float,...]]]:
    if not vectors: return [],[]
    k=max(1,min(k,len(vectors)))
    # inicialização determinística por pontos bem separados
    centroids=[vectors[0]]
    while len(centroids)<k:
        candidate=max(vectors,key=lambda v:min(_dist(v,c) for c in centroids))
        centroids.append(candidate)
    assignments=[0]*len(vectors)
    for _ in range(max_iter):
        new=[min(range(k),key=lambda j:(_dist(v,centroids[j]),j)) for v in vectors]
        groups=[[] for _ in range(k)]
        for idx,v in zip(new,vectors): groups[idx].append(v)
        next_centroids=[]
        for j,group in enumerate(groups):
            if group:
                next_centroids.append(tuple(sum(v[d] for v in group)/len(group) for d in range(len(vectors[0]))))
            else: next_centroids.append(centroids[j])
        if new==assignments and next_centroids==centroids: break
        assignments,centroids=new,next_centroids
    # normaliza IDs pelo centróide para resultados reprodutíveis
    order=sorted(range(k),key=lambda j:centroids[j])
    remap={old:new for new,old in enumerate(order)}
    return [remap[a] for a in assignments],[centroids[old] for old in order]


def cluster_signatures(signatures: list[TrajectorySignature], clusters: int|None=None) -> dict[str,object]:
    if not signatures:
        return {"cluster_count":0,"clusters":[],"assignments":[]}
    k=clusters or max(2,min(8,round(len(signatures)**0.5)))
    k=max(1,min(k,len(signatures)))
    assignments,centroids=deterministic_kmeans([s.vector for s in signatures],k)
    rows=[]; cluster_rows=[]
    for idx,(sig,cluster_id) in enumerate(zip(signatures,assignments)):
        distance=_dist(sig.vector,centroids[cluster_id])
        rows.append({"start":sig.start.isoformat(),"symbol":sig.symbol,"cluster_id":cluster_id+1,
                     "cluster_label":f"FAMÍLIA EMPÍRICA {cluster_id+1}","distance":round(distance,6),
                     "rule_family":sig.rule_family,"rule_confidence":round(sig.rule_confidence,4)})
    for cid in range(k):
        members=[(i,s) for i,s in enumerate(signatures) if assignments[i]==cid]
        medoid_i=min(members,key=lambda x:_dist(x[1].vector,centroids[cid]))[0]
        rules=Counter(s.rule_family for _,s in members)
        dominant,count=rules.most_common(1)[0]
        cluster_rows.append({"cluster_id":cid+1,"label":f"Família empírica {cid+1}","size":len(members),
            "mean_path":[round(v,4) for v in centroids[cid][:len(signatures[0].path)]],
            "medoid_start":signatures[medoid_i].start.isoformat(),"cohesion":round(sum(_dist(s.vector,centroids[cid]) for _,s in members)/len(members),6),
            "dominant_rule":dominant,"dominance":round(count/len(members),4),"rule_distribution":dict(rules)})
    return {"cluster_count":k,"clusters":cluster_rows,"assignments":rows}


def analyze_trajectory_families(trades: Iterable[Trade], *, interval_seconds: int, research_features: Iterable[ResearchCandle]|None=None,
    quality_only: bool=True, clusters: int|None=None, sample_points: int=DEFAULT_SAMPLE_POINTS) -> dict[str,object]:
    trades=list(trades)
    grouped=group_trades_by_candle(trades,interval_seconds)
    features={f.candle.start:f for f in (research_features or [])}
    signatures=[]; excluded=0
    for key in sorted(grouped,key=lambda k:k[1]):
        bucket=grouped[key]; start=key[1]
        feature=features.get(start)
        if quality_only and feature is not None and not feature.session_eligible:
            excluded+=1; continue
        signatures.append(build_signature(bucket,interval_seconds,sample_points))
    clustering=cluster_signatures(signatures,clusters)
    rules=Counter(s.rule_family for s in signatures)
    total=len(signatures)
    rule_rows=[{"family":fam,"count":count,"share":round(count/total,4) if total else 0.0} for fam,count in rules.most_common()]
    result={"model_version":TRAJECTORY_MODEL_VERSION,"method":"taxonomia interpretável + k-means determinístico em trajetórias normalizadas",
        "candles":len(grouped),"eligible_candles":total,"excluded_low_quality":excluded,"quality_only":quality_only,
        "sample_points":sample_points,"rule_families":rule_rows,**clustering}
    return result
