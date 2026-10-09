from __future__ import annotations

from dataclasses import asdict
from math import isfinite

from .candles import trade_sort_key
from .metrics import CandleDNA
from .models import AggressorSide, Candle, Trade


INTERPRETATION_MODEL_VERSION = "1.0"


def _pct(value: float | None) -> str:
    if value is None or not isfinite(value):
        return "—"
    return f"{value * 100:.1f}%".replace(".", ",")


def _num(value: float | int, decimals: int = 0) -> str:
    if decimals <= 0:
        return f"{int(round(value)):,}".replace(",", ".")
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _price(ticks: int | float, tick_size: float) -> float:
    return round(ticks * tick_size, 10)


def _close_zone(candle: Candle) -> str:
    span = candle.high_ticks - candle.low_ticks
    if span <= 0:
        return "CENTRO"
    loc = (candle.close_ticks - candle.low_ticks) / span
    if loc >= 0.80:
        return "TOPO"
    if loc <= 0.20:
        return "FUNDO"
    return "MEIO"


def _geometry(candle: Candle) -> dict[str, object]:
    body = candle.close_ticks - candle.open_ticks
    span = candle.high_ticks - candle.low_ticks
    upper_wick = candle.high_ticks - max(candle.open_ticks, candle.close_ticks)
    lower_wick = min(candle.open_ticks, candle.close_ticks) - candle.low_ticks
    if body > 0:
        direction = "ALTA"
    elif body < 0:
        direction = "BAIXA"
    else:
        direction = "NEUTRO"
    return {
        "direction": direction,
        "body_ticks": body,
        "range_ticks": span,
        "upper_wick_ticks": max(0, upper_wick),
        "lower_wick_ticks": max(0, lower_wick),
        "body_abs_share": (abs(body) / span if span else 0.0),
        "close_zone": _close_zone(candle),
    }


def _phase_stats(ordered: list[Trade], tick_size: float) -> list[dict[str, object]]:
    total = len(ordered)
    cuts = [0, total // 3, (2 * total) // 3, total]
    labels = ["INICIO", "MEIO", "FINAL"]
    result: list[dict[str, object]] = []
    for idx, label in enumerate(labels):
        start = cuts[idx]
        end = cuts[idx + 1]
        if end <= start:
            continue
        bucket = ordered[start:end]
        buy = sum(t.quantity for t in bucket if t.aggressor == AggressorSide.BUY)
        sell = sum(t.quantity for t in bucket if t.aggressor == AggressorSide.SELL)
        unknown = sum(
            t.quantity
            for t in bucket
            if t.aggressor not in {AggressorSide.BUY, AggressorSide.SELL}
        )
        directed = buy + sell
        delta = buy - sell
        dominance = abs(delta) / directed if directed else None
        if directed == 0:
            direction = "SEM_DADOS_AGRESSOR"
        elif dominance is not None and dominance < 0.15:
            direction = "EQUILIBRADA"
        else:
            direction = "COMPRA" if delta > 0 else "VENDA"
        result.append({
            "phase": label,
            "start_trade_number": start + 1,
            "end_trade_number": end,
            "start_ts": bucket[0].ts.isoformat(),
            "end_ts": bucket[-1].ts.isoformat(),
            "start_price": _price(bucket[0].price_ticks, tick_size),
            "end_price": _price(bucket[-1].price_ticks, tick_size),
            "price_change_ticks": bucket[-1].price_ticks - bucket[0].price_ticks,
            "buy_aggression": buy,
            "sell_aggression": sell,
            "unknown_aggression": unknown,
            "directed_aggression": directed,
            "delta": delta,
            "dominance": dominance,
            "direction": direction,
        })
    return result


def _phase_sentence(phase: dict[str, object]) -> str:
    label = {
        "INICIO": "No início",
        "MEIO": "No miolo",
        "FINAL": "Na fase final",
    }.get(str(phase["phase"]), str(phase["phase"]))
    direction = str(phase["direction"])
    delta = int(phase["delta"])
    move = int(phase["price_change_ticks"])
    if direction == "SEM_DADOS_AGRESSOR":
        flow = "o lado agressor não estava disponível nos negócios desta fase"
    elif direction == "EQUILIBRADA":
        flow = "o fluxo agressor conhecido ficou relativamente equilibrado"
    else:
        side = "compradora" if direction == "COMPRA" else "vendedora"
        flow = f"predominou a agressão {side}, com delta {_num(delta)}"
    if move > 0:
        response = f"e o preço terminou esse trecho {move} tick(s) acima do início da fase"
    elif move < 0:
        response = f"e o preço terminou esse trecho {abs(move)} tick(s) abaixo do início da fase"
    else:
        response = "sem deslocamento líquido de preço nesse trecho"
    return f"{label}, {flow}, {response}."


def _evidence_quality(aggression: dict[str, object], total_trades: int) -> dict[str, object]:
    summary = aggression["summary"]
    aggressor_coverage = float(summary.get("aggressor_coverage") or 0.0)
    identity_coverage = float(summary.get("agent_identity_coverage") or 0.0)
    if aggressor_coverage <= 0:
        score = 0.0
        label = "INDISPONIVEL"
    else:
        score = 0.60 * aggressor_coverage + 0.25 * identity_coverage + 0.15 * min(total_trades / 100.0, 1.0)
        if score >= 0.80:
            label = "ALTA"
        elif score >= 0.60:
            label = "MODERADA"
        else:
            label = "LIMITADA"
    return {
        "score": score,
        "label": label,
        "aggressor_coverage": aggressor_coverage,
        "agent_identity_coverage": identity_coverage,
        "trades": total_trades,
    }


def _level_fact(level: dict[str, object], tick_size: float) -> str:
    direction = level.get("direction")
    if direction == "COMPRA":
        side = "compradora"
    elif direction == "VENDA":
        side = "vendedora"
    else:
        side = "equilibrada"
    return (
        f"No preço {_num(float(level['price']), 2)}, houve {_num(int(level['directed_aggression']))} "
        f"contratos de agressão direcionada, intensidade {str(level['intensity']).lower()} e "
        f"leitura {side}; o nível concentrou {_pct(float(level['share_of_candle_directed_aggression']))} "
        "da agressão direcionada conhecida do candle."
    )


def _agent_fact(aggression: dict[str, object]) -> list[str]:
    facts: list[str] = []
    buys = aggression.get("top_buy_aggressors") or []
    sells = aggression.get("top_sell_aggressors") or []
    if buys:
        x = buys[0]
        facts.append(
            f"O principal agente comprador agressor identificado foi {x['agent']}, com "
            f"{_num(int(x['quantity']))} contratos ({_pct(float(x['share']))} da agressão compradora identificada)."
        )
    if sells:
        x = sells[0]
        facts.append(
            f"O principal agente vendedor agressor identificado foi {x['agent']}, com "
            f"{_num(int(x['quantity']))} contratos ({_pct(float(x['share']))} da agressão vendedora identificada)."
        )
    return facts


def _hypothesis(
    code: str,
    title: str,
    score: float,
    explanation: str,
    supporting: list[str],
    counter: list[str] | None = None,
) -> dict[str, object]:
    score = max(0.0, min(1.0, score))
    if score >= 0.72:
        confidence = "FORTE"
    elif score >= 0.48:
        confidence = "MODERADA"
    else:
        confidence = "FRACA"
    return {
        "code": code,
        "title": title,
        "confidence": confidence,
        "score": score,
        "explanation": explanation,
        "supporting_evidence": supporting,
        "counter_evidence": counter or [],
    }


def interpret_candle(
    trades: list[Trade],
    *,
    candle: Candle,
    dna: CandleDNA,
    aggression: dict[str, object],
    waves: dict[str, object],
    tick_size: float,
    flow_efficiency: dict[str, object] | None = None,
    paradox: dict[str, object] | None = None,
) -> dict[str, object]:
    """Gera uma interpretação auditável, separando observação de hipótese."""
    if not trades:
        raise ValueError("É necessário ao menos um negócio para interpretar o candle")
    ordered = sorted(trades, key=trade_sort_key)
    geom = _geometry(candle)
    phases = _phase_stats(ordered, tick_size)
    quality = _evidence_quality(aggression, len(ordered))
    summary = aggression["summary"]
    buy = int(summary["buy_aggression"])
    sell = int(summary["sell_aggression"])
    delta = int(summary["delta"])
    known = buy + sell
    imbalance = delta / known if known else 0.0

    observed: list[dict[str, object]] = []
    observed.append({
        "code": "GEOMETRIA",
        "text": (
            f"O candle abriu em {_num(_price(candle.open_ticks, tick_size), 2)}, atingiu máxima "
            f"{_num(_price(candle.high_ticks, tick_size), 2)}, mínima {_num(_price(candle.low_ticks, tick_size), 2)} "
            f"e fechou em {_num(_price(candle.close_ticks, tick_size), 2)}. O corpo foi de "
            f"{_num(abs(int(geom['body_ticks'])))} tick(s), com fechamento na região "
            f"{str(geom['close_zone']).lower()} do range."
        ),
        "data": geom,
    })
    if known > 0:
        aggression_text = (
            f"A agressão conhecida somou {_num(known)} contratos: {_num(buy)} compradores e "
            f"{_num(sell)} vendedores; delta {_num(delta)} e cobertura de agressor "
            f"{_pct(float(summary['aggressor_coverage']))}."
        )
    else:
        aggression_text = (
            "Não foi possível calcular agressão compradora/vendedora para este candle porque "
            "nenhum negócio possui lado agressor BUY/SELL reconhecido. "
            f"O candle contém {_num(int(summary['total_volume']))} contratos de volume total, "
            f"dos quais {_num(int(summary['rlp_volume']))} estão marcados como RLP e "
            f"{_num(int(summary['unknown_volume']))} ficaram sem lado agressor identificável. "
            "Cobertura de agressor: 0,0%. Isto significa dado de agressão indisponível, não agressão igual a zero."
        )

    observed.append({
        "code": "AGRESSAO_TOTAL",
        "text": aggression_text,
        "data": {
            "buy": buy,
            "sell": sell,
            "delta": delta,
            "coverage": summary["aggressor_coverage"],
            "data_available": known > 0,
            "rlp_volume": summary["rlp_volume"],
            "unknown_volume": summary["unknown_volume"],
            "total_volume": summary["total_volume"],
        },
    })

    observed.append({
        "code": "COMPOSICAO_AGRESSAO",
        "text": (
            f"Do volume total do candle, {_pct(float(summary.get('buy_share_total_volume') or 0.0))} veio de "
            f"agressão compradora reconhecida, {_pct(float(summary.get('sell_share_total_volume') or 0.0))} de "
            f"agressão vendedora, {_pct(float(summary.get('rlp_share_total_volume') or 0.0))} de RLP e "
            f"{_pct(float(summary.get('unknown_share_total_volume') or 0.0))} permaneceu sem classificação direcional. "
            f"Entre apenas as agressões BUY/SELL conhecidas, a divisão foi "
            f"{_pct(float(summary.get('buy_share_directed') or 0.0))} compra e "
            f"{_pct(float(summary.get('sell_share_directed') or 0.0))} venda."
        ),
        "data": {
            "buy_share_total_volume": summary.get("buy_share_total_volume"),
            "sell_share_total_volume": summary.get("sell_share_total_volume"),
            "rlp_share_total_volume": summary.get("rlp_share_total_volume"),
            "unknown_share_total_volume": summary.get("unknown_share_total_volume"),
            "buy_share_directed": summary.get("buy_share_directed"),
            "sell_share_directed": summary.get("sell_share_directed"),
        },
    })

    if summary.get("price_flow_relation") == "DIVERGENTE":
        observed.append({
            "code": "DIVERGENCIA_PRECO_FLUXO",
            "text": (
                f"O candle foi de {str(summary.get('price_direction')).lower()}, enquanto o fluxo agressor "
                f"direcionado predominante foi de {str(summary.get('direction')).lower()}. "
                f"Esta divergência foi marcada para estudo com prioridade {str(summary.get('study_priority')).lower()}. "
                "Ela não é, por si só, erro de dado nem prova de absorção: a sequência dos negócios, os níveis de preço, "
                "as revisitas e a resposta posterior precisam ser examinados."
            ),
            "data": {
                "price_direction": summary.get("price_direction"),
                "flow_direction": summary.get("direction"),
                "relation": summary.get("price_flow_relation"),
                "study_priority": summary.get("study_priority"),
            },
        })

    if flow_efficiency is not None:
        fe_summary = flow_efficiency.get("summary") or {}
        fe_response = flow_efficiency.get("response") or {}
        observed.append({
            "code": "EFICIENCIA_FLUXO",
            "text": (
                f"A resposta líquida do preço foi de {_num(int(fe_response.get('price_change_ticks') or 0))} tick(s). "
                f"A eficiência sobre toda a agressão direcionada foi "
                f"{_num(float(fe_response.get('ticks_per_1000_directed') or 0.0), 2)} tick(s) por 1.000 contratos. "
                f"Foram detectados {int(fe_summary.get('effort_without_result_count') or 0)} episódio(s) de esforço sem resultado "
                f"e {int(fe_summary.get('efficiency_decay_count') or 0)} episódio(s) de perda de eficiência."
            ),
            "data": {
                "response": fe_response,
                "summary": fe_summary,
            },
        })

    if paradox is not None and paradox.get("paradoxical"):
        flags = list(paradox.get("flags") or [])
        observed.append({
            "code": "CANDLE_PARADOXAL",
            "text": (
                f"O candle foi marcado como paradoxal, com prioridade {str(paradox.get('priority')).lower().replace('_', ' ')} "
                f"e {len(flags)} sinal(is) de conflito entre esforço agressor e resposta do preço."
            ),
            "data": paradox,
        })

    strongest = list(aggression.get("strongest_levels") or [])
    if strongest:
        observed.append({
            "code": "NIVEL_MAIS_AGREDIDO",
            "text": _level_fact(strongest[0], tick_size),
            "data": strongest[0],
        })

    for text in _agent_fact(aggression):
        observed.append({"code": "AGENTE", "text": text})

    terminations = list(waves.get("termination_events") or [])
    if terminations:
        e = terminations[-1]
        observed.append({
            "code": "ULTIMO_TERMINO_ONDA",
            "text": (
                f"A última onda agressora encerrada foi {e['side']}, terminando às "
                f"{str(e['end_ts'])[11:19]} por {str(e['termination_type']).lower().replace('_', ' ')}, "
                f"com queda de pressão de {_pct(float(e['pressure_decay']))} em relação ao pico da onda."
            ),
            "data": e,
        })
    if waves.get("open_episode"):
        o = waves["open_episode"]
        observed.append({
            "code": "ONDA_ABERTA_FECHAMENTO",
            "text": (
                f"O candle terminou com uma onda {o['side']} ainda aberta no fechamento, "
                "sem evento de término confirmado dentro do próprio candle."
            ),
            "data": o,
        })

    chronology = [_phase_sentence(p) for p in phases]

    hypotheses: list[dict[str, object]] = []
    candle_up = candle.close_ticks > candle.open_ticks
    candle_down = candle.close_ticks < candle.open_ticks
    close_top = geom["close_zone"] == "TOPO"
    close_bottom = geom["close_zone"] == "FUNDO"
    directed_strength = abs(imbalance)
    coverage = float(summary["aggressor_coverage"])

    # Hipótese 1: agressão alinhada ao fechamento.
    if candle_up and delta > 0:
        score = 0.35 + 0.30 * directed_strength + 0.20 * coverage + (0.12 if close_top else 0.0)
        hypotheses.append(_hypothesis(
            "AGRESSAO_ALINHADA_ALTA",
            "Pressão compradora compatível com o fechamento de alta",
            score,
            (
                "O fechamento acima da abertura ocorreu com saldo agressor comprador. A leitura mais simples é que "
                "a iniciativa compradora participou do deslocamento e/ou ajudou a sustentar os preços mais altos. "
                "Isso é compatibilidade entre fluxo e preço, não prova de causalidade."
            ),
            [
                f"Delta comprador de {_num(delta)} contratos.",
                f"Fechamento {str(geom['close_zone']).lower()} no range.",
                f"Cobertura de agressor de {_pct(coverage)}.",
            ],
        ))
    elif candle_down and delta < 0:
        score = 0.35 + 0.30 * directed_strength + 0.20 * coverage + (0.12 if close_bottom else 0.0)
        hypotheses.append(_hypothesis(
            "AGRESSAO_ALINHADA_BAIXA",
            "Pressão vendedora compatível com o fechamento de baixa",
            score,
            (
                "O fechamento abaixo da abertura ocorreu com saldo agressor vendedor. A leitura mais simples é que "
                "a iniciativa vendedora participou do deslocamento e/ou ajudou a sustentar os preços mais baixos. "
                "Isso é compatibilidade entre fluxo e preço, não prova de causalidade."
            ),
            [
                f"Delta vendedor de {_num(abs(delta))} contratos.",
                f"Fechamento {str(geom['close_zone']).lower()} no range.",
                f"Cobertura de agressor de {_pct(coverage)}.",
            ],
        ))

    # Hipótese 2: divergência preço x agressão, compatível com absorção passiva.
    if candle_up and delta < 0:
        score = 0.38 + 0.25 * directed_strength + 0.18 * coverage
        hypotheses.append(_hypothesis(
            "ALTA_COM_DELTA_VENDEDOR",
            "Venda agressora absorvida ou incapaz de produzir queda sustentada",
            score,
            (
                "O candle subiu apesar de maior volume vendedor agressor. Isso é compatível com a hipótese de que "
                "compradores passivos tenham absorvido parte da venda, ou de que a venda agressora tenha ocorrido "
                "sem capacidade de deslocar o preço para baixo. Sem livro MBO/MBP, absorção permanece hipótese."
            ),
            [
                f"Candle fechou {_num(candle.close_ticks-candle.open_ticks)} tick(s) acima da abertura.",
                f"Delta foi vendedor em {_num(abs(delta))} contratos.",
            ],
            ["A fonte de Trades não revela toda a liquidez passiva disponível."],
        ))
    elif candle_down and delta > 0:
        score = 0.38 + 0.25 * directed_strength + 0.18 * coverage
        hypotheses.append(_hypothesis(
            "BAIXA_COM_DELTA_COMPRADOR",
            "Compra agressora absorvida ou incapaz de produzir alta sustentada",
            score,
            (
                "O candle caiu apesar de maior volume comprador agressor. Isso é compatível com a hipótese de que "
                "vendedores passivos tenham absorvido parte da compra, ou de que a compra agressora não tenha sido "
                "capaz de sustentar preços mais altos. Sem livro MBO/MBP, absorção permanece hipótese."
            ),
            [
                f"Candle fechou {_num(candle.open_ticks-candle.close_ticks)} tick(s) abaixo da abertura.",
                f"Delta foi comprador em {_num(delta)} contratos.",
            ],
            ["A fonte de Trades não revela toda a liquidez passiva disponível."],
        ))

    if flow_efficiency is not None:
        fe_events = list(flow_efficiency.get("events") or [])
        effort_events = [e for e in fe_events if e.get("code") == "ESFORCO_SEM_RESULTADO"]
        decay_events = [e for e in fe_events if str(e.get("code", "")).startswith("PERDA_EFICIENCIA_")]
        if effort_events:
            strongest_effort = max(
                effort_events,
                key=lambda e: float(e.get("effort_vs_phase_median") or 0.0),
            )
            score = 0.48 + min(0.22, float(strongest_effort.get("effort_vs_phase_median") or 0.0) * 0.10) + 0.15 * coverage
            hypotheses.append(_hypothesis(
                "ESFORCO_AGRESSOR_SEM_RESULTADO",
                "Esforço agressor elevado sem deslocamento proporcional",
                score,
                (
                    "Uma fase do candle apresentou agressão relevante, mas o preço respondeu pouco, não respondeu "
                    "ou caminhou contra o lado dominante. Isso é compatível com perda de eficiência do fluxo e merece "
                    "investigação de absorção passiva ou resistência do lado oposto."
                ),
                [
                    str(strongest_effort.get("description") or "Evento de esforço sem resultado detectado."),
                    "A métrica compara deslocamento em ticks com o volume agressor executado.",
                ],
                ["Sem MBO/MBP não é possível provar absorção passiva."],
            ))
        if decay_events:
            strongest_decay = min(
                decay_events,
                key=lambda e: float(e.get("efficiency_ratio") or 1.0),
            )
            score = 0.58 + min(0.20, (1.0 - max(0.0, float(strongest_decay.get("efficiency_ratio") or 1.0))) * 0.20)
            hypotheses.append(_hypothesis(
                "PERDA_EFICIENCIA_FLUXO",
                "Agressão persistente com eficiência decrescente",
                score,
                (
                    "O lado agressor continuou executando volume, mas obteve progressivamente menos deslocamento favorável. "
                    "Esse padrão é compatível com exaustão do impulso e pode anteceder neutralização ou troca de controle."
                ),
                [
                    str(strongest_decay.get("description") or "Perda de eficiência detectada."),
                ],
            ))

    # Hipótese 3: rejeição em extremos baseada em wick + níveis/ondas.
    upper = int(geom["upper_wick_ticks"])
    lower = int(geom["lower_wick_ticks"])
    span = max(int(geom["range_ticks"]), 1)
    near_high = [
        x for x in aggression.get("levels", [])
        if candle.high_ticks - int(x["price_ticks"]) <= 1
        and x.get("response") == "POSSIVEL_ABSORCAO"
    ]
    near_low = [
        x for x in aggression.get("levels", [])
        if int(x["price_ticks"]) - candle.low_ticks <= 1
        and x.get("response") == "POSSIVEL_ABSORCAO"
    ]
    buy_end_near_high = [
        e for e in terminations
        if e["side"] == "BUY" and candle.high_ticks - int(e["end_price_ticks"]) <= 2
    ]
    sell_end_near_low = [
        e for e in terminations
        if e["side"] == "SELL" and int(e["end_price_ticks"]) - candle.low_ticks <= 2
    ]
    if upper / span >= 0.25 and (near_high or buy_end_near_high):
        support = [f"Sombra superior de {_num(upper)} tick(s), {_pct(upper/span)} do range."]
        if near_high:
            support.append("Há nível próximo da máxima rotulado como possível absorção.")
        if buy_end_near_high:
            support.append("Uma onda BUY terminou próxima da máxima.")
        hypotheses.append(_hypothesis(
            "REJEICAO_MAXIMA",
            "Perda de eficiência compradora próxima da máxima",
            0.58 + min(0.18, upper / span * 0.20) + (0.10 if near_high else 0.0) + (0.10 if buy_end_near_high else 0.0),
            (
                "A combinação entre sombra superior e enfraquecimento/absorção compatível perto da máxima sugere "
                "que a compra agressora encontrou dificuldade para converter esforço em permanência nos preços altos. "
                "Isso pode ajudar a explicar por que o fechamento ocorreu abaixo da máxima."
            ),
            support,
        ))
    if lower / span >= 0.25 and (near_low or sell_end_near_low):
        support = [f"Sombra inferior de {_num(lower)} tick(s), {_pct(lower/span)} do range."]
        if near_low:
            support.append("Há nível próximo da mínima rotulado como possível absorção.")
        if sell_end_near_low:
            support.append("Uma onda SELL terminou próxima da mínima.")
        hypotheses.append(_hypothesis(
            "REJEICAO_MINIMA",
            "Perda de eficiência vendedora próxima da mínima",
            0.58 + min(0.18, lower / span * 0.20) + (0.10 if near_low else 0.0) + (0.10 if sell_end_near_low else 0.0),
            (
                "A combinação entre sombra inferior e enfraquecimento/absorção compatível perto da mínima sugere "
                "que a venda agressora encontrou dificuldade para converter esforço em permanência nos preços baixos. "
                "Isso pode ajudar a explicar por que o fechamento ocorreu acima da mínima."
            ),
            support,
        ))

    # Hipótese 4: onda ainda aberta no fechamento.
    open_wave = waves.get("open_episode")
    if open_wave:
        side = str(open_wave["side"])
        aligned = (side == "BUY" and (candle_up or close_top)) or (side == "SELL" and (candle_down or close_bottom))
        if aligned:
            hypotheses.append(_hypothesis(
                "ONDA_ABERTA_SUSTENTA_FECHAMENTO",
                f"Onda {side} ainda ativa pode ter sustentado a região de fechamento",
                0.62 + 0.15 * coverage,
                (
                    f"O candle terminou sem término confirmado da onda {side}. A persistência dessa pressão até o "
                    "fim é compatível com um fechamento ainda sustentado pelo mesmo lado agressor."
                ),
                [
                    f"Onda {side} permaneceu aberta no fim do candle.",
                    f"Fechamento na região {str(geom['close_zone']).lower()} do range.",
                ],
            ))

    # Hipótese 5: fluxo balanceado / disputa.
    if known and abs(imbalance) < 0.15 and geom["close_zone"] == "MEIO":
        hypotheses.append(_hypothesis(
            "DISPUTA_EQUILIBRADA",
            "Disputa bilateral sem domínio agressor claro",
            0.60 + 0.15 * coverage,
            (
                "O saldo agressor ficou próximo do equilíbrio e o fechamento ocorreu no miolo do range. "
                "A formação é compatível com uma disputa em que nenhum lado conseguiu converter a agressão "
                "em domínio persistente do preço."
            ),
            [
                f"Desequilíbrio agressor absoluto de {_pct(abs(imbalance))}.",
                "Fechamento no meio do range.",
            ],
        ))

    # Evidência final: mudança entre primeiro e último terço.
    if len(phases) >= 3:
        first, final = phases[0], phases[-1]
        if first["direction"] != final["direction"] and {
            first["direction"], final["direction"]
        } <= {"COMPRA", "VENDA"}:
            hypotheses.append(_hypothesis(
                "MUDANCA_CONTROLE_INTRABAR",
                "Mudança de controle agressor ao longo do candle",
                0.66,
                (
                    f"O início foi dominado por {str(first['direction']).lower()} e a fase final por "
                    f"{str(final['direction']).lower()}. Essa mudança de controle é uma explicação plausível "
                    "para o candle não ter encerrado com a mesma dinâmica observada em sua primeira fase."
                ),
                [_phase_sentence(first), _phase_sentence(final)],
            ))

    hypotheses.sort(key=lambda item: float(item["score"]), reverse=True)

    # Síntese do fechamento: usa as hipóteses mais fortes, sem transformar hipótese em fato.
    if hypotheses:
        top = hypotheses[:2]
        synthesis = (
            f"O fechamento em {_num(_price(candle.close_ticks, tick_size), 2)} é mais compatível, nesta leitura, "
            f"com: {top[0]['title'].lower()}"
        )
        if len(top) > 1:
            synthesis += f"; em segundo plano, {top[1]['title'].lower()}"
        synthesis += (
            ". Essas são hipóteses explicativas construídas a partir do fluxo executado e da trajetória do preço; "
            "não constituem demonstração causal."
        )
    else:
        synthesis = (
            "Os dados disponíveis não produzem uma hipótese explicativa suficientemente forte para o fechamento. "
            "O sistema mantém a leitura como inconclusiva em vez de forçar uma narrativa."
        )

    limitations = [
        "Times & Trades mostra execuções, não toda a liquidez passiva do livro.",
        "O identificador de agente não deve ser interpretado automaticamente como investidor final.",
        "RLP e agressões sem lado conhecido reduzem a cobertura da leitura direcional.",
        "Hipóteses de absorção, exaustão e sustentação descrevem compatibilidades observadas; não provam causalidade.",
        "A avaliação do porquê do fechamento é retrospectiva e deve ser validada em uma biblioteca histórica ampla.",
    ]
    if quality["label"] == "LIMITADA":
        limitations.insert(
            0,
            "A qualidade da evidência de agressão deste candle é limitada; a interpretação deve receber menor peso.",
        )

    return {
        "model_version": INTERPRETATION_MODEL_VERSION,
        "label": "RELATORIO_INTERPRETATIVO — HIPOTESES, NAO CAUSALIDADE COMPROVADA",
        "evidence_quality": quality,
        "geometry": geom,
        "phase_analysis": phases,
        "observed_facts": observed,
        "process_description": chronology,
        "hypotheses": hypotheses,
        "closing_synthesis": synthesis,
        "limitations": limitations,
        "audit": {
            "aggression_model_version": aggression.get("model_version"),
            "aggression_wave_model_version": waves.get("model_version"),
            "flow_efficiency_model_version": (
                flow_efficiency.get("model_version") if flow_efficiency is not None else None
            ),
            "paradox_model_version": paradox.get("model_version") if paradox is not None else None,
            "dna": asdict(dna),
        },
    }
