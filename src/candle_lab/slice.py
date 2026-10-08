from __future__ import annotations

import csv
import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from .importers import _detect_dialect, _detect_encoding, _looks_like_profit_headerless_trade, _parse_datetime


@dataclass(frozen=True, slots=True)
class SliceResult:
    source_path: str
    output_path: str
    source_size: int
    output_size: int
    source_order: str
    symbol: str
    start: str
    end: str
    scanned_rows: int
    matched_rows: int
    stopped_early: bool
    source_fingerprint: str
    first_source_row: int
    last_source_row: int
    indexed_seek: bool
    source_byte_start: int
    source_byte_end: int
    sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _probe(path: Path, max_rows: int = 20_000) -> tuple[str, csv.Dialect, str, str]:
    encoding = _detect_encoding(path)
    with path.open("r", encoding=encoding, newline="") as handle:
        sample = handle.read(8192)
    dialect = _detect_dialect(sample)

    timestamps: list[datetime] = []
    symbols: set[str] = set()
    with path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.reader(handle, dialect=dialect)
        for row in reader:
            if not row or not any(cell.strip() for cell in row):
                continue
            if not timestamps and not _looks_like_profit_headerless_trade(row):
                raise ValueError(
                    "O recorte seletivo v0.12 espera o layout real de Trades do Profit sem cabeçalho e com 8 colunas."
                )
            if len(row) != 8:
                raise ValueError(f"Layout inesperado: {len(row)} colunas; esperado=8")
            symbols.add(row[0].strip().upper())
            timestamps.append(_parse_datetime(None, row[1], row[2]))
            distinct_times=len({ts for ts in timestamps})
            if len(timestamps) >= 2048 and distinct_times >= 3:
                break
            if len(timestamps) >= max_rows:
                break

    if not timestamps:
        raise ValueError("Arquivo de Trades vazio")
    if len(symbols) != 1:
        raise ValueError(f"O arquivo contém mais de um ativo: {', '.join(sorted(symbols))}")

    asc = desc = 0
    for left, right in zip(timestamps, timestamps[1:]):
        if right > left:
            asc += 1
        elif right < left:
            desc += 1
    if desc and not asc:
        order = "DESCENDING"
    elif asc and not desc:
        order = "ASCENDING"
    elif not asc and not desc:
        order = "SAME_TIMESTAMP"
    else:
        order = "MIXED"
    if order not in {"ASCENDING", "DESCENDING"}:
        raise ValueError(f"Ordem temporal {order}; o recorte seletivo exige arquivo monotônico.")
    return encoding, dialect, next(iter(symbols)), order


def source_fingerprint(path: str | Path, block_size: int = 1024 * 1024) -> str:
    """Identidade rápida da fonte sem reler todo o CSV.

    Usa tamanho + primeiro/último bloco. Serve para idempotência dos recortes;
    não é apresentado como SHA-256 integral do arquivo original.
    """
    path = Path(path).resolve()
    stat = path.stat()
    digest = hashlib.sha256()
    digest.update(str(stat.st_size).encode())
    with path.open("rb") as handle:
        digest.update(handle.read(block_size))
        if stat.st_size > block_size:
            handle.seek(max(0, stat.st_size - block_size))
            digest.update(handle.read(block_size))
    return digest.hexdigest()


def _sha256(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(block_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def slice_profit_trades(
    source_path: str | Path,
    *,
    start: datetime,
    end: datetime,
    output_path: str | Path | None = None,
    symbol: str | None = None,
    progress: Callable[[dict[str, object]], None] | None = None,
    seek_byte_start: int | None = None,
    seek_byte_end: int | None = None,
    source_row_base: int = 0,
) -> SliceResult:
    """Extrai [start, end) do CSV original sem carregar o arquivo inteiro em memória."""
    source = Path(str(source_path).strip().strip('"')).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {source}")
    if source.suffix.lower() != ".csv":
        raise ValueError("O arquivo de Trades precisa ser .csv")
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start e end precisam possuir timezone")
    if end <= start:
        raise ValueError("O final do intervalo deve ser posterior ao início")

    encoding, dialect, file_symbol, source_order = _probe(source)
    symbol_used = (symbol or file_symbol).strip().upper()
    if symbol_used != file_symbol:
        raise ValueError(f"Ativo informado ({symbol_used}) difere do arquivo ({file_symbol})")

    if output_path is None:
        safe_start = start.strftime("%Y%m%d-%H%M%S")
        safe_end = end.strftime("%H%M%S")
        output = Path("data/slices") / f"{symbol_used}_{safe_start}_{safe_end}_TRADES.csv"
    else:
        output = Path(output_path)
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    scanned = matched = 0
    source_row = int(source_row_base)
    stopped_early = False
    first_source_row = 0
    last_source_row = 0
    source_size = source.stat().st_size
    source_id = source_fingerprint(source)
    indexed_seek = seek_byte_start is not None
    byte_begin = int(seek_byte_start or 0)
    byte_limit = int(seek_byte_end) if seek_byte_end is not None else source_size

    # O caminho indexado abre em binário para que tell/seek usem offsets físicos exatos.
    with source.open("rb") as src, output.open("w", encoding=encoding, newline="") as dst:
        if byte_begin:
            src.seek(byte_begin)
        writer = csv.writer(dst, dialect=dialect)
        while src.tell() < byte_limit:
            raw = src.readline()
            if not raw:
                break
            scanned += 1
            source_row += 1
            decoded = raw.decode(encoding).rstrip("\r\n")
            if not decoded.strip():
                continue
            row = next(csv.reader([decoded], dialect=dialect))
            if not row or not any(cell.strip() for cell in row):
                continue
            if len(row) != 8:
                raise ValueError(f"Linha-fonte {source_row}: esperado=8 colunas; recebido={len(row)}")
            ts = _parse_datetime(None, row[1], row[2])

            include = False
            if source_order == "DESCENDING":
                if ts >= end:
                    include = False
                elif ts < start:
                    stopped_early = True
                    break
                else:
                    include = True
            else:
                if ts < start:
                    include = False
                elif ts >= end:
                    stopped_early = True
                    break
                else:
                    include = True

            if include:
                writer.writerow(row)
                matched += 1
                if first_source_row == 0:
                    first_source_row = source_row
                last_source_row = source_row

            if progress and scanned % 100_000 == 0:
                progress({
                    "scanned_rows": scanned,
                    "source_row": source_row,
                    "matched_rows": matched,
                    "source_order": source_order,
                    "source_bytes": source_size,
                    "indexed_seek": indexed_seek,
                })

    if matched == 0:
        output.unlink(missing_ok=True)
        raise ValueError(
            "Nenhum negócio foi encontrado no intervalo selecionado. "
            "Confirme contrato, data e horário."
        )

    return SliceResult(
        source_path=str(source),
        output_path=str(output),
        source_size=source_size,
        output_size=output.stat().st_size,
        source_order=source_order,
        symbol=symbol_used,
        start=start.isoformat(),
        end=end.isoformat(),
        scanned_rows=scanned,
        matched_rows=matched,
        stopped_early=stopped_early,
        source_fingerprint=source_id,
        first_source_row=first_source_row,
        last_source_row=last_source_row,
        indexed_seek=indexed_seek,
        source_byte_start=byte_begin,
        source_byte_end=byte_limit,
        sha256=_sha256(output),
    )
