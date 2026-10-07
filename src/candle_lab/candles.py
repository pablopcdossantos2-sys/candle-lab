from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Iterable

from .models import Candle, Trade


def floor_time(ts: datetime, interval_seconds: int) -> datetime:
    if interval_seconds <= 0:
        raise ValueError("interval_seconds deve ser > 0")
    epoch = int(ts.timestamp())
    floored = epoch - (epoch % interval_seconds)
    return datetime.fromtimestamp(floored, tz=ts.tzinfo)


def trade_sort_key(trade: Trade) -> tuple[object, ...]:
    """Ordenação determinística preservando a sequência da fonte em timestamps iguais."""
    seq = trade.sequence_no if trade.sequence_no is not None else 2**63 - 1
    trade_id = trade.trade_id or ""
    try:
        trade_id_key: object = (0, int(trade_id))
    except (TypeError, ValueError):
        trade_id_key = (1, trade_id)
    return trade.ts, seq, trade_id_key


def group_trades_by_candle(trades: Iterable[Trade], interval_seconds: int) -> dict[tuple[str, datetime], list[Trade]]:
    grouped: dict[tuple[str, datetime], list[Trade]] = defaultdict(list)
    for trade in trades:
        grouped[(trade.symbol, floor_time(trade.ts, interval_seconds))].append(trade)
    for key in grouped:
        grouped[key].sort(key=trade_sort_key)
    return dict(grouped)


def build_candles(trades: Iterable[Trade], interval_seconds: int) -> list[Candle]:
    grouped = group_trades_by_candle(trades, interval_seconds)
    candles: list[Candle] = []
    for (symbol, start), ordered in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1])):
        prices = [t.price_ticks for t in ordered]
        candles.append(
            Candle(
                symbol=symbol,
                start=start,
                end=start + timedelta(seconds=interval_seconds),
                interval_seconds=interval_seconds,
                open_ticks=prices[0],
                high_ticks=max(prices),
                low_ticks=min(prices),
                close_ticks=prices[-1],
                volume=sum(t.quantity for t in ordered),
                trades=len(ordered),
            )
        )
    return candles


def trades_for_candle(trades: Iterable[Trade], candle: Candle) -> list[Trade]:
    return sorted(
        [
            t
            for t in trades
            if t.symbol == candle.symbol and candle.start <= t.ts < candle.end
        ],
        key=trade_sort_key,
    )
