from __future__ import annotations

import csv
import hashlib
import json
import time
import tracemalloc
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Callable, Iterable

from .importers import (
    _aggressor,
    _decimal_number,
    _detect_dialect,
    _detect_encoding,
    _looks_like_profit_headerless_trade,
    _parse_datetime,
)
from .models import AggressorSide
from .reconciliation import ReferenceCandle
from .storage import MarketStore


ProgressCallback = Callable[[dict[str, object]], None]


@dataclass(frozen=True, slots=True)
class BulkImportResult:
    file_hash: str
    file_name: str
    file_size: int
    symbol: str
    source_order: str
    status: str
    processed_rows: int
    inserted_rows: int
    resumed_from_row: int
    first_timestamp: str | None
    last_timestamp: str | None
    elapsed_seconds: float
    python_peak_memory_mb: float
    aggressor_known_pct: float
    rlp_rows: int
    already_imported: bool
    session_dates: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def sha256_file(path: str | Path, block_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            block = handle.read(block_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _probe_profit_file(path: Path, max_rows: int = 2048) -> dict[str, object]:
    encoding = _detect_encoding(path)
    with path.open("r", encoding=encoding, newline="") as handle:
        sample = handle.read(8192)
    dialect = _detect_dialect(sample)

    timestamps: list[datetime] = []
    symbols: set[str] = set()
    rows = 0
    with path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.reader(handle, dialect=dialect)
        for row in reader:
            if not row or not any(cell.strip() for cell in row):
                continue
            if rows == 0 and not _looks_like_profit_headerless_trade(row):
                raise ValueError(
                    "A importação massiva v0.11 aceita o layout real de Trades do Profit "
                    "sem cabeçalho e com 8 colunas. Use o importador normal para outros layouts."
                )
            if len(row) != 8:
                raise ValueError(f"Layout inesperado: linha de amostra possui {len(row)} colunas, esperado=8")
            symbols.add(row[0].strip().upper())
            timestamps.append(_parse_datetime(None, row[1], row[2]))
            rows += 1
            if rows >= max_rows:
                break

    if not timestamps:
        raise ValueError("Arquivo de Trades vazio")
    if len(symbols) != 1:
        raise ValueError(f"O arquivo parece conter mais de um ativo: {', '.join(sorted(symbols))}")

    asc = desc = 0
    for a, b in zip(timestamps, timestamps[1:]):
        if b > a:
            asc += 1
        elif b < a:
            desc += 1
    if desc and not asc:
        source_order = "DESCENDING"
    elif asc and not desc:
        source_order = "ASCENDING"
    elif not asc and not desc:
        source_order = "SAME_TIMESTAMP"
    else:
        source_order = "MIXED"

    if source_order not in {"ASCENDING", "DESCENDING"}:
        raise ValueError(
            f"A ordem temporal da amostra é {source_order}. Para ingestão massiva segura, "
            "o arquivo precisa estar monotonicamente crescente ou decrescente."
        )

    return {
        "encoding": encoding,
        "dialect": dialect,
        "symbol": next(iter(symbols)),
        "source_order": source_order,
    }


def _bulk_row(
    row: list[str],
    *,
    row_no: int,
    symbol_override: str,
    tick_size: Decimal,
    source: str,
    file_hash: str,
    source_order: str,
) -> tuple[object, ...]:
    if len(row) != 8:
        raise ValueError(f"Linha {row_no}: esperado layout Profit de 8 colunas; recebido={len(row)}")

    file_symbol = row[0].strip().upper()
    symbol = symbol_override or file_symbol
    if symbol_override and file_symbol != symbol_override:
        raise ValueError(
            f"Linha {row_no}: ativo do arquivo ({file_symbol}) difere do ativo informado ({symbol_override})"
        )

    ts = _parse_datetime(None, row[1], row[2])
    price = _decimal_number(row[4])
    ratio = price / tick_size
    price_ticks = int(ratio.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if abs(ratio - Decimal(price_ticks)) > Decimal("0.000001"):
        raise ValueError(f"Linha {row_no}: preço {price} não é múltiplo do tick {tick_size}")

    try:
        quantity = int(row[5].strip())
    except ValueError as exc:
        raise ValueError(f"Linha {row_no}: quantidade inválida: {row[5]}") from exc
    if quantity <= 0:
        raise ValueError(f"Linha {row_no}: quantidade deve ser positiva")

    raw_aggressor = row[7].strip()
    aggressor = _aggressor(raw_aggressor)
    # O export real recebido estava descendente. sequence_no negativo permite que
    # ORDER BY ts, sequence_no reproduza a reversão do arquivo sem carregar tudo na RAM.
    sequence_no = -row_no if source_order == "DESCENDING" else row_no
    event_key = hashlib.sha256(f"{file_hash}:{row_no}".encode()).hexdigest()
    flags = f"raw_aggressor={raw_aggressor}" if raw_aggressor else None

    return (
        event_key,
        symbol,
        ts,
        ts.date(),
        price_ticks,
        quantity,
        None,
        aggressor.value,
        source,
        row[3].strip() or None,
        row[6].strip() or None,
        sequence_no,
        flags,
        file_hash,
        row_no,
    )


def _ensure_bulk_row(con, *, file_hash: str, file_name: str, file_path: str, file_size: int,
                     source: str, symbol: str, tick_size: float, source_order: str) -> dict[str, object]:
    row = con.execute(
        """SELECT file_hash,status,processed_rows,inserted_rows,byte_offset,first_ts,last_ts,
                  elapsed_seconds,diagnostics_json
           FROM bulk_imports WHERE file_hash=?""",
        [file_hash],
    ).fetchone()
    if row:
        return {
            "file_hash": row[0], "status": row[1], "processed_rows": int(row[2] or 0),
            "inserted_rows": int(row[3] or 0), "byte_offset": int(row[4] or 0),
            "first_ts": row[5], "last_ts": row[6], "elapsed_seconds": float(row[7] or 0.0),
            "diagnostics": json.loads(row[8] or "{}"),
        }

    con.execute(
        """INSERT INTO bulk_imports(
            file_hash,file_name,file_path,file_size,source,symbol,tick_size,source_order,status,
            processed_rows,inserted_rows,byte_offset,first_ts,last_ts,elapsed_seconds,diagnostics_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [file_hash,file_name,file_path,file_size,source,symbol,tick_size,source_order,"PENDING",
         0,0,0,None,None,0.0,"{}"],
    )
    return {
        "file_hash": file_hash, "status": "PENDING", "processed_rows": 0,
        "inserted_rows": 0, "byte_offset": 0, "first_ts": None, "last_ts": None,
        "elapsed_seconds": 0.0, "diagnostics": {},
    }


def bulk_import_profit_file(
    path: str | Path,
    *,
    store: MarketStore,
    tick_size: float,
    symbol: str | None = None,
    source: str = "profit_bulk_csv",
    chunk_rows: int = 100_000,
    resume: bool = True,
    progress: ProgressCallback | None = None,
) -> BulkImportResult:
    path = Path(str(path).strip().strip('"')).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    if path.suffix.lower() != ".csv":
        raise ValueError("A importação massiva aceita arquivos .csv")

    if tick_size <= 0:
        raise ValueError("tick_size deve ser > 0")
    if chunk_rows < 1_000:
        raise ValueError("chunk_rows deve ser >= 1000")

    probe = _probe_profit_file(path)
    file_symbol = str(probe["symbol"])
    symbol_used = (symbol or file_symbol).strip().upper()
    if symbol and symbol_used != file_symbol:
        raise ValueError(f"Ativo informado ({symbol_used}) difere do arquivo ({file_symbol})")

    source_order = str(probe["source_order"])
    encoding = str(probe["encoding"])
    dialect = probe["dialect"]
    file_size = path.stat().st_size

    if progress:
        progress({"phase": "hash", "message": "Calculando SHA-256 do arquivo...", "bytes_total": file_size})
    file_hash = sha256_file(path)

    started = time.perf_counter()
    tracemalloc.start()

    warnings = [
        "O layout Profit observado possui timestamp com precisão de 1 segundo e não contém Número do Negócio.",
        "Ocorrências textualmente idênticas são preservadas; não há deduplicação por conteúdo.",
    ]
    if source_order == "DESCENDING":
        warnings.append(
            "Arquivo em ordem mais recente → mais antigo. sequence_no negativo preserva a reversão "
            "da ordem relativa intrassegundo sem materializar o arquivo inteiro."
        )

    with store.connect() as con:
        state = _ensure_bulk_row(
            con,
            file_hash=file_hash,
            file_name=path.name,
            file_path=str(path),
            file_size=file_size,
            source=source,
            symbol=symbol_used,
            tick_size=tick_size,
            source_order=source_order,
        )
        if state["status"] == "COMPLETED":
            peak = tracemalloc.get_traced_memory()[1] / 1024 / 1024
            tracemalloc.stop()
            diagnostics = dict(state.get("diagnostics") or {})
            return BulkImportResult(
                file_hash=file_hash, file_name=path.name, file_size=file_size, symbol=symbol_used,
                source_order=source_order, status="COMPLETED",
                processed_rows=int(state["processed_rows"]), inserted_rows=int(state["inserted_rows"]),
                resumed_from_row=int(state["processed_rows"]),
                first_timestamp=state.get("first_ts"), last_timestamp=state.get("last_ts"),
                elapsed_seconds=float(state.get("elapsed_seconds") or 0.0),
                python_peak_memory_mb=round(peak, 2),
                aggressor_known_pct=float(diagnostics.get("aggressor_known_pct", 0.0)),
                rlp_rows=int(diagnostics.get("rlp_rows", 0)),
                already_imported=True,
                session_dates=list(diagnostics.get("session_dates") or []),
                warnings=list(diagnostics.get("warnings") or warnings),
            )

        if not resume and int(state["processed_rows"]) > 0:
            raise ValueError(
                "Já existe uma importação parcial deste mesmo arquivo. Use resume=True "
                "ou remova explicitamente o lote parcial antes de reiniciar."
            )

        processed_rows = int(state["processed_rows"] or 0)
        inserted_rows = int(state["inserted_rows"] or 0)
        byte_offset = int(state["byte_offset"] or 0)
        resumed_from_row = processed_rows
        previous_elapsed = float(state["elapsed_seconds"] or 0.0)
        first_ts = state.get("first_ts")
        last_ts = state.get("last_ts")
        existing_diag = dict(state.get("diagnostics") or {})
        known_aggressor = int(existing_diag.get("known_aggressor_rows", 0))
        rlp_rows = int(existing_diag.get("rlp_rows", 0))
        session_dates = set(existing_diag.get("session_dates") or [])

        con.execute(
            """INSERT INTO instruments(symbol,tick_size) VALUES (?,?)
               ON CONFLICT(symbol) DO UPDATE SET tick_size=excluded.tick_size,updated_at=now()""",
            [symbol_used, tick_size],
        )
        con.execute(
            """UPDATE bulk_imports SET status='RUNNING',updated_at=now()
               WHERE file_hash=?""",
            [file_hash],
        )

        tick = Decimal(str(tick_size))
        insert_sql = """INSERT INTO trades(
            event_key,symbol,ts,session_date,price_ticks,quantity,trade_id,aggressor,source,
            buyer_id,seller_id,sequence_no,flags,source_file_hash,source_row
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(event_key) DO NOTHING"""

        try:
            with path.open("rb") as binary:
                binary.seek(byte_offset)
                while True:
                    raw_lines: list[bytes] = []
                    for _ in range(chunk_rows):
                        raw = binary.readline()
                        if not raw:
                            break
                        raw_lines.append(raw)
                    if not raw_lines:
                        break

                    next_offset = binary.tell()
                    rows: list[tuple[object, ...]] = []
                    reader = csv.reader(
                        (raw.decode(encoding).rstrip("\r\n") for raw in raw_lines),
                        dialect=dialect,
                    )
                    local_row = processed_rows
                    for row in reader:
                        if not row or not any(cell.strip() for cell in row):
                            continue
                        local_row += 1
                        parsed = _bulk_row(
                            row,
                            row_no=local_row,
                            symbol_override=symbol_used,
                            tick_size=tick,
                            source=source,
                            file_hash=file_hash,
                            source_order=source_order,
                        )
                        rows.append(parsed)
                        ts = parsed[2]
                        assert isinstance(ts, datetime)
                        iso = ts.isoformat()
                        first_ts = iso if first_ts is None or iso < str(first_ts) else first_ts
                        last_ts = iso if last_ts is None or iso > str(last_ts) else last_ts
                        session_dates.add(ts.date().isoformat())
                        raw_agg = row[7].strip()
                        if _aggressor(raw_agg) != AggressorSide.NONE:
                            known_aggressor += 1
                        if raw_agg.upper() == "RLP":
                            rlp_rows += 1

                    if rows:
                        con.execute("BEGIN TRANSACTION")
                        try:
                            con.executemany(insert_sql, rows)
                            inserted_rows += len(rows)
                            processed_rows = local_row
                            elapsed = previous_elapsed + (time.perf_counter() - started)
                            diagnostics = {
                                "encoding": encoding,
                                "source_order": source_order,
                                "known_aggressor_rows": known_aggressor,
                                "aggressor_known_pct": round(known_aggressor / max(processed_rows, 1) * 100, 2),
                                "rlp_rows": rlp_rows,
                                "session_dates": sorted(session_dates),
                                "warnings": warnings,
                            }
                            con.execute(
                                """UPDATE bulk_imports SET processed_rows=?,inserted_rows=?,byte_offset=?,
                                   first_ts=?,last_ts=?,elapsed_seconds=?,diagnostics_json=?,updated_at=now()
                                   WHERE file_hash=?""",
                                [processed_rows,inserted_rows,next_offset,first_ts,last_ts,elapsed,
                                 json.dumps(diagnostics,ensure_ascii=False),file_hash],
                            )
                            con.execute("COMMIT")
                        except Exception:
                            con.execute("ROLLBACK")
                            raise

                    if progress:
                        progress({
                            "phase": "import",
                            "processed_rows": processed_rows,
                            "inserted_rows": inserted_rows,
                            "bytes_processed": next_offset,
                            "bytes_total": file_size,
                            "percent": round(next_offset / max(file_size, 1) * 100, 2),
                            "resumed_from_row": resumed_from_row,
                        })

            elapsed = previous_elapsed + (time.perf_counter() - started)
            diagnostics = {
                "encoding": encoding,
                "source_order": source_order,
                "known_aggressor_rows": known_aggressor,
                "aggressor_known_pct": round(known_aggressor / max(processed_rows, 1) * 100, 2),
                "rlp_rows": rlp_rows,
                "session_dates": sorted(session_dates),
                "warnings": warnings,
            }
            con.execute(
                """UPDATE bulk_imports SET status='COMPLETED',processed_rows=?,inserted_rows=?,
                   byte_offset=?,first_ts=?,last_ts=?,elapsed_seconds=?,diagnostics_json=?,
                   updated_at=now(),completed_at=now() WHERE file_hash=?""",
                [processed_rows,inserted_rows,file_size,first_ts,last_ts,elapsed,
                 json.dumps(diagnostics,ensure_ascii=False),file_hash],
            )
        except Exception as exc:
            elapsed = previous_elapsed + (time.perf_counter() - started)
            con.execute(
                """UPDATE bulk_imports SET status='FAILED',elapsed_seconds=?,
                   diagnostics_json=?,updated_at=now() WHERE file_hash=?""",
                [elapsed,json.dumps({"error":str(exc),"warnings":warnings},ensure_ascii=False),file_hash],
            )
            raise

    peak = tracemalloc.get_traced_memory()[1] / 1024 / 1024
    tracemalloc.stop()

    return BulkImportResult(
        file_hash=file_hash, file_name=path.name, file_size=file_size, symbol=symbol_used,
        source_order=source_order, status="COMPLETED", processed_rows=processed_rows,
        inserted_rows=inserted_rows, resumed_from_row=resumed_from_row,
        first_timestamp=str(first_ts) if first_ts else None, last_timestamp=str(last_ts) if last_ts else None,
        elapsed_seconds=round(elapsed, 3), python_peak_memory_mb=round(peak, 2),
        aggressor_known_pct=round(known_aggressor / max(processed_rows, 1) * 100, 2),
        rlp_rows=rlp_rows, already_imported=False, session_dates=sorted(session_dates), warnings=warnings,
    )


def aggregate_candles_sql(
    store: MarketStore, *, symbol: str, session_date: date | str, interval_seconds: int
) -> list[dict[str, object]]:
    if interval_seconds <= 0:
        raise ValueError("interval_seconds deve ser > 0")
    with store.connect() as con:
        rows = con.execute(
            """WITH base AS (
                SELECT
                    to_timestamp(floor(epoch(ts) / ?) * ?) AS start,
                    ts, sequence_no, price_ticks, quantity
                FROM trades
                WHERE symbol=? AND session_date=?
            )
            SELECT
                start,
                first(price_ticks ORDER BY ts ASC, sequence_no ASC) AS open_ticks,
                max(price_ticks) AS high_ticks,
                min(price_ticks) AS low_ticks,
                last(price_ticks ORDER BY ts ASC, sequence_no ASC) AS close_ticks,
                sum(quantity) AS volume,
                count(*) AS trades,
                min(ts) AS first_trade,
                max(ts) AS last_trade
            FROM base
            GROUP BY start
            ORDER BY start""",
            [interval_seconds, interval_seconds, symbol, str(session_date)],
        ).fetchall()
    return [
        {
            "start": row[0], "open_ticks": int(row[1]), "high_ticks": int(row[2]),
            "low_ticks": int(row[3]), "close_ticks": int(row[4]), "volume": int(row[5]),
            "trades": int(row[6]), "first_trade": row[7], "last_trade": row[8],
        }
        for row in rows
    ]


def _reference_is_complete(ref: ReferenceCandle, first_ts: datetime, last_ts: datetime) -> bool:
    tolerance = min(5.0, ref.interval_seconds * 0.10)
    first_bucket = ref.start <= first_ts < ref.end
    last_bucket = ref.start <= last_ts < ref.end
    if first_bucket and (first_ts - ref.start).total_seconds() > tolerance:
        return False
    if last_bucket and (last_ts - ref.start).total_seconds() < ref.interval_seconds - tolerance:
        return False
    return ref.start >= first_ts - timedelta(seconds=tolerance) and ref.end <= last_ts + timedelta(seconds=tolerance)


def reconcile_store_references(
    store: MarketStore,
    *,
    symbol: str,
    session_date: date | str,
    references: Iterable[ReferenceCandle],
    interval_seconds: int,
    tick_size: float,
) -> dict[str, object]:
    references = [r for r in references if r.symbol == symbol and str(r.start.date()) == str(session_date)]
    candles = aggregate_candles_sql(
        store, symbol=symbol, session_date=session_date, interval_seconds=interval_seconds
    )
    actual = {row["start"]: row for row in candles}

    with store.connect() as con:
        bounds = con.execute(
            "SELECT min(ts),max(ts),count(*),sum(quantity) FROM trades WHERE symbol=? AND session_date=?",
            [symbol, str(session_date)],
        ).fetchone()
    if not bounds or bounds[0] is None:
        raise ValueError("Nenhum trade armazenado para o pregão solicitado")
    first_ts, last_ts, trade_rows, total_quantity = bounds

    complete_refs = [r for r in references if _reference_is_complete(r, first_ts, last_ts)]
    partial_refs = [r for r in references if r not in complete_refs and r.end > first_ts and r.start <= last_ts]

    results: list[dict[str, object]] = []
    exact = ohlc_match = mismatch = no_data = 0
    for ref in complete_refs:
        row = actual.get(ref.start)
        if row is None:
            no_data += 1
            results.append({"start":ref.start.isoformat(),"status":"NO_DATA","checks":[]})
            continue
        checks = []
        price_ok = True
        for field in ("open","high","low","close"):
            delta = int(row[f"{field}_ticks"]) - int(getattr(ref, f"{field}_ticks"))
            checks.append({"field":field,"match":delta==0,"delta_ticks":delta,"delta_price":delta*tick_size})
            price_ok &= delta == 0
        optional_ok = True
        if ref.volume is not None:
            delta = int(row["volume"]) - int(ref.volume)
            checks.append({"field":"volume","match":delta==0,"delta":delta})
            optional_ok &= delta == 0
        if ref.trades is not None:
            delta = int(row["trades"]) - int(ref.trades)
            checks.append({"field":"trades","match":delta==0,"delta":delta})
            optional_ok &= delta == 0

        if price_ok and optional_ok:
            status = "EXACT"; exact += 1
        elif price_ok:
            status = "OHLC_MATCH"; ohlc_match += 1
        else:
            status = "MISMATCH"; mismatch += 1
        results.append({
            "start":ref.start.isoformat(),"status":status,"checks":checks,
            "actual":{"open":row["open_ticks"]*tick_size,"high":row["high_ticks"]*tick_size,
                      "low":row["low_ticks"]*tick_size,"close":row["close_ticks"]*tick_size,
                      "volume":row["volume"],"trades":row["trades"]},
            "reference":{"open":ref.open_ticks*tick_size,"high":ref.high_ticks*tick_size,
                         "low":ref.low_ticks*tick_size,"close":ref.close_ticks*tick_size,
                         "volume":ref.volume,"trades":ref.trades},
        })

    comparable = exact + ohlc_match + mismatch
    return {
        "symbol": symbol,
        "session_date": str(session_date),
        "interval_seconds": interval_seconds,
        "observed_window": {
            "first_trade": first_ts.isoformat(),
            "last_trade": last_ts.isoformat(),
            "trade_rows": int(trade_rows),
            "total_quantity": int(total_quantity),
            "partial_boundary_candles": len(partial_refs),
        },
        "summary": {
            "reference_candles": len(complete_refs),
            "reconstructed_candles": len(candles),
            "exact": exact,
            "ohlc_match": ohlc_match,
            "mismatch": mismatch,
            "no_data": no_data,
            "ohlc_match_rate": (exact + ohlc_match) / comparable if comparable else 0.0,
            "exact_rate": exact / comparable if comparable else 0.0,
        },
        "partial_boundary_references": [
            {"start":r.start.isoformat(),"end":r.end.isoformat(),"status":"PARTIAL_SOURCE_WINDOW"}
            for r in partial_refs
        ],
        "results": results,
    }


def export_session_parquet(
    store: MarketStore, *, symbol: str, session_date: date | str, output_dir: str | Path = "data/parquet"
) -> Path:
    output = Path(output_dir) / symbol / f"{session_date}.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    escaped = str(output.resolve()).replace("'", "''")
    with store.connect() as con:
        con.execute(
            f"""COPY (
                SELECT * FROM trades
                WHERE symbol=? AND session_date=?
                ORDER BY ts,sequence_no
            ) TO '{escaped}' (FORMAT PARQUET, COMPRESSION ZSTD)""",
            [symbol, str(session_date)],
        )
    return output
