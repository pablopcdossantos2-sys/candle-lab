from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from math import log
from statistics import median
from typing import Iterable

from .candles import build_candles, group_trades_by_candle
from .metrics import CandleDNA, candle_dna
from .models import Candle, Trade
from .quality import SessionQuality, assess_session_quality

RESEARCH_INDEX_VERSION = "0.7.0"


@dataclass(frozen=True, slots=True)
class ResearchCandle:
    candle: Candle
    dna: CandleDNA
    direction: str
    body_share: float
    upper_wick_share: float
    lower_wick_share: float
    volatility_ratio: float
    volatility_bucket: str
    session_regime: str
    session_directional_efficiency: float
    session_net_to_range: float
    regime_short: str
    regime_medium: str
    regime_to_date: str
    opening_gap_ticks: int | None
    opening_gap_ratio: float | None
    opening_gap_bucket: str
    session_quality: SessionQuality

    @property
    def session_date(self):
        return self.candle.start.date()

    @property
    def minute_of_day(self) -> int:
        return self.candle.start.hour * 60 + self.candle.start.minute

    @property
    def session_eligible(self) -> bool:
        return self.session_quality.eligible_for_research

    def to_record(self) -> dict[str, object]:
        return {
            "symbol": self.candle.symbol, "session_date": self.session_date.isoformat(),
            "start": self.candle.start.isoformat(), "end": self.candle.end.isoformat(),
            "interval_seconds": self.candle.interval_seconds, "open_ticks": self.candle.open_ticks,
            "high_ticks": self.candle.high_ticks, "low_ticks": self.candle.low_ticks,
            "close_ticks": self.candle.close_ticks, "volume": self.candle.volume, "trades": self.candle.trades,
            "direction": self.direction, "body_share": self.body_share, "upper_wick_share": self.upper_wick_share,
            "lower_wick_share": self.lower_wick_share, "volatility_ratio": self.volatility_ratio,
            "volatility_bucket": self.volatility_bucket, "session_regime": self.session_regime,
            "session_directional_efficiency": self.session_directional_efficiency,
            "session_net_to_range": self.session_net_to_range, "regime_short": self.regime_short,
            "regime_medium": self.regime_medium, "regime_to_date": self.regime_to_date,
            "opening_gap_ticks": self.opening_gap_ticks, "opening_gap_ratio": self.opening_gap_ratio,
            "opening_gap_bucket": self.opening_gap_bucket, "session_quality": self.session_quality.to_record(),
            "minute_of_day": self.minute_of_day, "dna": asdict(self.dna),
        }

    @classmethod
    def from_record(cls, record: dict[str, object]) -> "ResearchCandle":
        candle = Candle(
            symbol=str(record["symbol"]), start=datetime.fromisoformat(str(record["start"])),
            end=datetime.fromisoformat(str(record["end"])), interval_seconds=int(record["interval_seconds"]),
            open_ticks=int(record["open_ticks"]), high_ticks=int(record["high_ticks"]),
            low_ticks=int(record["low_ticks"]), close_ticks=int(record["close_ticks"]),
            volume=int(record["volume"]), trades=int(record["trades"]),
        )
        dna = CandleDNA(**dict(record["dna"]))
        quality_payload = dict(record.get("session_quality") or {})
        if not quality_payload:
            quality_payload = {
                "symbol": candle.symbol, "session_date": candle.start.date().isoformat(),
                "schedule_id": None, "schedule_label": None, "expected_start": None, "expected_end": None,
                "observed_first": candle.start.isoformat(), "observed_last": candle.end.isoformat(),
                "expected_duration_seconds": None, "observed_span_seconds": 0.0, "coverage_ratio": None,
                "active_minute_ratio": None, "start_delay_seconds": None, "end_early_seconds": None,
                "gap_threshold_seconds": 60.0, "gap_count": 0, "max_gap_seconds": 0.0,
                "p95_intertrade_seconds": 0.0, "status": "UNKNOWN_SCHEDULE", "score": 0.0,
                "eligible_for_research": False, "warnings": ["Índice legado sem avaliação de qualidade."], "largest_gaps": [],
            }
        return cls(
            candle=candle, dna=dna, direction=str(record["direction"]), body_share=float(record["body_share"]),
            upper_wick_share=float(record["upper_wick_share"]), lower_wick_share=float(record["lower_wick_share"]),
            volatility_ratio=float(record["volatility_ratio"]), volatility_bucket=str(record["volatility_bucket"]),
            session_regime=str(record["session_regime"]), session_directional_efficiency=float(record["session_directional_efficiency"]),
            session_net_to_range=float(record["session_net_to_range"]), regime_short=str(record.get("regime_short") or record["session_regime"]),
            regime_medium=str(record.get("regime_medium") or record["session_regime"]), regime_to_date=str(record.get("regime_to_date") or record["session_regime"]),
            opening_gap_ticks=int(record["opening_gap_ticks"]) if record.get("opening_gap_ticks") is not None else None,
            opening_gap_ratio=float(record["opening_gap_ratio"]) if record.get("opening_gap_ratio") is not None else None,
            opening_gap_bucket=str(record.get("opening_gap_bucket") or "UNKNOWN"),
            session_quality=SessionQuality.from_record(quality_payload),
        )


def _shape(candle: Candle) -> tuple[str, float, float, float]:
    candle_range = candle.high_ticks - candle.low_ticks
    body = candle.close_ticks - candle.open_ticks
    if candle_range <= 0:
        return "DOJI", 0.0, 0.0, 0.0
    direction = "BULLISH" if body > 0 else "BEARISH" if body < 0 else "DOJI"
    body_share = abs(body) / candle_range
    upper_wick = candle.high_ticks - max(candle.open_ticks, candle.close_ticks)
    lower_wick = min(candle.open_ticks, candle.close_ticks) - candle.low_ticks
    return direction, body_share, upper_wick / candle_range, lower_wick / candle_range


def _session_regime(candles: list[Candle]) -> tuple[str, float, float]:
    if not candles:
        return "UNKNOWN", 0.0, 0.0
    first, last = candles[0], candles[-1]
    session_high = max(c.high_ticks for c in candles)
    session_low = min(c.low_ticks for c in candles)
    session_range = session_high - session_low
    net = last.close_ticks - first.open_ticks
    path = 0
    previous = first.open_ticks
    for candle in candles:
        path += abs(candle.close_ticks - previous)
        previous = candle.close_ticks
    directional_efficiency = abs(net) / path if path else 0.0
    net_to_range = abs(net) / session_range if session_range else 0.0
    if session_range == 0:
        regime = "RANGE"
    elif net_to_range >= 0.55 and directional_efficiency >= 0.25:
        regime = "TREND_UP" if net > 0 else "TREND_DOWN"
    elif net_to_range <= 0.28 or directional_efficiency <= 0.12:
        regime = "RANGE"
    else:
        regime = "MIXED"
    return regime, directional_efficiency, net_to_range


def _volatility_bucket(ratio: float) -> str:
    if ratio < 0.65: return "LOW"
    if ratio < 1.35: return "NORMAL"
    if ratio < 2.25: return "HIGH"
    return "EXTREME"


def _opening_gap_bucket(gap_ticks: int | None, ratio: float | None) -> str:
    if gap_ticks is None or ratio is None: return "NO_PREVIOUS_SESSION"
    absolute = abs(ratio)
    if absolute < 0.10: magnitude = "NONE"
    elif absolute < 0.25: magnitude = "SMALL"
    elif absolute < 0.50: magnitude = "MEDIUM"
    else: magnitude = "LARGE"
    if magnitude == "NONE" or gap_ticks == 0: return "NONE"
    return f"{magnitude}_{'UP' if gap_ticks > 0 else 'DOWN'}"


def build_research_index(trades: Iterable[Trade], interval_seconds: int) -> list[ResearchCandle]:
    trades = list(trades)
    if not trades: return []
    by_session: dict[tuple[str, object], list[Trade]] = {}
    for trade in trades:
        by_session.setdefault((trade.symbol, trade.ts.date()), []).append(trade)
    sessions=[]
    for (symbol, session_date), session_trades in sorted(by_session.items(), key=lambda item: item[0]):
        grouped=group_trades_by_candle(session_trades, interval_seconds)
        candles=[]; buckets=[]
        for key in sorted(grouped,key=lambda k:k[1]):
            bucket=grouped[key]
            candles.append(build_candles(bucket, interval_seconds)[0]); buckets.append(bucket)
        sessions.append({"symbol":symbol,"session_date":session_date,"trades":session_trades,"candles":candles,"buckets":buckets,"quality":assess_session_quality(session_trades)})
    result=[]; previous_by_symbol={}
    for session in sessions:
        symbol=str(session["symbol"]); candles=list(session["candles"]); buckets=list(session["buckets"]); quality=session["quality"]
        assert isinstance(quality, SessionQuality)
        if not candles: continue
        regime,session_eff,net_to_range=_session_regime(candles)
        nonzero_ranges=[c.high_ticks-c.low_ticks for c in candles if c.high_ticks>c.low_ticks]
        median_range=median(nonzero_ranges) if nonzero_ranges else 0.0
        previous_candles=previous_by_symbol.get(symbol)
        if previous_candles:
            previous_close=previous_candles[-1].close_ticks
            previous_range=max(c.high_ticks for c in previous_candles)-min(c.low_ticks for c in previous_candles)
            gap_ticks=candles[0].open_ticks-previous_close
            gap_ratio=gap_ticks/previous_range if previous_range else (0.0 if gap_ticks==0 else None)
        else: gap_ticks=None; gap_ratio=None
        gap_bucket=_opening_gap_bucket(gap_ticks,gap_ratio)
        for index,(candle,bucket) in enumerate(zip(candles,buckets)):
            direction,body_share,upper_wick_share,lower_wick_share=_shape(candle)
            candle_range=candle.high_ticks-candle.low_ticks
            volatility_ratio=candle_range/median_range if median_range else (1.0 if candle_range==0 else 99.0)
            result.append(ResearchCandle(
                candle=candle,dna=candle_dna(bucket,interval_seconds=interval_seconds),direction=direction,
                body_share=body_share,upper_wick_share=upper_wick_share,lower_wick_share=lower_wick_share,
                volatility_ratio=volatility_ratio,volatility_bucket=_volatility_bucket(volatility_ratio),
                session_regime=regime,session_directional_efficiency=session_eff,session_net_to_range=net_to_range,
                regime_short=_session_regime(candles[max(0,index-4):index+1])[0],
                regime_medium=_session_regime(candles[max(0,index-14):index+1])[0],
                regime_to_date=_session_regime(candles[:index+1])[0],opening_gap_ticks=gap_ticks,
                opening_gap_ratio=gap_ratio,opening_gap_bucket=gap_bucket,session_quality=quality))
        previous_by_symbol[symbol]=candles
    return result


def _ratio_distance(a: float, b: float) -> float:
    return min(abs(log((max(a,0.0)+1.0)/(max(b,0.0)+1.0)))/2.0,1.0)


def visual_distance(target: ResearchCandle, candidate: ResearchCandle) -> tuple[float, dict[str,float]]:
    direction_penalty=0.0 if target.direction==candidate.direction else (0.45 if "DOJI" in {target.direction,candidate.direction} else 1.0)
    parts={"direcao":(direction_penalty,1.3),"corpo":(abs(target.body_share-candidate.body_share),1.35),
           "pavio_superior":(abs(target.upper_wick_share-candidate.upper_wick_share),1.0),
           "pavio_inferior":(abs(target.lower_wick_share-candidate.lower_wick_share),1.0),
           "fechamento_no_range":(abs(target.dna.close_location-candidate.dna.close_location),0.55),
           "amplitude":(_ratio_distance(target.dna.range_ticks,candidate.dna.range_ticks),0.25)}
    weighted=sum(v*w for v,w in parts.values()); total=sum(w for _,w in parts.values())
    return weighted/total if total else 1.0,{name:round(value,4) for name,(value,_) in parts.items()}


def dna_distance(target: ResearchCandle, candidate: ResearchCandle) -> tuple[float, dict[str,float]]:
    t,c=target.dna,candidate.dna
    parts={"eficiencia_direcional":(abs(t.directional_efficiency-c.directional_efficiency),1.15),
           "eficiencia_range":(abs(t.range_efficiency-c.range_efficiency),0.95),
           "reversoes":(abs(t.reversal_rate-c.reversal_rate),0.9),"revisitas":(min(abs(t.revisit_rate-c.revisit_rate),1.0),0.8),
           "ordem_extremos":(0.0 if t.high_first==c.high_first else 1.0,0.65),
           "volume_superior":(abs(t.upper_third_volume_share-c.upper_third_volume_share),0.45),
           "volume_inferior":(abs(t.lower_third_volume_share-c.lower_third_volume_share),0.45),
           "distancia_percorrida":(_ratio_distance(t.path_distance_ticks,c.path_distance_ticks),0.55),
           "numero_negocios":(_ratio_distance(target.candle.trades,candidate.candle.trades),0.45),
           "volume":(_ratio_distance(target.candle.volume,candidate.candle.volume),0.35),
           "velocidade":(_ratio_distance(t.trades_per_second,c.trades_per_second),0.5)}
    if t.aggression_imbalance is not None and c.aggression_imbalance is not None:
        parts["agressao"]=(abs(t.aggression_imbalance-c.aggression_imbalance)/2.0,0.7)
    weighted=sum(v*w for v,w in parts.values()); total=sum(w for _,w in parts.values())
    return weighted/total if total else 1.0,{name:round(value,4) for name,(value,_) in parts.items()}


def _clock_distance_minutes(a: ResearchCandle,b: ResearchCandle)->int:
    return abs(a.minute_of_day-b.minute_of_day)


def _compact_feature(feature: ResearchCandle)->dict[str,object]:
    candle=feature.candle; quality=feature.session_quality
    return {"symbol":candle.symbol,"start":candle.start.isoformat(),"end":candle.end.isoformat(),"session_date":candle.start.date().isoformat(),
            "interval_seconds":candle.interval_seconds,"open_ticks":candle.open_ticks,"high_ticks":candle.high_ticks,
            "low_ticks":candle.low_ticks,"close_ticks":candle.close_ticks,"volume":candle.volume,"trades":candle.trades,
            "direction":feature.direction,"body_share":feature.body_share,"upper_wick_share":feature.upper_wick_share,
            "lower_wick_share":feature.lower_wick_share,"volatility_ratio":feature.volatility_ratio,"volatility_bucket":feature.volatility_bucket,
            "session_regime":feature.session_regime,"session_directional_efficiency":feature.session_directional_efficiency,
            "session_net_to_range":feature.session_net_to_range,"regime_short":feature.regime_short,"regime_medium":feature.regime_medium,
            "regime_to_date":feature.regime_to_date,"opening_gap_ticks":feature.opening_gap_ticks,"opening_gap_ratio":feature.opening_gap_ratio,
            "opening_gap_bucket":feature.opening_gap_bucket,"session_quality":{"status":quality.status,"score":quality.score,
            "coverage_ratio":quality.coverage_ratio,"active_minute_ratio":quality.active_minute_ratio,"gap_count":quality.gap_count,
            "max_gap_seconds":quality.max_gap_seconds,"eligible_for_research":quality.eligible_for_research,"schedule_id":quality.schedule_id},
            "minute_of_day":feature.minute_of_day,"dna":{"range_ticks":feature.dna.range_ticks,
            "directional_efficiency":feature.dna.directional_efficiency,"range_efficiency":feature.dna.range_efficiency,
            "reversal_rate":feature.dna.reversal_rate,"revisit_rate":feature.dna.revisit_rate,"high_first":feature.dna.high_first,
            "aggression_imbalance":feature.dna.aggression_imbalance,"trades_per_second":feature.dna.trades_per_second}}


def research_matches(features: Iterable[ResearchCandle], *, target_start: datetime, limit:int=8, same_time:bool=False,
    time_tolerance_minutes:int=20,same_volatility:bool=False,same_regime:bool=False,same_context_regime:bool=False,
    quality_only:bool=False,other_sessions_only:bool=True)->dict[str,object]:
    features=list(features); target=next((f for f in features if f.candle.start==target_start),None)
    if target is None: raise ValueError("Candle-alvo não encontrado no índice de pesquisa")
    candidates=[]; excluded_low_quality=0
    for candidate in features:
        if candidate.candle.start==target.candle.start: continue
        if other_sessions_only and candidate.session_date==target.session_date: continue
        if quality_only and not candidate.session_eligible: excluded_low_quality+=1; continue
        if same_time and _clock_distance_minutes(target,candidate)>time_tolerance_minutes: continue
        if same_volatility and candidate.volatility_bucket!=target.volatility_bucket: continue
        if same_regime and candidate.session_regime!=target.session_regime: continue
        if same_context_regime and candidate.regime_medium!=target.regime_medium: continue
        candidates.append(candidate)
    def ranked(distance_fn):
        rows=[]
        for candidate in candidates:
            distance,components=distance_fn(target,candidate)
            rows.append({"score":round(max(0.0,min(100.0,(1.0-distance)*100.0)),1),"feature":_compact_feature(candidate),
                         "distance_components":components,"clock_distance_minutes":_clock_distance_minutes(target,candidate)})
        rows.sort(key=lambda row:(-float(row["score"]),str(row["feature"]["start"])))
        return rows[:max(1,min(limit,50))]
    target_warning=None
    if not target.session_eligible:
        target_warning="O pregão do candle-alvo não é elegível pela política de qualidade v0.7. Os resultados podem ser úteis para inspeção, mas não devem ser tratados como amostra íntegra."
    return {"method":"pesquisa comparativa v0.7 — heurística explicável, com controle de qualidade e contexto multiescala",
            "target":_compact_feature(target),"target_quality_warning":target_warning,
            "filters":{"same_time":same_time,"time_tolerance_minutes":time_tolerance_minutes,"same_volatility":same_volatility,
            "same_regime":same_regime,"same_context_regime":same_context_regime,"quality_only":quality_only,"other_sessions_only":other_sessions_only},
            "library_candles":len(features),"candidates_considered":len(candidates),"excluded_low_quality":excluded_low_quality,
            "visual_matches":ranked(visual_distance),"dna_matches":ranked(dna_distance)}


def normalized_intrabar_path(trades: Iterable[Trade], start: datetime, interval_seconds:int)->list[dict[str,float]]:
    trades=sorted(trades,key=lambda t:(t.ts,t.sequence_no or 0,t.trade_id or ""))
    if not trades:return []
    prices=[t.price_ticks for t in trades]; low=min(prices); high=max(prices); span=high-low; open_ticks=prices[0]
    result=[]
    for trade in trades:
        elapsed=(trade.ts-start).total_seconds()
        time_fraction=min(1.0,max(0.0,elapsed/interval_seconds)) if interval_seconds else 0.0
        result.append({"time_fraction":time_fraction,"price_from_open_ticks":float(trade.price_ticks-open_ticks),
                       "range_position":(trade.price_ticks-low)/span if span else 0.5})
    return result


def intrabar_comparison_payload(target_trades: Iterable[Trade],candidate_trades:Iterable[Trade],*,interval_seconds:int,tick_size:float,
    target_feature:ResearchCandle|None=None,candidate_feature:ResearchCandle|None=None)->dict[str,object]:
    target_trades=list(target_trades); candidate_trades=list(candidate_trades)
    if not target_trades or not candidate_trades: raise ValueError("Os dois candles precisam possuir negócios para comparação")
    target_candle=build_candles(target_trades,interval_seconds)[0]; candidate_candle=build_candles(candidate_trades,interval_seconds)[0]
    target_feature=target_feature or build_research_index(target_trades,interval_seconds)[0]
    candidate_feature=candidate_feature or build_research_index(candidate_trades,interval_seconds)[0]
    visual_dist,visual_parts=visual_distance(target_feature,candidate_feature); dna_dist,dna_parts=dna_distance(target_feature,candidate_feature)
    def candle_payload(feature):
        candle=feature.candle
        return {**_compact_feature(feature),"open":round(candle.open_ticks*tick_size,10),"high":round(candle.high_ticks*tick_size,10),
                "low":round(candle.low_ticks*tick_size,10),"close":round(candle.close_ticks*tick_size,10)}
    return {"target":candle_payload(target_feature),"candidate":candle_payload(candidate_feature),
            "scores":{"visual":round((1.0-visual_dist)*100.0,1),"dna":round((1.0-dna_dist)*100.0,1)},
            "visual_distance_components":visual_parts,"dna_distance_components":dna_parts,
            "paths":{"target":normalized_intrabar_path(target_trades,target_candle.start,interval_seconds),
                     "candidate":normalized_intrabar_path(candidate_trades,candidate_candle.start,interval_seconds)},
            "note":"Trajetórias normalizadas: tempo = fração do candle; preço relativo = ticks desde a abertura; posição = 0..1 dentro do range de cada candle."}
