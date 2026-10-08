from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median

from .candles import trade_sort_key
from .models import AggressorSide, Trade


AGGRESSION_MODEL_VERSION = "1.0"


def _is_rlp(trade: Trade) -> bool:
    return trade.aggressor == AggressorSide.NONE and "raw_aggressor=RLP" in (trade.flags or "")


def _top_agents(counter: Counter[str], trades_counter: Counter[str], total: int, limit: int = 5) -> list[dict[str, object]]:
    rows = []
    for agent, qty in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]:
        rows.append({
            "agent": agent,
            "quantity": int(qty),
            "trades": int(trades_counter.get(agent, 0)),
            "share": (qty / total if total else 0.0),
        })
    return rows


def _intensity_label(value: int, positives: list[int]) -> tuple[str, float, float]:
    if value <= 0 or not positives:
        return "SEM_AGRESSAO_DIRECIONADA", 0.0, 0.0

    ordered = sorted(positives)
    rank = sum(1 for item in ordered if item <= value) / len(ordered)
    med = median(ordered)
    ratio = value / med if med else 0.0

    # A classificação é deliberadamente relativa aos níveis do próprio candle.
    # Com poucos níveis, a razão contra a mediana evita um percentil instável.
    if len(ordered) < 4:
        if ratio >= 2.5:
            label = "EXTREMA"
        elif ratio >= 1.5:
            label = "ALTA"
        elif ratio >= 0.75:
            label = "MODERADA"
        else:
            label = "BAIXA"
    else:
        if rank >= 0.90:
            label = "EXTREMA"
        elif rank >= 0.70:
            label = "ALTA"
        elif rank >= 0.40:
            label = "MODERADA"
        else:
            label = "BAIXA"
    return label, rank, ratio


def _direction(buy: int, sell: int) -> tuple[str, float | None]:
    known = buy + sell
    if not known:
        return "SEM_DIRECAO", None
    delta = buy - sell
    dominance = abs(delta) / known
    if dominance < 0.15:
        return "EQUILIBRADA", dominance
    return ("COMPRA" if delta > 0 else "VENDA"), dominance


def _response_label(
    *,
    direction: str,
    intensity: str,
    dominance: float | None,
    favorable_excursion_ticks: int,
    adverse_excursion_ticks: int,
    revisits: int,
) -> str:
    if direction not in {"COMPRA", "VENDA"} or dominance is None:
        return "DISPUTA_OU_INDEFINIDA"
    if intensity not in {"ALTA", "EXTREMA"} or dominance < 0.50:
        return "PRESSAO_SEM_CONFIRMACAO"

    # Heurística descritiva: agressão dominante seguida de deslocamento favorável.
    if favorable_excursion_ticks >= 2 and favorable_excursion_ticks > adverse_excursion_ticks:
        return "IMPULSO_COMPATIVEL"

    # Alto volume agressor, pouca continuação e revisita ao nível são compatíveis
    # com absorção, mas sem livro de ofertas isso não é prova de absorção.
    if favorable_excursion_ticks <= 1 and revisits >= 1:
        return "POSSIVEL_ABSORCAO"

    return "PRESSAO_SEM_CONFIRMACAO"


def aggression_analysis(trades: list[Trade], tick_size: float) -> dict[str, object]:
    if not trades:
        raise ValueError("É necessário ao menos um negócio para analisar agressão")

    ordered = sorted(trades, key=trade_sort_key)
    total_volume = sum(t.quantity for t in ordered)

    level_stats: dict[int, dict[str, object]] = {}
    overall_buy_agents: Counter[str] = Counter()
    overall_sell_agents: Counter[str] = Counter()
    overall_buy_agent_trades: Counter[str] = Counter()
    overall_sell_agent_trades: Counter[str] = Counter()

    total_buy = total_sell = total_rlp = total_unknown = 0

    for idx, trade in enumerate(ordered):
        level = level_stats.setdefault(trade.price_ticks, {
            "volume": 0,
            "buy": 0,
            "sell": 0,
            "rlp": 0,
            "unknown": 0,
            "trades": 0,
            "first_index": idx,
            "last_index": idx,
            "visits": 0,
            "previous_index": None,
            "buy_agents": Counter(),
            "sell_agents": Counter(),
            "buy_agent_trades": Counter(),
            "sell_agent_trades": Counter(),
        })
        level["volume"] = int(level["volume"]) + trade.quantity
        level["trades"] = int(level["trades"]) + 1
        level["last_index"] = idx

        previous_index = level["previous_index"]
        if previous_index is None or idx != int(previous_index) + 1:
            level["visits"] = int(level["visits"]) + 1
        level["previous_index"] = idx

        if trade.aggressor == AggressorSide.BUY:
            level["buy"] = int(level["buy"]) + trade.quantity
            total_buy += trade.quantity
            agent = (trade.buyer_id or "").strip()
            if agent:
                level["buy_agents"][agent] += trade.quantity
                level["buy_agent_trades"][agent] += 1
                overall_buy_agents[agent] += trade.quantity
                overall_buy_agent_trades[agent] += 1
        elif trade.aggressor == AggressorSide.SELL:
            level["sell"] = int(level["sell"]) + trade.quantity
            total_sell += trade.quantity
            agent = (trade.seller_id or "").strip()
            if agent:
                level["sell_agents"][agent] += trade.quantity
                level["sell_agent_trades"][agent] += 1
                overall_sell_agents[agent] += trade.quantity
                overall_sell_agent_trades[agent] += 1
        elif _is_rlp(trade):
            level["rlp"] = int(level["rlp"]) + trade.quantity
            total_rlp += trade.quantity
        else:
            level["unknown"] = int(level["unknown"]) + trade.quantity
            total_unknown += trade.quantity

    known_total = total_buy + total_sell
    directed_by_level = [int(v["buy"]) + int(v["sell"]) for v in level_stats.values()]
    positive_directed = [v for v in directed_by_level if v > 0]

    prices = [t.price_ticks for t in ordered]
    rows: list[dict[str, object]] = []
    for price_ticks, raw in sorted(level_stats.items(), reverse=True):
        buy = int(raw["buy"])
        sell = int(raw["sell"])
        directed = buy + sell
        delta = buy - sell
        direction, dominance = _direction(buy, sell)
        intensity, percentile_rank, median_ratio = _intensity_label(directed, positive_directed)

        last_index = int(raw["last_index"])
        future_prices = prices[last_index + 1:]
        if direction == "COMPRA":
            favorable = max([0] + [p - price_ticks for p in future_prices])
            adverse = max([0] + [price_ticks - p for p in future_prices])
        elif direction == "VENDA":
            favorable = max([0] + [price_ticks - p for p in future_prices])
            adverse = max([0] + [p - price_ticks for p in future_prices])
        else:
            favorable = adverse = 0

        response = _response_label(
            direction=direction,
            intensity=intensity,
            dominance=dominance,
            favorable_excursion_ticks=favorable,
            adverse_excursion_ticks=adverse,
            revisits=max(0, int(raw["visits"]) - 1),
        )

        rows.append({
            "price_ticks": price_ticks,
            "price": round(price_ticks * tick_size, 10),
            "volume": int(raw["volume"]),
            "trades": int(raw["trades"]),
            "buy_aggression": buy,
            "sell_aggression": sell,
            "directed_aggression": directed,
            "rlp_volume": int(raw["rlp"]),
            "unknown_volume": int(raw["unknown"]),
            "delta": delta,
            "direction": direction,
            "dominance": dominance,
            "intensity": intensity,
            "intensity_percentile": percentile_rank,
            "vs_median_ratio": median_ratio,
            "share_of_candle_directed_aggression": (directed / known_total if known_total else 0.0),
            "visits": int(raw["visits"]),
            "favorable_excursion_ticks_after_level": favorable,
            "adverse_excursion_ticks_after_level": adverse,
            "response": response,
            "top_buy_aggressors": _top_agents(
                raw["buy_agents"], raw["buy_agent_trades"], buy, limit=3
            ),
            "top_sell_aggressors": _top_agents(
                raw["sell_agents"], raw["sell_agent_trades"], sell, limit=3
            ),
        })

    direction, dominance = _direction(total_buy, total_sell)
    strongest = sorted(
        rows,
        key=lambda row: (-int(row["directed_aggression"]), -abs(int(row["delta"])), -int(row["volume"])),
    )

    return {
        "model_version": AGGRESSION_MODEL_VERSION,
        "method": (
            "Agressão executada observada no Times & Trades. Intensidade relativa aos níveis "
            "do próprio candle; não é limiar universal de mercado."
        ),
        "limitations": (
            "Sem MBO/MBP, o Candle Lab não observa toda a liquidez passiva. "
            "POSSIVEL_ABSORCAO e IMPULSO_COMPATIVEL são heurísticas descritivas, não prova causal."
        ),
        "summary": {
            "total_volume": total_volume,
            "buy_aggression": total_buy,
            "sell_aggression": total_sell,
            "directed_aggression": known_total,
            "rlp_volume": total_rlp,
            "unknown_volume": total_unknown,
            "aggressor_coverage": (known_total / total_volume if total_volume else 0.0),
            "delta": total_buy - total_sell,
            "direction": direction,
            "dominance": dominance,
            "levels": len(rows),
        },
        "top_buy_aggressors": _top_agents(
            overall_buy_agents, overall_buy_agent_trades, total_buy, limit=8
        ),
        "top_sell_aggressors": _top_agents(
            overall_sell_agents, overall_sell_agent_trades, total_sell, limit=8
        ),
        "strongest_levels": strongest[:8],
        "levels": rows,
    }
