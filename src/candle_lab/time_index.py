from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable

from .importers import _parse_datetime
from .slice import _probe, source_fingerprint


INDEX_VERSION = "1.1"
INDEX_GRANULARITY_SECONDS = 60


@dataclass(frozen=True, slots=True)
class MinuteLocator:
    start: str
    end: str
    first_source_row: int
    last_source_row: int
    byte_start: int
    byte_end: int
    trades: int
    first_physical_timestamp: str
    last_physical_timestamp: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TimeIndex:
    version: str
    source_path: str
    source_size: int
    source_mtime_ns: int
    source_fingerprint: str
    source_sha256: str
    symbol: str
    source_order: str
    encoding: str
    delimiter: str
    granularity_seconds: int
    layout_profile: str
    source_has_header: bool
    source_header_line: int
    rows: int
    first_timestamp: str
    last_timestamp: str
    buckets: tuple[MinuteLocator, ...]
    index_path: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["buckets"] = [item.to_dict() for item in self.buckets]
        return payload


def _floor_minute(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


def _default_index_path(source: Path, index_dir: str | Path, fingerprint: str) -> Path:
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in source.stem)[:80]
    return Path(index_dir).resolve() / f"{safe_name}_{fingerprint[:16]}.cidx.json"


def _load_index(path: Path) -> TimeIndex:
    payload = json.loads(path.read_text(encoding="utf-8"))
    buckets = tuple(MinuteLocator(**item) for item in payload.pop("buckets"))
    return TimeIndex(**payload, buckets=buckets)


def _index_is_current(index: TimeIndex, source: Path, fingerprint: str) -> bool:
    stat = source.stat()
    return (
        index.version == INDEX_VERSION
        and index.source_size == stat.st_size
        and index.source_mtime_ns == stat.st_mtime_ns
        and index.source_fingerprint == fingerprint
        and index.granularity_seconds == INDEX_GRANULARITY_SECONDS
    )


def build_time_index(
    source_path: str | Path,
    *,
    index_dir: str | Path = "data/indexes",
    symbol: str | None = None,
    progress: Callable[[dict[str, object]], None] | None = None,
) -> TimeIndex:
    source = Path(str(source_path).strip().strip('"')).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {source}")
    if source.suffix.lower() != ".csv":
        raise ValueError("O arquivo de Trades precisa possuir extensão .csv")

    probe = _probe(source, symbol=symbol)
    encoding, dialect = probe.encoding, probe.dialect
    layout, source_order, file_symbol = probe.layout, probe.source_order, probe.symbol
    symbol_used = (symbol or file_symbol).strip().upper()
    if file_symbol and symbol_used != file_symbol:
        raise ValueError(f"Ativo informado ({symbol_used}) difere do arquivo ({file_symbol})")

    fingerprint = source_fingerprint(source)
    output = _default_index_path(source, index_dir, fingerprint)
    output.parent.mkdir(parents=True, exist_ok=True)

    stat = source.stat()
    digest = hashlib.sha256()
    buckets: dict[str, dict[str, object]] = {}
    rows = 0
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    last_progress_byte = 0
    progress_step_bytes = 8 * 1024 * 1024

    physical_line = 0
    with source.open("rb") as handle:
        while True:
            byte_start = handle.tell()
            raw = handle.readline()
            if not raw:
                break
            byte_end = handle.tell()
            digest.update(raw)
            physical_line += 1

            decoded = raw.decode(encoding).rstrip("\r\n")
            if not decoded.strip():
                continue
            row = next(csv.reader([decoded], dialect=dialect))
            if not row or not any(cell.strip() for cell in row):
                continue
            if physical_line < layout.data_start_line:
                continue
            if layout.has_header and physical_line == layout.header_line:
                continue

            try:
                ts = layout.timestamp(row)
            except (ValueError, IndexError) as exc:
                raise ValueError(f"Linha física {physical_line}: data/hora inválida: {exc}") from exc

            row_symbol = layout.symbol(row) or symbol_used
            if row_symbol != symbol_used:
                raise ValueError(f"Linha física {physical_line}: ativo {row_symbol} difere de {symbol_used}")
            rows += 1
            if first_ts is None or ts < first_ts:
                first_ts = ts
            if last_ts is None or ts > last_ts:
                last_ts = ts

            bucket_start = _floor_minute(ts)
            key = bucket_start.isoformat()
            item = buckets.get(key)
            if item is None:
                buckets[key] = {
                    "start": key,
                    "end": (bucket_start + timedelta(minutes=1)).isoformat(),
                    "first_source_row": physical_line,
                    "last_source_row": physical_line,
                    "byte_start": byte_start,
                    "byte_end": byte_end,
                    "trades": 1,
                    "first_physical_timestamp": ts.isoformat(),
                    "last_physical_timestamp": ts.isoformat(),
                }
            else:
                item["last_source_row"] = physical_line
                item["byte_end"] = byte_end
                item["trades"] = int(item["trades"]) + 1
                item["last_physical_timestamp"] = ts.isoformat()

            if progress and byte_end - last_progress_byte >= progress_step_bytes:
                progress({
                    "phase": "index",
                    "rows": rows,
                    "bytes_processed": byte_end,
                    "bytes_total": stat.st_size,
                    "percent": round(byte_end / max(stat.st_size, 1) * 100, 2),
                    "minutes_indexed": len(buckets),
                })
                last_progress_byte = byte_end

    if progress:
        progress({
            "phase": "index",
            "rows": rows,
            "bytes_processed": stat.st_size,
            "bytes_total": stat.st_size,
            "percent": 100.0,
            "minutes_indexed": len(buckets),
        })

    if not rows or first_ts is None or last_ts is None:
        raise ValueError("Nenhuma linha válida encontrada no CSV")

    final_stat = source.stat()
    if final_stat.st_size != stat.st_size or final_stat.st_mtime_ns != stat.st_mtime_ns:
        raise RuntimeError(
            "O CSV foi alterado durante a indexação. Feche qualquer programa que esteja modificando "
            "o arquivo e execute a preparação do índice novamente."
        )

    # Mantemos ordem cronológica no arquivo de índice, independentemente da ordem física da fonte.
    minute_entries = tuple(MinuteLocator(**buckets[key]) for key in sorted(buckets))
    index = TimeIndex(
        version=INDEX_VERSION,
        source_path=str(source),
        source_size=stat.st_size,
        source_mtime_ns=stat.st_mtime_ns,
        source_fingerprint=fingerprint,
        source_sha256=digest.hexdigest(),
        symbol=symbol_used,
        source_order=source_order,
        encoding=encoding,
        delimiter=dialect.delimiter,
        granularity_seconds=INDEX_GRANULARITY_SECONDS,
        layout_profile=layout.profile,
        source_has_header=layout.has_header,
        source_header_line=layout.header_line,
        rows=rows,
        first_timestamp=first_ts.isoformat(),
        last_timestamp=last_ts.isoformat(),
        buckets=minute_entries,
        index_path=str(output),
    )
    output.write_text(json.dumps(index.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def ensure_time_index(
    source_path: str | Path,
    *,
    index_dir: str | Path = "data/indexes",
    symbol: str | None = None,
    progress: Callable[[dict[str, object]], None] | None = None,
) -> tuple[TimeIndex, bool]:
    source = Path(str(source_path).strip().strip('"')).expanduser().resolve()
    fingerprint = source_fingerprint(source)
    path = _default_index_path(source, index_dir, fingerprint)
    if path.exists():
        try:
            index = _load_index(path)
            if _index_is_current(index, source, fingerprint):
                if symbol and index.symbol != symbol.strip().upper():
                    raise ValueError(f"Ativo informado ({symbol}) difere do índice ({index.symbol})")
                return index, False
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            pass
    return build_time_index(source, index_dir=index_dir, symbol=symbol, progress=progress), True


def _bucket_map(index: TimeIndex) -> dict[datetime, MinuteLocator]:
    return {datetime.fromisoformat(item.start): item for item in index.buckets}


def locate_interval(index: TimeIndex, *, start: datetime, end: datetime) -> dict[str, object]:
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start e end precisam possuir timezone")
    if end <= start:
        raise ValueError("O final do intervalo deve ser posterior ao início")
    if start.second or start.microsecond or end.second or end.microsecond:
        raise ValueError(
            "O índice M1 localiza intervalos alinhados ao minuto. "
            "Selecione candles do gráfico para obter limites :00 exatos."
        )

    selected = [
        item for item in index.buckets
        if datetime.fromisoformat(item.end) > start and datetime.fromisoformat(item.start) < end
    ]
    if not selected:
        raise ValueError("O índice não possui negócios no intervalo solicitado")

    source_row_min = min(item.first_source_row for item in selected)
    source_row_max = max(item.last_source_row for item in selected)
    byte_start = min(item.byte_start for item in selected)
    byte_end = max(item.byte_end for item in selected)
    trades = sum(item.trades for item in selected)

    if index.source_order == "DESCENDING":
        chronological_open_row = source_row_max
        chronological_close_row = source_row_min
    else:
        chronological_open_row = source_row_min
        chronological_close_row = source_row_max

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "source_row_min": source_row_min,
        "source_row_max": source_row_max,
        "chronological_open_row": chronological_open_row,
        "chronological_close_row": chronological_close_row,
        "byte_start": byte_start,
        "byte_end": byte_end,
        "byte_length": byte_end - byte_start,
        "trades": trades,
        "minute_buckets": len(selected),
        "source_order": index.source_order,
    }


def locate_candles(
    index: TimeIndex,
    *,
    candle_starts: Iterable[datetime],
    interval_seconds: int,
) -> list[dict[str, object]]:
    if interval_seconds <= 0:
        raise ValueError("interval_seconds deve ser > 0")
    if interval_seconds % INDEX_GRANULARITY_SECONDS != 0:
        raise ValueError(
            "O índice temporal v0.13 é M1. O mapeamento exato de linhas aceita "
            "timeframes múltiplos de 60 segundos (M1/M2/M5/M15 etc.)."
        )
    result = []
    for candle_start in candle_starts:
        candle_end = candle_start + timedelta(seconds=interval_seconds)
        try:
            located = locate_interval(index, start=candle_start, end=candle_end)
        except ValueError:
            located = {
                "start": candle_start.isoformat(),
                "end": candle_end.isoformat(),
                "status": "NO_TRADES",
                "source_row_min": None,
                "source_row_max": None,
                "chronological_open_row": None,
                "chronological_close_row": None,
                "byte_start": None,
                "byte_end": None,
                "byte_length": 0,
                "trades": 0,
                "minute_buckets": 0,
                "source_order": index.source_order,
            }
        else:
            located["status"] = "FOUND"
        result.append(located)
    return result


def index_summary(index: TimeIndex) -> dict[str, object]:
    return {
        "version": index.version,
        "index_path": index.index_path,
        "symbol": index.symbol,
        "source_order": index.source_order,
        "source_size": index.source_size,
        "source_sha256": index.source_sha256,
        "rows": index.rows,
        "minutes_indexed": len(index.buckets),
        "first_timestamp": index.first_timestamp,
        "last_timestamp": index.last_timestamp,
        "granularity_seconds": index.granularity_seconds,
        "layout_profile": index.layout_profile,
        "source_has_header": index.source_has_header,
        "source_header_line": index.source_header_line,
    }
