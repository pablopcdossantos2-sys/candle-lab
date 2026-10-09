from __future__ import annotations

from statistics import median

from .candles import trade_sort_key
from .models import AggressorSide, Trade


FLOW_EFFICIENCY_MODEL_VERSION = "1.0"


def _direction_from_delta(buy: int, sell: int) -> tuple[str, float | None]:
    directed = buy + sell
    if directed <= 0:
        return "SEM_DADOS", None
    delta = buy - sell
    dominance = abs(delta) / directed
    if dominance < 0.15:
        return "EQUILIBRADO", dominance
    return ("BUY" if delta > 0 else "SELL"), dominance


def _phase_buckets(ordered: list[Trade]) -> list[tuple[str, list[Trade]]]:
    total = len(ordered)
    cuts = [0, total // 3, (2 * total) // 3, total]
    labels = ["INICIO", "MEIO", "FINAL"]
    result: list[tuple[str, list[Trade]]] = []
    for index, label in enumerate(labels):
        bucket = ordered[cuts[index] : cuts[index + 1]]
        if bucket:
            result.append((label, bucket))
    return result


def _phase_raw(label: str, bucket: list[Trade]) -> dict[str, object]:
    buy = sum(t.quantity for t in bucket if t.aggressor == AggressorSide.BUY)
    sell = sum(t.quantity for t in bucket if t.aggressor == AggressorSide.SELL)
    directed = buy + sell
    delta = buy - sell
    direction, dominance = _direction_from_delta(buy, sell)
    move = bucket[-1].price_ticks - bucket[0].price_ticks
    seconds = max(1.0, (bucket[-1].ts - bucket[0].ts).total_seconds())
    buy_eff = (move / buy * 1000.0) if buy else None
    sell_eff = (-move / sell * 1000.0) if sell else None

    if direction == "BUY":
        dominant_volume = buy
        signed_response = move
    elif direction == "SELL":
        dominant_volume = sell
        signed_response = -move
    else:
        dominant_volume = 0
        signed_response = 0

    dominant_eff = (
        signed_response / dominant_volume * 1000.0
        if dominant_volume > 0
        else None
    )

    return {
        "phase": label,
        "start_ts": bucket[0].ts.isoformat(),
        "end_ts": bucket[-1].ts.isoformat(),
        "start_trade_number": None,
        "end_trade_number": None,
        "trades": len(bucket),
        "volume": sum(t.quantity for t in bucket),
        "buy_aggression": buy,
        "sell_aggression": sell,
        "directed_aggression": directed,
        "delta": delta,
        "flow_direction": direction,
        "dominance": dominance,
        "price_change_ticks": move,
        "duration_seconds": seconds,
        "directed_contracts_per_second": directed / seconds,
        "buy_response_ticks_per_1000": buy_eff,
        "sell_response_ticks_per_1000": sell_eff,
        "dominant_response_ticks_per_1000": dominant_eff,
    }


def _efficiency_label(
    phase: dict[str, object],
    positive_reference: list[float],
) -> str:
    if int(phase["directed_aggression"]) <= 0:
        return "SEM_DADOS"
    if phase["flow_direction"] == "EQUILIBRADO":
        return "FLUXO_EQUILIBRADO"

    value = phase["dominant_response_ticks_per_1000"]
    if value is None:
        return "SEM_DADOS"
    value = float(value)
    if value < 0:
        return "RESPOSTA_OPOSTA"
    if value == 0:
        return "SEM_RESPOSTA"

    reference = median(positive_reference) if positive_reference else value
    if reference <= 0:
        return "MODERADA"
    ratio = value / reference
    if ratio >= 1.5:
        return "ALTA"
    if ratio >= 0.5:
        return "MODERADA"
    return "BAIXA"


def _efficiency_decay_events(phases: list[dict[str, object]]) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for side in ("BUY", "SELL"):
        key = "buy_response_ticks_per_1000" if side == "BUY" else "sell_response_ticks_per_1000"
        volume_key = "buy_aggression" if side == "BUY" else "sell_aggression"
        candidates = [
            phase
            for phase in phases
            if int(phase[volume_key]) > 0 and phase[key] is not None
        ]
        if len(candidates) < 2:
            continue
        first = candidates[0]
        last = candidates[-1]
        first_eff = float(first[key])
        last_eff = float(last[key])
        first_volume = int(first[volume_key])
        last_volume = int(last[volume_key])

        if first_eff > 0 and last_volume >= max(1, int(first_volume * 0.50)):
            ratio = last_eff / first_eff
            if ratio <= 0.40:
                events.append({
                    "code": f"PERDA_EFICIENCIA_{side}",
                    "side": side,
                    "from_phase": first["phase"],
                    "to_phase": last["phase"],
                    "initial_efficiency": first_eff,
                    "final_efficiency": last_eff,
                    "efficiency_ratio": ratio,
                    "initial_volume": first_volume,
                    "final_volume": last_volume,
                    "aggression_not_collapsed": last_volume >= first_volume * 0.80,
                    "description": (
                        f"A eficiência {side} caiu fortemente entre {first['phase']} e {last['phase']} "
                        "sem desaparecimento proporcional do esforço agressor."
                    ),
                })
    return events


def flow_efficiency_analysis(
    trades: list[Trade],
    *,
    tick_size: float,
    aggression: dict[str, object] | None = None,
) -> dict[str, object]:
    """Separa iniciativa, esforço e resposta do preço para um candle.

    Métricas de eficiência são descritivas e relativas ao próprio candle. Elas não
    estimam impacto causal de mercado.
    """
    if not trades:
        raise ValueError("É necessário ao menos um negócio para analisar eficiência do fluxo")

    ordered = sorted(trades, key=trade_sort_key)
    total_volume = sum(t.quantity for t in ordered)
    buy = sum(t.quantity for t in ordered if t.aggressor == AggressorSide.BUY)
    sell = sum(t.quantity for t in ordered if t.aggressor == AggressorSide.SELL)
    directed = buy + sell
    delta = buy - sell
    direction, dominance = _direction_from_delta(buy, sell)
    price_change = ordered[-1].price_ticks - ordered[0].price_ticks
    range_ticks = max(t.price_ticks for t in ordered) - min(t.price_ticks for t in ordered)
    duration = max(1.0, (ordered[-1].ts - ordered[0].ts).total_seconds())

    phases = [_phase_raw(label, bucket) for label, bucket in _phase_buckets(ordered)]

    trade_cursor = 1
    for phase in phases:
        phase["start_trade_number"] = trade_cursor
        phase["end_trade_number"] = trade_cursor + int(phase["trades"]) - 1
        trade_cursor = int(phase["end_trade_number"]) + 1

    effort_values = [int(p["directed_aggression"]) for p in phases if int(p["directed_aggression"]) > 0]
    effort_median = median(effort_values) if effort_values else 0.0
    positive_efficiencies = [
        float(p["dominant_response_ticks_per_1000"])
        for p in phases
        if p["dominant_response_ticks_per_1000"] is not None
        and float(p["dominant_response_ticks_per_1000"]) > 0
    ]

    for phase in phases:
        directed_phase = int(phase["directed_aggression"])
        phase["effort_vs_phase_median"] = (
            directed_phase / effort_median if effort_median > 0 else None
        )
        phase["efficiency_label"] = _efficiency_label(phase, positive_efficiencies)

    events: list[dict[str, object]] = []
    for phase in phases:
        effort_ratio = phase["effort_vs_phase_median"]
        label = str(phase["efficiency_label"])
        if (
            effort_ratio is not None
            and float(effort_ratio) >= 1.0
            and label in {"BAIXA", "SEM_RESPOSTA", "RESPOSTA_OPOSTA"}
        ):
            events.append({
                "code": "ESFORCO_SEM_RESULTADO",
                "phase": phase["phase"],
                "side": phase["flow_direction"],
                "effort_vs_phase_median": effort_ratio,
                "efficiency_label": label,
                "price_change_ticks": phase["price_change_ticks"],
                "directed_aggression": phase["directed_aggression"],
                "description": (
                    f"{phase['phase']}: esforço agressor igual ou acima da mediana do candle "
                    f"com resposta classificada como {label.lower().replace('_', ' ')}."
                ),
            })

    events.extend(_efficiency_decay_events(phases))

    if direction == "BUY":
        whole_side_eff = (price_change / buy * 1000.0) if buy else None
    elif direction == "SELL":
        whole_side_eff = (-price_change / sell * 1000.0) if sell else None
    else:
        whole_side_eff = None

    price_direction = "ALTA" if price_change > 0 else "BAIXA" if price_change < 0 else "NEUTRO"
    if direction == "SEM_DADOS":
        relation = "DADOS_INSUFICIENTES"
    elif direction == "EQUILIBRADO":
        relation = "FLUXO_EQUILIBRADO"
    elif price_direction == "NEUTRO":
        relation = "PRECO_NEUTRO"
    elif (direction == "BUY" and price_direction == "ALTA") or (
        direction == "SELL" and price_direction == "BAIXA"
    ):
        relation = "ALINHADO"
    else:
        relation = "DIVERGENTE"

    top_agent_share = None
    if aggression is not None:
        if direction == "BUY":
            agents = aggression.get("top_buy_aggressors") or []
        elif direction == "SELL":
            agents = aggression.get("top_sell_aggressors") or []
        else:
            agents = []
        if agents:
            top_agent_share = float(agents[0].get("share") or 0.0)

    return {
        "model_version": FLOW_EFFICIENCY_MODEL_VERSION,
        "method": (
            "Separa iniciativa, esforço e resposta. Eficiência = deslocamento do preço em ticks "
            "por 1.000 contratos de agressão do lado analisado. Comparações de ALTA/MODERADA/BAIXA "
            "são relativas às fases do próprio candle."
        ),
        "limitations": (
            "A métrica descreve associação entre fluxo executado e resposta do preço; não mede impacto "
            "causal puro e não observa toda a liquidez passiva, cancelamentos ou ordens não executadas."
        ),
        "initiative": {
            "side": direction,
            "dominance": dominance,
            "buy_aggression": buy,
            "sell_aggression": sell,
            "delta": delta,
            "relation_to_price": relation,
            "top_agent_share": top_agent_share,
        },
        "effort": {
            "total_volume": total_volume,
            "directed_aggression": directed,
            "directed_share_total": directed / total_volume if total_volume else 0.0,
            "contracts_per_second": directed / duration,
            "trades_per_second": len(ordered) / duration,
            "duration_seconds": duration,
        },
        "response": {
            "price_change_ticks": price_change,
            "range_ticks": range_ticks,
            "price_direction": price_direction,
            "ticks_per_1000_directed": (
                price_change / directed * 1000.0 if directed else None
            ),
            "buy_response_ticks_per_1000": (
                price_change / buy * 1000.0 if buy else None
            ),
            "sell_response_ticks_per_1000": (
                -price_change / sell * 1000.0 if sell else None
            ),
            "dominant_side_response_ticks_per_1000": whole_side_eff,
        },
        "phases": phases,
        "events": events,
        "summary": {
            "relation": relation,
            "effort_without_result_count": sum(
                1 for event in events if event["code"] == "ESFORCO_SEM_RESULTADO"
            ),
            "efficiency_decay_count": sum(
                1 for event in events if str(event["code"]).startswith("PERDA_EFICIENCIA_")
            ),
            "paradox_candidate": (
                relation == "DIVERGENTE"
                or any(event["code"] == "ESFORCO_SEM_RESULTADO" for event in events)
                or any(str(event["code"]).startswith("PERDA_EFICIENCIA_") for event in events)
            ),
        },
    }
