from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, time
from statistics import median
from typing import Iterable

from .models import Trade

QUALITY_MODEL_VERSION = "0.7.0"


@dataclass(frozen=True, slots=True)
class ScheduleDefinition:
    schedule_id: str
    label: str
    open_time: time
    close_time: time
    effective_from: date | None = None
    effective_to: date | None = None
    source_note: str = ""

    def applies(self, session_date: date) -> bool:
        if self.effective_from and session_date < self.effective_from:
            return False
        if self.effective_to and session_date > self.effective_to:
            return False
        return True


@dataclass(frozen=True, slots=True)
class ObservedGap:
    start: datetime
    end: datetime
    seconds: float

    def to_record(self) -> dict[str, object]:
        return {"start": self.start.isoformat(), "end": self.end.isoformat(), "seconds": round(self.seconds, 3)}


@dataclass(frozen=True, slots=True)
class SessionQuality:
    symbol: str
    session_date: date
    schedule_id: str | None
    schedule_label: str | None
    expected_start: datetime | None
    expected_end: datetime | None
    observed_first: datetime
    observed_last: datetime
    expected_duration_seconds: float | None
    observed_span_seconds: float
    coverage_ratio: float | None
    active_minute_ratio: float | None
    start_delay_seconds: float | None
    end_early_seconds: float | None
    gap_threshold_seconds: float
    gap_count: int
    max_gap_seconds: float
    p95_intertrade_seconds: float
    status: str
    score: float
    eligible_for_research: bool
    warnings: tuple[str, ...]
    largest_gaps: tuple[ObservedGap, ...]

    def to_record(self) -> dict[str, object]:
        payload = asdict(self)
        payload["session_date"] = self.session_date.isoformat()
        payload["expected_start"] = self.expected_start.isoformat() if self.expected_start else None
        payload["expected_end"] = self.expected_end.isoformat() if self.expected_end else None
        payload["observed_first"] = self.observed_first.isoformat()
        payload["observed_last"] = self.observed_last.isoformat()
        payload["warnings"] = list(self.warnings)
        payload["largest_gaps"] = [gap.to_record() for gap in self.largest_gaps]
        payload["quality_model_version"] = QUALITY_MODEL_VERSION
        return payload

    @classmethod
    def from_record(cls, record: dict[str, object]) -> "SessionQuality":
        gaps = tuple(
            ObservedGap(
                start=datetime.fromisoformat(str(g["start"])),
                end=datetime.fromisoformat(str(g["end"])),
                seconds=float(g["seconds"]),
            )
            for g in list(record.get("largest_gaps") or [])
        )
        return cls(
            symbol=str(record["symbol"]),
            session_date=date.fromisoformat(str(record["session_date"])),
            schedule_id=str(record["schedule_id"]) if record.get("schedule_id") else None,
            schedule_label=str(record["schedule_label"]) if record.get("schedule_label") else None,
            expected_start=datetime.fromisoformat(str(record["expected_start"])) if record.get("expected_start") else None,
            expected_end=datetime.fromisoformat(str(record["expected_end"])) if record.get("expected_end") else None,
            observed_first=datetime.fromisoformat(str(record["observed_first"])),
            observed_last=datetime.fromisoformat(str(record["observed_last"])),
            expected_duration_seconds=float(record["expected_duration_seconds"]) if record.get("expected_duration_seconds") is not None else None,
            observed_span_seconds=float(record["observed_span_seconds"]),
            coverage_ratio=float(record["coverage_ratio"]) if record.get("coverage_ratio") is not None else None,
            active_minute_ratio=float(record["active_minute_ratio"]) if record.get("active_minute_ratio") is not None else None,
            start_delay_seconds=float(record["start_delay_seconds"]) if record.get("start_delay_seconds") is not None else None,
            end_early_seconds=float(record["end_early_seconds"]) if record.get("end_early_seconds") is not None else None,
            gap_threshold_seconds=float(record["gap_threshold_seconds"]),
            gap_count=int(record["gap_count"]),
            max_gap_seconds=float(record["max_gap_seconds"]),
            p95_intertrade_seconds=float(record["p95_intertrade_seconds"]),
            status=str(record["status"]),
            score=float(record["score"]),
            eligible_for_research=bool(record["eligible_for_research"]),
            warnings=tuple(str(x) for x in list(record.get("warnings") or [])),
            largest_gaps=gaps,
        )


SCHEDULES = {
    "WIN_CURRENT": ScheduleDefinition(
        schedule_id="B3_WIN_2025_03_10",
        label="WIN — negociação normal 09:00–18:25",
        open_time=time(9, 0),
        close_time=time(18, 25),
        effective_from=date(2025, 3, 10),
        source_note="B3: grade de derivativos vigente desde 10/03/2025; no vencimento do contrato vincendo, o encerramento pode ocorrer às 17:00.",
    ),
    "WDO_CURRENT": ScheduleDefinition(
        schedule_id="B3_WDO_2025_03_10",
        label="WDO — negociação normal 09:00–18:30",
        open_time=time(9, 0),
        close_time=time(18, 30),
        effective_from=date(2025, 3, 10),
        source_note="B3: grade de derivativos vigente desde 10/03/2025.",
    ),
    "WINLAB06": ScheduleDefinition(
        schedule_id="SYNTHETIC_WINLAB06_V1",
        label="Amostra interna — 10:00–10:12",
        open_time=time(10, 0),
        close_time=time(10, 12),
        effective_from=date(2026, 10, 1),
        source_note="Janela artificial usada exclusivamente pela amostra sintética do Candle Lab.",
    ),
}


def schedule_for_symbol(symbol: str, session_date: date) -> ScheduleDefinition | None:
    value = symbol.strip().upper()
    if value == "WINLAB06":
        schedule = SCHEDULES["WINLAB06"]
        return schedule if schedule.applies(session_date) else None
    if value.startswith("WIN"):
        schedule = SCHEDULES["WIN_CURRENT"]
        return schedule if schedule.applies(session_date) else None
    if value.startswith("WDO"):
        schedule = SCHEDULES["WDO_CURRENT"]
        return schedule if schedule.applies(session_date) else None
    return None


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lower = int(pos)
    upper = min(lower + 1, len(ordered) - 1)
    frac = pos - lower
    return ordered[lower] * (1 - frac) + ordered[upper] * frac


def _boundary_score(delay_seconds: float | None) -> float:
    if delay_seconds is None:
        return 0.0
    if delay_seconds <= 120:
        return 1.0
    return max(0.0, 1.0 - (delay_seconds - 120) / 780.0)


def assess_session_quality(trades: Iterable[Trade]) -> SessionQuality:
    ordered = sorted(trades, key=lambda t: (t.ts, t.sequence_no or 0, t.trade_id or ""))
    if not ordered:
        raise ValueError("Não é possível avaliar qualidade de um pregão sem negócios")
    symbols = {trade.symbol for trade in ordered}
    dates = {trade.ts.date() for trade in ordered}
    if len(symbols) != 1 or len(dates) != 1:
        raise ValueError("A avaliação de qualidade exige um único ativo e um único pregão")

    symbol = ordered[0].symbol
    session_date = ordered[0].ts.date()
    observed_first = ordered[0].ts
    observed_last = ordered[-1].ts
    observed_span = max(0.0, (observed_last - observed_first).total_seconds())
    schedule = schedule_for_symbol(symbol, session_date)

    intervals = [max(0.0, (b.ts - a.ts).total_seconds()) for a, b in zip(ordered, ordered[1:])]
    p95 = _percentile(intervals, 0.95)
    gap_threshold = max(60.0, min(300.0, max(1.0, p95) * 20.0))
    gaps = [ObservedGap(a.ts, b.ts, delta) for a, b, delta in zip(ordered, ordered[1:], intervals) if delta > gap_threshold]
    largest_gaps = tuple(sorted(gaps, key=lambda g: g.seconds, reverse=True)[:8])
    max_gap = max(intervals, default=0.0)

    warnings: list[str] = []
    if schedule is None:
        warnings.append("Não há grade nominal cadastrada para este ativo/data; a cobertura de sessão não pode ser certificada.")
        return SessionQuality(
            symbol=symbol, session_date=session_date, schedule_id=None, schedule_label=None,
            expected_start=None, expected_end=None, observed_first=observed_first, observed_last=observed_last,
            expected_duration_seconds=None, observed_span_seconds=observed_span, coverage_ratio=None,
            active_minute_ratio=None, start_delay_seconds=None, end_early_seconds=None,
            gap_threshold_seconds=gap_threshold, gap_count=len(gaps), max_gap_seconds=max_gap,
            p95_intertrade_seconds=p95, status="UNKNOWN_SCHEDULE", score=50.0 if not gaps else 40.0,
            eligible_for_research=False, warnings=tuple(warnings), largest_gaps=largest_gaps,
        )

    tz = observed_first.tzinfo
    expected_start = datetime.combine(session_date, schedule.open_time, tzinfo=tz)
    expected_end = datetime.combine(session_date, schedule.close_time, tzinfo=tz)
    expected_duration = max(1.0, (expected_end - expected_start).total_seconds())
    intersection_start = max(observed_first, expected_start)
    intersection_end = min(observed_last, expected_end)
    covered_span = max(0.0, (intersection_end - intersection_start).total_seconds())
    coverage_ratio = min(1.0, covered_span / expected_duration)
    start_delay = max(0.0, (observed_first - expected_start).total_seconds())
    end_early = max(0.0, (expected_end - observed_last).total_seconds())

    expected_minutes = max(1, int((expected_duration + 59) // 60))
    active_minutes: set[int] = set()
    for trade in ordered:
        if expected_start <= trade.ts < expected_end:
            minute_index = int((trade.ts - expected_start).total_seconds() // 60)
            if 0 <= minute_index < expected_minutes:
                active_minutes.add(minute_index)
    active_ratio = min(1.0, len(active_minutes) / expected_minutes)

    gap_excess = sum(max(0.0, gap.seconds - gap_threshold) for gap in gaps)
    gap_score = max(0.0, 1.0 - gap_excess / max(expected_duration * 0.08, 1.0))
    score = 100.0 * (
        0.35 * coverage_ratio
        + 0.18 * _boundary_score(start_delay)
        + 0.18 * _boundary_score(end_early)
        + 0.19 * active_ratio
        + 0.10 * gap_score
    )
    score = round(max(0.0, min(100.0, score)), 1)

    missing_start = start_delay > 300
    missing_end = end_early > 300
    severe_gaps = max_gap > 300 or active_ratio < 0.90

    if missing_start and missing_end:
        status = "PARTIAL_BOTH"
    elif missing_start:
        status = "PARTIAL_START"
    elif missing_end:
        status = "PARTIAL_END"
    elif severe_gaps:
        status = "GAPPED"
    elif coverage_ratio >= 0.985 and active_ratio >= 0.97 and score >= 94:
        status = "COMPLETE"
    elif coverage_ratio >= 0.965 and active_ratio >= 0.94 and score >= 88:
        status = "LIKELY_COMPLETE"
    else:
        status = "REVIEW"

    if start_delay > 120:
        warnings.append(f"Primeiro negócio observado {start_delay/60:.1f} min após a abertura nominal.")
    if end_early > 120:
        warnings.append(f"Último negócio observado {end_early/60:.1f} min antes do encerramento nominal.")
    if gaps:
        warnings.append(f"Foram observadas {len(gaps)} lacuna(s) entre negócios acima de {gap_threshold:.0f}s; isso pode refletir ausência de dados ou pausa real de negociação.")
    if symbol.startswith("WIN") and symbol != "WINLAB06":
        warnings.append("No vencimento do contrato vincendo, a B3 prevê encerramento antecipado do WIN às 17:00; a v0.7 ainda não infere automaticamente a data de vencimento.")

    eligible = status in {"COMPLETE", "LIKELY_COMPLETE"} and score >= 88.0
    return SessionQuality(
        symbol=symbol, session_date=session_date, schedule_id=schedule.schedule_id, schedule_label=schedule.label,
        expected_start=expected_start, expected_end=expected_end, observed_first=observed_first, observed_last=observed_last,
        expected_duration_seconds=expected_duration, observed_span_seconds=observed_span, coverage_ratio=coverage_ratio,
        active_minute_ratio=active_ratio, start_delay_seconds=start_delay, end_early_seconds=end_early,
        gap_threshold_seconds=gap_threshold, gap_count=len(gaps), max_gap_seconds=max_gap, p95_intertrade_seconds=p95,
        status=status, score=score, eligible_for_research=eligible, warnings=tuple(warnings), largest_gaps=largest_gaps,
    )


def assess_library_quality(trades: Iterable[Trade]) -> list[SessionQuality]:
    grouped: dict[tuple[str, date], list[Trade]] = {}
    for trade in trades:
        grouped.setdefault((trade.symbol, trade.ts.date()), []).append(trade)
    return [assess_session_quality(grouped[key]) for key in sorted(grouped)]
