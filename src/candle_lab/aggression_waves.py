from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime

from .candles import trade_sort_key
from .models import AggressorSide, Trade


AGGRESSION_WAVE_MODEL_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class PressureWindow:
    index: int
    ts: datetime
    price_ticks: int
    buy: int
    sell: int
    directed: int
    total: int
    signed_dominance: float
    coverage: float


def _window_metrics(
    ordered: list[Trade],
    *,
    window_trades: int,
) -> list[PressureWindow]:
    queue: deque[tuple[int, int, int]] = deque()
    buy = sell = total = 0
    rows: list[PressureWindow] = []

    for index, trade in enumerate(ordered):
        b = trade.quantity if trade.aggressor == AggressorSide.BUY else 0
        s = trade.quantity if trade.aggressor == AggressorSide.SELL else 0
        q = trade.quantity
        queue.append((b, s, q))
        buy += b
        sell += s
        total += q

        if len(queue) > window_trades:
            old_b, old_s, old_q = queue.popleft()
            buy -= old_b
            sell -= old_s
            total -= old_q

        directed = buy + sell
        signed = (buy - sell) / directed if directed else 0.0
        coverage = directed / total if total else 0.0
        rows.append(
            PressureWindow(
                index=index,
                ts=trade.ts,
                price_ticks=trade.price_ticks,
                buy=buy,
                sell=sell,
                directed=directed,
                total=total,
                signed_dominance=signed,
                coverage=coverage,
            )
        )
    return rows


def _side_value(side: str, window: PressureWindow) -> int:
    return window.buy if side == "BUY" else window.sell


def _same_side_dominance(side: str, window: PressureWindow) -> float:
    return window.signed_dominance if side == "BUY" else -window.signed_dominance


def _top_episode_agents(
    ordered: list[Trade],
    *,
    side: str,
    start_index: int,
    end_index: int,
    limit: int = 5,
) -> list[dict[str, object]]:
    qty: Counter[str] = Counter()
    trades: Counter[str] = Counter()
    total = 0
    for trade in ordered[start_index : end_index + 1]:
        if side == "BUY" and trade.aggressor == AggressorSide.BUY:
            agent = (trade.buyer_id or "").strip()
        elif side == "SELL" and trade.aggressor == AggressorSide.SELL:
            agent = (trade.seller_id or "").strip()
        else:
            continue
        total += trade.quantity
        if agent:
            qty[agent] += trade.quantity
            trades[agent] += 1

    return [
        {
            "agent": agent,
            "quantity": int(volume),
            "trades": int(trades[agent]),
            "share": (volume / total if total else 0.0),
        }
        for agent, volume in sorted(qty.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def _post_event_evaluation(
    ordered: list[Trade],
    *,
    event_index: int,
    side: str,
    horizon_trades: int,
    reversal_ticks: int,
) -> dict[str, object]:
    event_price = ordered[event_index].price_ticks
    future = ordered[event_index + 1 : event_index + 1 + horizon_trades]
    if not future:
        return {
            "uses_future_data": True,
            "outcome": "SEM_JANELA_POSTERIOR",
            "observations": 0,
            "max_reversal_ticks": 0,
            "max_continuation_ticks": 0,
            "first_reversal_trade_offset": None,
        }

    prices = [trade.price_ticks for trade in future]
    if side == "BUY":
        reversal = max([0] + [event_price - p for p in prices])
        continuation = max([0] + [p - event_price for p in prices])
        reversal_offsets = [
            i + 1 for i, p in enumerate(prices) if event_price - p >= reversal_ticks
        ]
    else:
        reversal = max([0] + [p - event_price for p in prices])
        continuation = max([0] + [event_price - p for p in prices])
        reversal_offsets = [
            i + 1 for i, p in enumerate(prices) if p - event_price >= reversal_ticks
        ]

    if reversal >= reversal_ticks and reversal > continuation:
        outcome = "REVERSAO_COMPATIVEL"
    elif continuation >= reversal_ticks and continuation > reversal:
        outcome = "CONTINUACAO"
    else:
        outcome = "ESTAGNACAO_OU_DISPUTA"

    return {
        "uses_future_data": True,
        "outcome": outcome,
        "observations": len(future),
        "max_reversal_ticks": reversal,
        "max_continuation_ticks": continuation,
        "first_reversal_trade_offset": reversal_offsets[0] if reversal_offsets else None,
    }


def aggression_wave_analysis(
    trades: list[Trade],
    tick_size: float,
    *,
    window_trades: int = 25,
    activation_dominance: float = 0.55,
    release_dominance: float = 0.20,
    opposite_takeover: float = 0.45,
    min_coverage: float = 0.50,
    activation_confirmations: int = 2,
    release_confirmations: int = 3,
    decay_ratio: float = 0.35,
    post_event_horizon_trades: int = 50,
    reversal_ticks: int = 2,
) -> dict[str, object]:
    """Detecta ondas e término de agressão usando apenas dados passados no instante do evento.

    A avaliação pós-evento é calculada separadamente e explicitamente marcada como look-ahead
    para validação histórica, nunca para definir o evento.
    """
    if not trades:
        raise ValueError("É necessário ao menos um negócio")
    if window_trades < 5:
        raise ValueError("window_trades deve ser >= 5")

    ordered = sorted(trades, key=trade_sort_key)
    windows = _window_metrics(ordered, window_trades=window_trades)

    active: dict[str, object] | None = None
    activation_side: str | None = None
    activation_count = 0
    activation_first_index: int | None = None
    release_count = 0
    release_candidate_type: str | None = None
    episodes: list[dict[str, object]] = []

    for w in windows:
        if w.index + 1 < window_trades:
            continue

        if active is None:
            side: str | None = None
            if w.coverage >= min_coverage and w.signed_dominance >= activation_dominance:
                side = "BUY"
            elif w.coverage >= min_coverage and w.signed_dominance <= -activation_dominance:
                side = "SELL"

            if side is None:
                activation_side = None
                activation_count = 0
                activation_first_index = None
                continue

            if side == activation_side:
                activation_count += 1
            else:
                activation_side = side
                activation_count = 1
                activation_first_index = w.index

            if activation_count >= activation_confirmations:
                start_index = activation_first_index if activation_first_index is not None else w.index
                active = {
                    "side": side,
                    "start_index": start_index,
                    "start_ts": ordered[start_index].ts,
                    "start_price_ticks": ordered[start_index].price_ticks,
                    "peak_side_window_qty": _side_value(side, w),
                    "peak_dominance": _same_side_dominance(side, w),
                    "peak_index": w.index,
                }
                activation_side = None
                activation_count = 0
                activation_first_index = None
                release_count = 0
                release_candidate_type = None
            continue

        side = str(active["side"])
        same_dom = _same_side_dominance(side, w)
        side_qty = _side_value(side, w)
        peak_qty = max(int(active["peak_side_window_qty"]), side_qty)
        if peak_qty > int(active["peak_side_window_qty"]):
            active["peak_side_window_qty"] = peak_qty
            active["peak_index"] = w.index
        active["peak_dominance"] = max(float(active["peak_dominance"]), same_dom)

        current_type: str | None = None
        if side == "BUY" and w.signed_dominance <= -opposite_takeover and w.coverage >= min_coverage:
            current_type = "TROCA_CONTROLE"
        elif side == "SELL" and w.signed_dominance >= opposite_takeover and w.coverage >= min_coverage:
            current_type = "TROCA_CONTROLE"
        elif same_dom <= release_dominance:
            ratio = side_qty / max(int(active["peak_side_window_qty"]), 1)
            if ratio <= decay_ratio:
                current_type = "EXAUSTAO"
            else:
                current_type = "NEUTRALIZACAO"

        if current_type is None:
            release_count = 0
            release_candidate_type = None
            continue

        if current_type == release_candidate_type:
            release_count += 1
        else:
            release_candidate_type = current_type
            release_count = 1

        if release_count < release_confirmations:
            continue

        end_index = w.index
        peak_qty = max(int(active["peak_side_window_qty"]), 1)
        current_side_qty = side_qty
        decay = 1.0 - min(current_side_qty / peak_qty, 1.0)
        end_price_ticks = ordered[end_index].price_ticks
        start_index = int(active["start_index"])

        event = {
            "side": side,
            "start_index": start_index,
            "start_trade_number": start_index + 1,
            "start_ts": ordered[start_index].ts.isoformat(),
            "start_price_ticks": int(active["start_price_ticks"]),
            "start_price": round(int(active["start_price_ticks"]) * tick_size, 10),
            "peak_index": int(active["peak_index"]),
            "peak_trade_number": int(active["peak_index"]) + 1,
            "peak_side_window_qty": int(active["peak_side_window_qty"]),
            "peak_dominance": float(active["peak_dominance"]),
            "end_index": end_index,
            "end_trade_number": end_index + 1,
            "end_ts": ordered[end_index].ts.isoformat(),
            "end_price_ticks": end_price_ticks,
            "end_price": round(end_price_ticks * tick_size, 10),
            "termination_type": release_candidate_type,
            "end_window_side_qty": current_side_qty,
            "end_window_opposite_qty": w.sell if side == "BUY" else w.buy,
            "end_window_directed_qty": w.directed,
            "end_window_coverage": w.coverage,
            "end_signed_dominance": w.signed_dominance,
            "pressure_decay": decay,
            "duration_trades": end_index - start_index + 1,
            "duration_seconds": max(
                0.0, (ordered[end_index].ts - ordered[start_index].ts).total_seconds()
            ),
            "top_aggressors": _top_episode_agents(
                ordered, side=side, start_index=start_index, end_index=end_index
            ),
        }
        event["post_event"] = _post_event_evaluation(
            ordered,
            event_index=end_index,
            side=side,
            horizon_trades=post_event_horizon_trades,
            reversal_ticks=reversal_ticks,
        )
        episodes.append(event)

        active = None
        release_count = 0
        release_candidate_type = None

        # Se o encerramento foi por troca de controle, a pressão oposta pode começar
        # uma nova onda imediatamente nos próximos negócios, sem retroagir o evento.
        activation_side = None
        activation_count = 0
        activation_first_index = None

    open_episode: dict[str, object] | None = None
    if active is not None:
        side = str(active["side"])
        last = windows[-1]
        start_index = int(active["start_index"])
        open_episode = {
            "side": side,
            "start_index": start_index,
            "start_trade_number": start_index + 1,
            "start_ts": ordered[start_index].ts.isoformat(),
            "start_price": round(ordered[start_index].price_ticks * tick_size, 10),
            "peak_side_window_qty": int(active["peak_side_window_qty"]),
            "peak_dominance": float(active["peak_dominance"]),
            "last_trade_number": last.index + 1,
            "last_ts": last.ts.isoformat(),
            "status": "ABERTA_NO_FIM_DO_CANDLE",
            "top_aggressors": _top_episode_agents(
                ordered, side=side, start_index=start_index, end_index=last.index
            ),
        }

    return {
        "model_version": AGGRESSION_WAVE_MODEL_VERSION,
        "causal_detection": True,
        "method": (
            "Janela móvel causal por número de negócios. Uma onda começa após confirmações "
            "consecutivas de dominância BUY/SELL e termina somente após confirmações consecutivas "
            "de perda de pressão, neutralização ou tomada pelo lado oposto."
        ),
        "parameters": {
            "window_trades": window_trades,
            "activation_dominance": activation_dominance,
            "release_dominance": release_dominance,
            "opposite_takeover": opposite_takeover,
            "min_coverage": min_coverage,
            "activation_confirmations": activation_confirmations,
            "release_confirmations": release_confirmations,
            "decay_ratio": decay_ratio,
            "post_event_horizon_trades": post_event_horizon_trades,
            "reversal_ticks": reversal_ticks,
        },
        "limitations": (
            "O término da agressão é um evento de fluxo executado, não uma garantia de reversão. "
            "A avaliação pós-evento usa dados futuros apenas para validação histórica e está "
            "explicitamente separada da detecção causal."
        ),
        "termination_events": episodes,
        "open_episode": open_episode,
        "summary": {
            "terminations": len(episodes),
            "exhaustion": sum(1 for e in episodes if e["termination_type"] == "EXAUSTAO"),
            "neutralization": sum(1 for e in episodes if e["termination_type"] == "NEUTRALIZACAO"),
            "control_handoff": sum(1 for e in episodes if e["termination_type"] == "TROCA_CONTROLE"),
            "reversal_compatible_ex_post": sum(
                1
                for e in episodes
                if e["post_event"]["outcome"] == "REVERSAO_COMPATIVEL"
            ),
        },
    }
