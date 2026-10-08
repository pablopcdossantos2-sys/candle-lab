from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from math import log

from .aggression import aggression_analysis
from .aggression_waves import aggression_wave_analysis
from .interpretation import interpret_candle
from .candles import build_candles, group_trades_by_candle, trade_sort_key
from .counterfactual import generate_ohlc_path
from .metrics import CandleDNA, candle_dna
from .models import AggressorSide, Candle, Trade


def _price(ticks: int | float, tick_size: float) -> float:
    return round(ticks * tick_size, 10)


def _candle_to_dict(candle: Candle, tick_size: float) -> dict[str, object]:
    return {
        "symbol": candle.symbol,
        "start": candle.start.isoformat(),
        "end": candle.end.isoformat(),
        "interval_seconds": candle.interval_seconds,
        "open_ticks": candle.open_ticks,
        "high_ticks": candle.high_ticks,
        "low_ticks": candle.low_ticks,
        "close_ticks": candle.close_ticks,
        "open": _price(candle.open_ticks, tick_size),
        "high": _price(candle.high_ticks, tick_size),
        "low": _price(candle.low_ticks, tick_size),
        "close": _price(candle.close_ticks, tick_size),
        "volume": candle.volume,
        "trades": candle.trades,
    }


def candle_payload(trades: list[Trade], interval_seconds: int, tick_size: float) -> list[dict[str, object]]:
    return [_candle_to_dict(candle, tick_size) for candle in build_candles(trades, interval_seconds)]


def _dna_payload(dna: CandleDNA, tick_size: float) -> dict[str, object]:
    payload = asdict(dna)
    payload["most_traded_price"] = _price(dna.most_traded_price_ticks, tick_size)
    payload["vwap"] = _price(dna.vwap_ticks, tick_size)
    return payload


def candle_detail_payload(trades: list[Trade], interval_seconds: int, tick_size: float, seed: int = 42) -> dict[str, object]:
    if not trades:
        raise ValueError("Nenhum negócio no candle selecionado")
    ordered = sorted(trades, key=trade_sort_key)
    candles = build_candles(ordered, interval_seconds)
    if len(candles) != 1:
        raise ValueError("O intervalo informado contém mais de um candle")
    candle = candles[0]
    dna = candle_dna(ordered, interval_seconds=interval_seconds)

    volume_by_price: dict[int, dict[str, int]] = {}
    timeline: list[dict[str, object]] = []
    running_high = running_low = ordered[0].price_ticks
    running_volume = 0
    running_buy = running_sell = 0
    for index, trade in enumerate(ordered):
        running_high = max(running_high, trade.price_ticks)
        running_low = min(running_low, trade.price_ticks)
        running_volume += trade.quantity
        if trade.aggressor == AggressorSide.BUY:
            running_buy += trade.quantity
        elif trade.aggressor == AggressorSide.SELL:
            running_sell += trade.quantity

        level = volume_by_price.setdefault(trade.price_ticks, {"volume": 0, "buy": 0, "sell": 0, "unknown": 0})
        level["volume"] += trade.quantity
        if trade.aggressor == AggressorSide.BUY:
            level["buy"] += trade.quantity
        elif trade.aggressor == AggressorSide.SELL:
            level["sell"] += trade.quantity
        else:
            level["unknown"] += trade.quantity

        known = running_buy + running_sell
        timeline.append(
            {
                "index": index,
                "sequence_no": trade.sequence_no,
                "ts": trade.ts.isoformat(),
                "price_ticks": trade.price_ticks,
                "price": _price(trade.price_ticks, tick_size),
                "quantity": trade.quantity,
                "trade_id": trade.trade_id,
                "aggressor": trade.aggressor.value,
                "buyer_id": trade.buyer_id,
                "seller_id": trade.seller_id,
                "running_high": _price(running_high, tick_size),
                "running_low": _price(running_low, tick_size),
                "running_close": _price(trade.price_ticks, tick_size),
                "running_volume": running_volume,
                "running_buy_qty": running_buy,
                "running_sell_qty": running_sell,
                "running_aggression_imbalance": ((running_buy - running_sell) / known if known else None),
            }
        )

    aggression = aggression_analysis(ordered, tick_size)
    aggression_waves = aggression_wave_analysis(ordered, tick_size)
    interpretation = interpret_candle(
        ordered,
        candle=candle,
        dna=dna,
        aggression=aggression,
        waves=aggression_waves,
        tick_size=tick_size,
    )

    points = max(16, min(160, len(ordered)))
    counterfactual_ticks = generate_ohlc_path(
        candle.open_ticks,
        candle.high_ticks,
        candle.low_ticks,
        candle.close_ticks,
        points=points,
        seed=seed,
    )

    return {
        "candle": _candle_to_dict(candle, tick_size),
        "dna": _dna_payload(dna, tick_size),
        "timeline": timeline,
        "volume_by_price": [
            {
                "price_ticks": p,
                "price": _price(p, tick_size),
                **stats,
                "delta": stats["buy"] - stats["sell"],
            }
            for p, stats in sorted(volume_by_price.items(), reverse=True)
        ],
        "aggression": aggression,
        "aggression_waves": aggression_waves,
        "interpretation": interpretation,
        "counterfactual": {
            "label": "SIMULAÇÃO CONTRAFACTUAL — NÃO É REPLAY HISTÓRICO",
            "seed": seed,
            "prices": [_price(p, tick_size) for p in counterfactual_ticks],
        },
    }


def _ratio_distance(a: float, b: float) -> float:
    return min(abs(log((a + 1.0) / (b + 1.0))) / 2.0, 1.0)


def _structural_distance(target_candle: Candle, target: CandleDNA, candidate_candle: Candle, candidate: CandleDNA) -> tuple[float, dict[str, float]]:
    parts: dict[str, tuple[float, float]] = {
        "corpo_range": (abs(target.body_to_range - candidate.body_to_range) / 2.0, 1.25),
        "fechamento_no_range": (abs(target.close_location - candidate.close_location), 0.8),
        "eficiencia_direcional": (abs(target.directional_efficiency - candidate.directional_efficiency), 1.0),
        "eficiencia_range": (abs(target.range_efficiency - candidate.range_efficiency), 1.0),
        "reversoes": (abs(target.reversal_rate - candidate.reversal_rate), 0.8),
        "revisitas": (min(abs(target.revisit_rate - candidate.revisit_rate), 1.0), 0.7),
        "volume_superior": (abs(target.upper_third_volume_share - candidate.upper_third_volume_share), 0.45),
        "volume_inferior": (abs(target.lower_third_volume_share - candidate.lower_third_volume_share), 0.45),
        "amplitude": (_ratio_distance(target.range_ticks, candidate.range_ticks), 0.55),
        "numero_negocios": (_ratio_distance(target_candle.trades, candidate_candle.trades), 0.4),
        "volume": (_ratio_distance(target_candle.volume, candidate_candle.volume), 0.35),
        "ordem_extremos": (0.0 if target.high_first == candidate.high_first else 1.0, 0.55),
    }
    if target.aggression_imbalance is not None and candidate.aggression_imbalance is not None:
        parts["agressao"] = (abs(target.aggression_imbalance - candidate.aggression_imbalance) / 2.0, 0.65)

    weighted_sum = sum(value * weight for value, weight in parts.values())
    total_weight = sum(weight for _, weight in parts.values())
    normalized = weighted_sum / total_weight if total_weight else 1.0
    return normalized, {name: round(value, 4) for name, (value, _) in parts.items()}


def similar_candles_payload(
    trades: list[Trade],
    *,
    target_start: datetime,
    interval_seconds: int,
    tick_size: float,
    limit: int = 8,
) -> dict[str, object]:
    grouped = group_trades_by_candle(trades, interval_seconds)
    target_key = None
    for key in grouped:
        if key[1] == target_start:
            target_key = key
            break
    if target_key is None:
        raise ValueError("Candle-alvo não encontrado no conjunto pesquisado")

    target_trades = grouped[target_key]
    target_candle = build_candles(target_trades, interval_seconds)[0]
    target_dna = candle_dna(target_trades, interval_seconds=interval_seconds)

    candidates: list[dict[str, object]] = []
    for key, bucket in grouped.items():
        if key == target_key:
            continue
        candle = build_candles(bucket, interval_seconds)[0]
        dna = candle_dna(bucket, interval_seconds=interval_seconds)
        distance, components = _structural_distance(target_candle, target_dna, candle, dna)
        score = max(0.0, min(100.0, (1.0 - distance) * 100.0))
        candidates.append(
            {
                "score": round(score, 1),
                "candle": _candle_to_dict(candle, tick_size),
                "dna": {
                    "directional_efficiency": dna.directional_efficiency,
                    "range_efficiency": dna.range_efficiency,
                    "reversal_rate": dna.reversal_rate,
                    "revisit_rate": dna.revisit_rate,
                    "high_first": dna.high_first,
                    "aggression_imbalance": dna.aggression_imbalance,
                },
                "distance_components": components,
            }
        )

    candidates.sort(key=lambda item: (-float(item["score"]), str(item["candle"]["start"])))
    return {
        "method": "heurística estrutural v0.4 — não é modelo de machine learning",
        "target": _candle_to_dict(target_candle, tick_size),
        "matches": candidates[: max(1, min(limit, 50))],
    }
