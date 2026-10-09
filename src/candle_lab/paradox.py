from __future__ import annotations

from .models import Candle


PARADOX_MODEL_VERSION = "1.0"


def _severity(score: float) -> str:
    if score >= 0.80:
        return "MUITO_ALTA"
    if score >= 0.60:
        return "ALTA"
    if score >= 0.40:
        return "MODERADA"
    return "BAIXA"


def detect_paradoxical_candle(
    *,
    candle: Candle,
    aggression: dict[str, object],
    flow_efficiency: dict[str, object],
) -> dict[str, object]:
    summary = aggression["summary"]
    relation = str(flow_efficiency["summary"]["relation"])
    events = list(flow_efficiency.get("events") or [])

    body_ticks = candle.close_ticks - candle.open_ticks
    price_direction = "ALTA" if body_ticks > 0 else "BAIXA" if body_ticks < 0 else "NEUTRO"
    coverage = float(summary.get("aggressor_coverage") or 0.0)
    dominance = float(summary.get("dominance") or 0.0)
    buy_share = float(summary.get("buy_share_directed") or 0.0)
    sell_share = float(summary.get("sell_share_directed") or 0.0)

    flags: list[dict[str, object]] = []

    if relation == "DIVERGENTE" and coverage > 0:
        score = min(1.0, 0.45 + 0.30 * dominance + 0.25 * coverage)
        if price_direction == "BAIXA" and buy_share > sell_share:
            code = "BAIXA_COM_COMPRA_AGRESSORA_DOMINANTE"
            title = "Candle de baixa com compra agressora dominante"
            explanation = (
                "O preço fechou abaixo da abertura mesmo com predominância BUY entre as agressões direcionadas. "
                "O caso merece estudo de absorção passiva, perda de eficiência compradora e sequência dos negócios."
            )
        elif price_direction == "ALTA" and sell_share > buy_share:
            code = "ALTA_COM_VENDA_AGRESSORA_DOMINANTE"
            title = "Candle de alta com venda agressora dominante"
            explanation = (
                "O preço fechou acima da abertura mesmo com predominância SELL entre as agressões direcionadas. "
                "O caso merece estudo de absorção passiva, perda de eficiência vendedora e sequência dos negócios."
            )
        else:
            code = "DIVERGENCIA_PRECO_FLUXO"
            title = "Divergência entre direção do preço e fluxo agressor"
            explanation = (
                "A direção final do preço não coincide com o lado predominante da agressão executada."
            )
        flags.append({
            "code": code,
            "title": title,
            "severity": _severity(score),
            "score": score,
            "evidence": {
                "price_direction": price_direction,
                "flow_direction": summary.get("direction"),
                "buy_share_directed": buy_share,
                "sell_share_directed": sell_share,
                "coverage": coverage,
                "dominance": dominance,
            },
            "explanation": explanation,
        })

    effort_events = [e for e in events if e.get("code") == "ESFORCO_SEM_RESULTADO"]
    if effort_events:
        strongest = max(
            effort_events,
            key=lambda e: float(e.get("effort_vs_phase_median") or 0.0),
        )
        effort_ratio = float(strongest.get("effort_vs_phase_median") or 0.0)
        score = min(1.0, 0.35 + min(effort_ratio, 2.0) * 0.20 + 0.25 * coverage)
        flags.append({
            "code": "AGRESSAO_FORTE_SEM_DESLOCAMENTO",
            "title": "Esforço agressor elevado com pouco resultado no preço",
            "severity": _severity(score),
            "score": score,
            "evidence": strongest,
            "explanation": (
                "Uma fase do candle apresentou esforço agressor igual ou superior à mediana interna, "
                "mas a resposta do preço foi baixa, nula ou oposta. Isso é compatível com perda de eficiência "
                "ou resistência passiva ao fluxo."
            ),
        })

    decay_events = [
        e for e in events
        if str(e.get("code", "")).startswith("PERDA_EFICIENCIA_")
    ]
    for event in decay_events:
        ratio = float(event.get("efficiency_ratio") or 1.0)
        score = min(1.0, 0.55 + (1.0 - max(0.0, ratio)) * 0.35)
        flags.append({
            "code": str(event["code"]),
            "title": (
                "Eficiência compradora em deterioração"
                if event.get("side") == "BUY"
                else "Eficiência vendedora em deterioração"
            ),
            "severity": _severity(score),
            "score": score,
            "evidence": event,
            "explanation": (
                "O lado agressor continuou realizando esforço, mas passou a obter menos deslocamento favorável. "
                "Esse padrão é candidato a estudo de exaustão antes de uma possível mudança de controle."
            ),
        })

    phases = list(flow_efficiency.get("phases") or [])
    if len(phases) >= 2:
        speeds = [float(p.get("directed_contracts_per_second") or 0.0) for p in phases]
        efficiencies = [
            p.get("dominant_response_ticks_per_1000")
            for p in phases
        ]
        for i in range(1, len(phases)):
            prev_eff = efficiencies[i - 1]
            curr_eff = efficiencies[i]
            if prev_eff is None or curr_eff is None:
                continue
            if speeds[i] > speeds[i - 1] * 1.15 and float(curr_eff) < float(prev_eff) * 0.60:
                score = min(1.0, 0.62 + min((speeds[i] / max(speeds[i - 1], 1e-9)) - 1.0, 1.0) * 0.20)
                flags.append({
                    "code": "AGRESSAO_ACELERA_E_EFICIENCIA_CAI",
                    "title": "Agressão acelerando enquanto a eficiência cai",
                    "severity": _severity(score),
                    "score": score,
                    "evidence": {
                        "from_phase": phases[i - 1]["phase"],
                        "to_phase": phases[i]["phase"],
                        "speed_before": speeds[i - 1],
                        "speed_after": speeds[i],
                        "efficiency_before": prev_eff,
                        "efficiency_after": curr_eff,
                    },
                    "explanation": (
                        "O fluxo agressor ficou mais rápido, mas passou a produzir menos deslocamento favorável. "
                        "É um padrão especialmente relevante para investigar absorção ou exaustão."
                    ),
                })

    flags.sort(key=lambda item: float(item["score"]), reverse=True)
    highest = float(flags[0]["score"]) if flags else 0.0

    return {
        "model_version": PARADOX_MODEL_VERSION,
        "paradoxical": bool(flags),
        "priority": _severity(highest) if flags else "NORMAL",
        "score": highest,
        "flags": flags,
        "method": (
            "O detector procura inconsistências entre esforço agressor e resposta do preço. "
            "Ele prioriza candles para investigação; não conclui automaticamente absorção, manipulação ou reversão."
        ),
    }
