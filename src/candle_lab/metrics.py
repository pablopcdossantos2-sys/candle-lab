from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import ceil
from statistics import mean, median

from .candles import trade_sort_key
from .models import AggressorSide, Trade


@dataclass(frozen=True, slots=True)
class CandleDNA:
    range_ticks: int
    path_distance_ticks: int
    net_displacement_ticks: int
    directional_efficiency: float
    range_efficiency: float
    body_to_range: float
    close_location: float
    reversals: int
    reversal_rate: float
    price_change_events: int
    unchanged_transitions: int
    unique_prices: int
    high_first: str
    time_to_high_ms: float
    time_to_low_ms: float
    high_visits: int
    low_visits: int
    total_revisits: int
    revisit_rate: float
    most_traded_price_ticks: int
    vwap_ticks: float
    mean_trade_size: float
    max_trade_size: int
    buy_aggression_qty: int
    sell_aggression_qty: int
    unknown_aggression_qty: int
    aggressor_coverage: float
    aggression_imbalance: float | None
    upper_third_volume_share: float
    middle_third_volume_share: float
    lower_third_volume_share: float
    up_excursion_ticks: int
    down_excursion_ticks: int
    max_drawdown_ticks: int
    max_drawup_ticks: int
    avg_intertrade_ms: float
    median_intertrade_ms: float
    p95_intertrade_ms: float
    max_intertrade_ms: float
    trades_per_second: float


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    lo = int(rank)
    hi = ceil(rank)
    if lo == hi:
        return ordered[lo]
    fraction = rank - lo
    return ordered[lo] * (1 - fraction) + ordered[hi] * fraction


def _price_visits(prices: list[int], target: int) -> int:
    visits = 0
    previous_on_target = False
    for price in prices:
        on_target = price == target
        if on_target and not previous_on_target:
            visits += 1
        previous_on_target = on_target
    return visits


def _all_revisits(prices: list[int]) -> int:
    seen: set[int] = set()
    previous: int | None = None
    revisits = 0
    for price in prices:
        if price != previous:
            if price in seen:
                revisits += 1
            seen.add(price)
        previous = price
    return revisits


def candle_dna(trades: list[Trade], interval_seconds: int | None = None) -> CandleDNA:
    if not trades:
        raise ValueError("É necessário ao menos um negócio")

    ordered = sorted(trades, key=trade_sort_key)
    prices = [t.price_ticks for t in ordered]
    quantities = [t.quantity for t in ordered]
    deltas = [b - a for a, b in zip(prices, prices[1:])]
    nonzero_deltas = [d for d in deltas if d != 0]

    high = max(prices)
    low = min(prices)
    price_range = high - low
    path_distance = sum(abs(d) for d in deltas)
    net = prices[-1] - prices[0]
    directional_efficiency = abs(net) / path_distance if path_distance else 0.0
    range_efficiency = price_range / path_distance if path_distance else 0.0
    body_to_range = net / price_range if price_range else 0.0
    close_location = (prices[-1] - low) / price_range if price_range else 0.5

    signs = [1 if d > 0 else -1 for d in nonzero_deltas]
    reversals = sum(1 for a, b in zip(signs, signs[1:]) if a != b)
    reversal_rate = reversals / max(len(signs) - 1, 1) if signs else 0.0

    first_high_index = prices.index(high)
    first_low_index = prices.index(low)
    if price_range == 0:
        high_first = "FLAT"
    elif first_high_index < first_low_index:
        high_first = "HIGH_FIRST"
    else:
        high_first = "LOW_FIRST"

    t0 = ordered[0].ts
    time_to_high_ms = (ordered[first_high_index].ts - t0).total_seconds() * 1000
    time_to_low_ms = (ordered[first_low_index].ts - t0).total_seconds() * 1000
    high_visits = _price_visits(prices, high)
    low_visits = _price_visits(prices, low)
    total_revisits = _all_revisits(prices)
    revisit_rate = total_revisits / max(len(ordered), 1)

    qty_by_price: Counter[int] = Counter()
    buy = sell = unknown = 0
    total_qty = sum(quantities)
    weighted_price = 0
    for t in ordered:
        qty_by_price[t.price_ticks] += t.quantity
        weighted_price += t.price_ticks * t.quantity
        if t.aggressor == AggressorSide.BUY:
            buy += t.quantity
        elif t.aggressor == AggressorSide.SELL:
            sell += t.quantity
        else:
            unknown += t.quantity

    poc = max(qty_by_price.items(), key=lambda kv: (kv[1], -kv[0]))[0]
    vwap_ticks = weighted_price / total_qty if total_qty else float(prices[-1])
    known_aggression = buy + sell
    aggressor_coverage = known_aggression / total_qty if total_qty else 0.0
    aggression_imbalance = (buy - sell) / known_aggression if known_aggression else None

    upper_qty = middle_qty = lower_qty = 0
    if price_range == 0:
        middle_qty = total_qty
    else:
        one_third = price_range / 3
        lower_cut = low + one_third
        upper_cut = high - one_third
        for trade in ordered:
            if trade.price_ticks <= lower_cut:
                lower_qty += trade.quantity
            elif trade.price_ticks >= upper_cut:
                upper_qty += trade.quantity
            else:
                middle_qty += trade.quantity

    running_high = running_low = prices[0]
    max_drawdown = max_drawup = 0
    for price in prices:
        running_high = max(running_high, price)
        running_low = min(running_low, price)
        max_drawdown = max(max_drawdown, running_high - price)
        max_drawup = max(max_drawup, price - running_low)

    intertrade_ms = [
        max(0.0, (b.ts - a.ts).total_seconds() * 1000)
        for a, b in zip(ordered, ordered[1:])
    ]
    elapsed_seconds = max((ordered[-1].ts - ordered[0].ts).total_seconds(), 0.0)
    denominator = interval_seconds if interval_seconds and interval_seconds > 0 else elapsed_seconds
    if denominator <= 0:
        trades_per_second = float(len(ordered))
    else:
        trades_per_second = len(ordered) / denominator

    return CandleDNA(
        range_ticks=price_range,
        path_distance_ticks=path_distance,
        net_displacement_ticks=net,
        directional_efficiency=directional_efficiency,
        range_efficiency=range_efficiency,
        body_to_range=body_to_range,
        close_location=close_location,
        reversals=reversals,
        reversal_rate=reversal_rate,
        price_change_events=len(nonzero_deltas),
        unchanged_transitions=sum(1 for d in deltas if d == 0),
        unique_prices=len(set(prices)),
        high_first=high_first,
        time_to_high_ms=time_to_high_ms,
        time_to_low_ms=time_to_low_ms,
        high_visits=high_visits,
        low_visits=low_visits,
        total_revisits=total_revisits,
        revisit_rate=revisit_rate,
        most_traded_price_ticks=poc,
        vwap_ticks=vwap_ticks,
        mean_trade_size=mean(quantities),
        max_trade_size=max(quantities),
        buy_aggression_qty=buy,
        sell_aggression_qty=sell,
        unknown_aggression_qty=unknown,
        aggressor_coverage=aggressor_coverage,
        aggression_imbalance=aggression_imbalance,
        upper_third_volume_share=upper_qty / total_qty if total_qty else 0.0,
        middle_third_volume_share=middle_qty / total_qty if total_qty else 0.0,
        lower_third_volume_share=lower_qty / total_qty if total_qty else 0.0,
        up_excursion_ticks=high - prices[0],
        down_excursion_ticks=prices[0] - low,
        max_drawdown_ticks=max_drawdown,
        max_drawup_ticks=max_drawup,
        avg_intertrade_ms=mean(intertrade_ms) if intertrade_ms else 0.0,
        median_intertrade_ms=median(intertrade_ms) if intertrade_ms else 0.0,
        p95_intertrade_ms=_percentile(intertrade_ms, 0.95),
        max_intertrade_ms=max(intertrade_ms) if intertrade_ms else 0.0,
        trades_per_second=trades_per_second,
    )
