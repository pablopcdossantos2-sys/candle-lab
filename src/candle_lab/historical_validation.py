from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from math import sqrt
from statistics import mean

from .aggression import aggression_analysis
from .aggression_waves import aggression_wave_analysis
from .candles import build_candles, group_trades_by_candle
from .interpretation import interpret_candle
from .metrics import candle_dna
from .models import Candle, Trade
from .reconciliation import ReferenceCandle


HISTORICAL_VALIDATION_MODEL_VERSION = "1.0"

_FIXED_DIRECTION = {
    "AGRESSAO_ALINHADA_ALTA": "UP",
    "AGRESSAO_ALINHADA_BAIXA": "DOWN",
    "ALTA_COM_DELTA_VENDEDOR": "UP",
    "BAIXA_COM_DELTA_COMPRADOR": "DOWN",
    "REJEICAO_MAXIMA": "DOWN",
    "REJEICAO_MINIMA": "UP",
}

_DIRECTIONAL_ROLE = {
    "AGRESSAO_ALINHADA_ALTA": "CONTINUACAO_EXPLORATORIA",
    "AGRESSAO_ALINHADA_BAIXA": "CONTINUACAO_EXPLORATORIA",
    "ALTA_COM_DELTA_VENDEDOR": "RESILIENCIA_OU_ABSORCAO",
    "BAIXA_COM_DELTA_COMPRADOR": "RESILIENCIA_OU_ABSORCAO",
    "REJEICAO_MAXIMA": "REVERSAO_CANDIDATA",
    "REJEICAO_MINIMA": "REVERSAO_CANDIDATA",
    "ONDA_ABERTA_SUSTENTA_FECHAMENTO": "CONTINUACAO_EXPLORATORIA",
    "MUDANCA_CONTROLE_INTRABAR": "CONTROLE_FINAL_EXPLORATORIO",
    "DISPUTA_EQUILIBRADA": "DESCRITIVA_NAO_DIRECIONAL",
}


def _is_synthetic(trades: list[Trade]) -> bool:
    return any((trade.source or "").lower().startswith("synthetic") for trade in trades)


def _reference_map(
    refs: list[ReferenceCandle] | None,
    interval_seconds: int,
) -> dict[object, ReferenceCandle]:
    if not refs:
        return {}
    return {
        ref.start: ref
        for ref in refs
        if int(ref.interval_seconds) == int(interval_seconds)
    }


def _reference_exact(candle: Candle, ref: ReferenceCandle) -> bool:
    if (
        candle.open_ticks != ref.open_ticks
        or candle.high_ticks != ref.high_ticks
        or candle.low_ticks != ref.low_ticks
        or candle.close_ticks != ref.close_ticks
    ):
        return False
    if ref.volume is not None and candle.volume != ref.volume:
        return False
    return True


def _sample_status(n: int) -> str:
    if n < 30:
        return "AMOSTRA_INSUFICIENTE"
    if n < 100:
        return "EXPLORATORIA"
    if n < 500:
        return "PRELIMINAR"
    return "AMOSTRA_MAIOR"


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float | None, float | None]:
    if total <= 0:
        return None, None
    p = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denom
    margin = z * sqrt((p * (1 - p) + z2 / (4 * total)) / total) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def _expected_direction(hypothesis: dict[str, object], report: dict[str, object]) -> str | None:
    code = str(hypothesis.get("code") or "")
    if code in _FIXED_DIRECTION:
        return _FIXED_DIRECTION[code]
    if code == "ONDA_ABERTA_SUSTENTA_FECHAMENTO":
        open_wave = report.get("audit", {}).get("open_wave")
        if isinstance(open_wave, dict):
            side = str(open_wave.get("side") or "")
            return "UP" if side == "BUY" else "DOWN" if side == "SELL" else None
        # Compatibility with reports generated before open_wave entered audit.
        title = str(hypothesis.get("title") or "")
        if "BUY" in title:
            return "UP"
        if "SELL" in title:
            return "DOWN"
    if code == "MUDANCA_CONTROLE_INTRABAR":
        phases = report.get("phase_analysis") or []
        if phases:
            final = phases[-1]
            direction = str(final.get("direction") or "")
            return "UP" if direction == "COMPRA" else "DOWN" if direction == "VENDA" else None
    return None


def _future_outcome(
    current: Candle,
    future: list[Candle],
    direction: str,
) -> dict[str, object]:
    last = future[-1]
    endpoint_delta = last.close_ticks - current.close_ticks
    max_up = max([0] + [c.high_ticks - current.close_ticks for c in future])
    max_down = max([0] + [current.close_ticks - c.low_ticks for c in future])
    sign = 1 if direction == "UP" else -1
    aligned_delta = endpoint_delta * sign
    favorable = max_up if direction == "UP" else max_down
    adverse = max_down if direction == "UP" else max_up
    return {
        "endpoint_delta_ticks": endpoint_delta,
        "aligned_endpoint_ticks": aligned_delta,
        "favorable_excursion_ticks": favorable,
        "adverse_excursion_ticks": adverse,
        "directional_hit": aligned_delta > 0,
        "two_tick_hit": aligned_delta >= 2,
    }


def _baseline(
    candles: dict[object, Candle],
    *,
    interval_seconds: int,
    horizon: int,
) -> dict[str, object]:
    up = down = flat = total = 0
    step = timedelta(seconds=interval_seconds)
    for start, candle in sorted(candles.items()):
        future = []
        for k in range(1, horizon + 1):
            item = candles.get(start + step * k)
            if item is None or item.start.date() != candle.start.date():
                future = []
                break
            future.append(item)
        if not future:
            continue
        delta = future[-1].close_ticks - candle.close_ticks
        total += 1
        if delta > 0:
            up += 1
        elif delta < 0:
            down += 1
        else:
            flat += 1
    return {
        "eligible": total,
        "up": up,
        "down": down,
        "flat": flat,
        "up_rate": up / total if total else None,
        "down_rate": down / total if total else None,
        "flat_rate": flat / total if total else None,
    }


def validate_historical_hypotheses(
    trades: list[Trade],
    *,
    interval_seconds: int,
    tick_size: float,
    reference_candles: list[ReferenceCandle] | None = None,
    horizons: tuple[int, ...] = (1, 3, 5),
    include_synthetic: bool = False,
    require_reference_when_available: bool = True,
) -> dict[str, object]:
    """Valida repetibilidade e comportamento posterior das hipóteses da v0.17.

    O estudo não 'prova' a explicação causal do candle. Ele mede ocorrência e associações
    posteriores fora do candle que originou a hipótese.
    """
    if interval_seconds <= 0:
        raise ValueError("interval_seconds deve ser positivo")
    horizons = tuple(sorted({int(h) for h in horizons if int(h) > 0}))
    if not horizons:
        raise ValueError("Informe ao menos um horizonte positivo")

    grouped = group_trades_by_candle(trades, interval_seconds)
    ref_map = _reference_map(reference_candles, interval_seconds)
    has_refs = bool(ref_map)

    eligible_groups: dict[object, list[Trade]] = {}
    eligible_candles: dict[object, Candle] = {}
    exclusions: Counter[str] = Counter()

    for (_, start), candle_trades in sorted(grouped.items(), key=lambda item: item[0][1]):
        if not include_synthetic and _is_synthetic(candle_trades):
            exclusions["SYNTHETIC"] += 1
            continue
        candles = build_candles(candle_trades, interval_seconds)
        if len(candles) != 1:
            exclusions["INVALID_GROUP"] += 1
            continue
        candle = candles[0]

        if has_refs and require_reference_when_available:
            ref = ref_map.get(start)
            if ref is None:
                exclusions["NO_REFERENCE"] += 1
                continue
            if not _reference_exact(candle, ref):
                exclusions["REFERENCE_MISMATCH"] += 1
                continue

        eligible_groups[start] = candle_trades
        eligible_candles[start] = candle

    baselines = {
        str(h): _baseline(eligible_candles, interval_seconds=interval_seconds, horizon=h)
        for h in horizons
    }

    hypothesis_occurrences: Counter[str] = Counter()
    confidence_counts: dict[str, Counter[str]] = defaultdict(Counter)
    interpretation_rows: list[dict[str, object]] = []
    outcome_buckets: dict[tuple[str, int, str], list[dict[str, object]]] = defaultdict(list)

    step = timedelta(seconds=interval_seconds)

    for start, candle_trades in sorted(eligible_groups.items()):
        candle = eligible_candles[start]
        dna = candle_dna(candle_trades, interval_seconds=interval_seconds)
        aggression = aggression_analysis(candle_trades, tick_size)
        waves = aggression_wave_analysis(candle_trades, tick_size)
        report = interpret_candle(
            candle_trades,
            candle=candle,
            dna=dna,
            aggression=aggression,
            waves=waves,
            tick_size=tick_size,
        )
        # Add open wave to audit for deterministic directional mapping.
        report.setdefault("audit", {})["open_wave"] = waves.get("open_episode")

        row_hypotheses = []
        for hypothesis in report.get("hypotheses", []):
            code = str(hypothesis["code"])
            hypothesis_occurrences[code] += 1
            confidence_counts[code][str(hypothesis["confidence"])] += 1
            direction = _expected_direction(hypothesis, report)
            row_hypotheses.append({
                "code": code,
                "score": hypothesis["score"],
                "confidence": hypothesis["confidence"],
                "expected_direction": direction,
            })
            if direction is None:
                continue

            for horizon in horizons:
                future: list[Candle] = []
                for k in range(1, horizon + 1):
                    future_candle = eligible_candles.get(start + step * k)
                    if future_candle is None or future_candle.start.date() != candle.start.date():
                        future = []
                        break
                    future.append(future_candle)
                if not future:
                    continue
                outcome = _future_outcome(candle, future, direction)
                outcome_buckets[(code, horizon, direction)].append({
                    **outcome,
                    "start": start.isoformat(),
                    "score": float(hypothesis["score"]),
                    "confidence": str(hypothesis["confidence"]),
                    "evidence_quality": str(report["evidence_quality"]["label"]),
                })

        interpretation_rows.append({
            "start": start.isoformat(),
            "evidence_quality": report["evidence_quality"]["label"],
            "hypotheses": row_hypotheses,
        })

    results: list[dict[str, object]] = []
    for (code, horizon, direction), rows in outcome_buckets.items():
        total = len(rows)
        hits = sum(1 for r in rows if r["directional_hit"])
        strong_hits = sum(1 for r in rows if r["two_tick_hit"])
        low, high = _wilson(hits, total)
        baseline = baselines[str(horizon)]
        baseline_rate = baseline["up_rate"] if direction == "UP" else baseline["down_rate"]
        hit_rate = hits / total if total else None
        lift = (hit_rate - baseline_rate) if hit_rate is not None and baseline_rate is not None else None

        by_confidence = {}
        for confidence in ("FORTE", "MODERADA", "FRACA"):
            subset = [r for r in rows if r["confidence"] == confidence]
            if not subset:
                continue
            n = len(subset)
            h = sum(1 for r in subset if r["directional_hit"])
            lo, hi = _wilson(h, n)
            by_confidence[confidence] = {
                "n": n,
                "hits": h,
                "hit_rate": h / n,
                "wilson95_low": lo,
                "wilson95_high": hi,
            }

        results.append({
            "hypothesis_code": code,
            "validation_role": _DIRECTIONAL_ROLE.get(code, "DIRECIONAL_EXPLORATORIA"),
            "expected_direction": direction,
            "horizon_candles": horizon,
            "occurrences_total": int(hypothesis_occurrences[code]),
            "with_contiguous_outcome": total,
            "sample_status": _sample_status(total),
            "directional_hits": hits,
            "directional_hit_rate": hit_rate,
            "two_tick_hits": strong_hits,
            "two_tick_hit_rate": strong_hits / total if total else None,
            "wilson95_low": low,
            "wilson95_high": high,
            "baseline_rate": baseline_rate,
            "lift_percentage_points": lift * 100 if lift is not None else None,
            "mean_aligned_endpoint_ticks": mean(r["aligned_endpoint_ticks"] for r in rows) if rows else None,
            "mean_favorable_excursion_ticks": mean(r["favorable_excursion_ticks"] for r in rows) if rows else None,
            "mean_adverse_excursion_ticks": mean(r["adverse_excursion_ticks"] for r in rows) if rows else None,
            "mean_hypothesis_score": mean(r["score"] for r in rows) if rows else None,
            "by_confidence": by_confidence,
        })

    # Preserve hypotheses that occurred but are not assigned a directional validation target.
    directional_codes = {str(r["hypothesis_code"]) for r in results}
    descriptive = [
        {
            "hypothesis_code": code,
            "validation_role": _DIRECTIONAL_ROLE.get(code, "DESCRITIVA"),
            "occurrences_total": int(count),
            "confidence_counts": dict(confidence_counts[code]),
            "note": (
                "Hipótese sem alvo direcional pré-registrado nesta versão. "
                "A validação limita-se à frequência/repetibilidade até que exista um desfecho externo definido."
            ),
        }
        for code, count in sorted(hypothesis_occurrences.items())
        if code not in directional_codes
    ]

    results.sort(key=lambda r: (-int(r["with_contiguous_outcome"]), str(r["hypothesis_code"]), int(r["horizon_candles"])))

    return {
        "model_version": HISTORICAL_VALIDATION_MODEL_VERSION,
        "scope": (
            "Validação histórica de repetibilidade e consequência externa. Não valida como verdadeira "
            "a narrativa causal que gerou a hipótese no mesmo candle."
        ),
        "symbol": trades[0].symbol if trades else None,
        "interval_seconds": interval_seconds,
        "horizons": list(horizons),
        "reference_mode": (
            "REFERENCE_EXACT_REQUIRED"
            if has_refs and require_reference_when_available
            else "TICK_LIBRARY_UNVERIFIED_BY_REFERENCE"
        ),
        "input": {
            "trades": len(trades),
            "raw_candle_groups": len(grouped),
            "eligible_candles": len(eligible_candles),
            "excluded": dict(exclusions),
            "synthetic_included": include_synthetic,
        },
        "baselines": baselines,
        "hypothesis_occurrences": dict(hypothesis_occurrences),
        "directional_results": results,
        "descriptive_results": descriptive,
        "interpretation_rows": interpretation_rows,
        "warnings": [
            "Não interprete lift positivo com amostra pequena como vantagem estatística comprovada.",
            "Os scores da v0.17 não são probabilidades; esta camada mede resultados externos separadamente.",
            "Candles futuros precisam ser contíguos no mesmo pregão para entrar no desfecho.",
            (
                "Candles foram exigidos como EXACT contra a referência OHLC/quantidade."
                if has_refs and require_reference_when_available
                else "Não havia referência compatível suficiente; a completude dos candles não foi verificada externamente."
            ),
        ],
    }
