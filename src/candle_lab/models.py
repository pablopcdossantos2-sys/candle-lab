from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AggressorSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class Trade:
    symbol: str
    ts: datetime
    price_ticks: int
    quantity: int
    trade_id: str | None = None
    aggressor: AggressorSide = AggressorSide.NONE
    source: str = "unknown"
    buyer_id: str | None = None
    seller_id: str | None = None
    sequence_no: int | None = None
    flags: str | None = None


@dataclass(frozen=True, slots=True)
class Candle:
    symbol: str
    start: datetime
    end: datetime
    interval_seconds: int
    open_ticks: int
    high_ticks: int
    low_ticks: int
    close_ticks: int
    volume: int
    trades: int
