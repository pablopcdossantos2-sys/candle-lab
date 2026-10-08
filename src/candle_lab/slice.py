from __future__ import annotations

import csv
import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from .importers import (
    _detect_dialect,
    _detect_encoding,
    _decimal_number,
    _looks_like_profit_headerless_trade,
    _norm_header,
    _parse_datetime,
)


@dataclass(frozen=True, slots=True)
class TradeCsvLayout:
    profile: str
    has_header: bool
    header_line: int
    data_start_line: int
    symbol_idx: int | None
    date_idx: int | None
    time_idx: int | None
    timestamp_idx: int | None
    buyer_idx: int | None
    price_idx: int
    quantity_idx: int
    seller_idx: int | None
    aggressor_idx: int | None

    def value(self, row: list[str], idx: int | None) -> str:
        if idx is None or idx < 0 or idx >= len(row):
            return ""
        return row[idx].strip()

    def timestamp(self, row: list[str]) -> datetime:
        return _parse_datetime(
            self.value(row, self.timestamp_idx) or None,
            self.value(row, self.date_idx) or None,
            self.value(row, self.time_idx) or None,
        )

    def symbol(self, row: list[str]) -> str:
        return self.value(row, self.symbol_idx).upper()

    def canonical_row(self, row: list[str], *, fallback_symbol: str) -> list[str]:
        ts = self.timestamp(row)
        symbol = self.symbol(row) or fallback_symbol
        price = _decimal_number(self.value(row, self.price_idx))
        quantity = _decimal_number(self.value(row, self.quantity_idx))
        return [
            symbol,
            ts.strftime("%d/%m/%y"),
            ts.strftime("%H:%M:%S"),
            self.value(row, self.buyer_idx),
            format(price, "f"),
            format(quantity, "f"),
            self.value(row, self.seller_idx),
            self.value(row, self.aggressor_idx),
        ]


@dataclass(frozen=True, slots=True)
class SourceProbe:
    encoding: str
    dialect: csv.Dialect
    symbol: str
    source_order: str
    layout: TradeCsvLayout


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
    layout_profile: str
    source_has_header: bool
    source_header_line: int
    sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_ALIASES = {
    "symbol": {"ativo", "ticker", "symbol", "instrumento", "contrato"},
    "date": {"data", "date", "session date", "session_date", "pregao", "pregão"},
    "time": {"hora", "time", "tempo", "horario", "horário"},
    "timestamp": {"timestamp", "datahora", "data hora", "datetime"},
    "buyer": {"agente comprador", "comprador", "buyer", "buyer id", "buyer_id", "corretora compradora"},
    "price": {"preco", "preço", "price", "valor", "preco negocio", "preço negócio"},
    "quantity": {"quantidade", "qtd", "quantity", "qty", "volume quantidade"},
    "seller": {"agente vendedor", "vendedor", "seller", "seller id", "seller_id", "corretora vendedora"},
    "aggressor": {"agressor", "aggressor", "aggression", "lado agressor", "agressor lado"},
}


def _header_index(row: list[str], names: set[str]) -> int | None:
    normalized = [_norm_header(cell) for cell in row]
    wanted = {_norm_header(name) for name in names}
    for idx, value in enumerate(normalized):
        if value in wanted:
            return idx
    return None


def _layout_from_header(row: list[str], *, physical_line: int) -> TradeCsvLayout | None:
    price_idx = _header_index(row, _ALIASES["price"])
    quantity_idx = _header_index(row, _ALIASES["quantity"])
    timestamp_idx = _header_index(row, _ALIASES["timestamp"])
    date_idx = _header_index(row, _ALIASES["date"])
    time_idx = _header_index(row, _ALIASES["time"])
    if price_idx is None or quantity_idx is None:
        return None
    if timestamp_idx is None and (date_idx is None or time_idx is None):
        return None
    return TradeCsvLayout(
        profile="Nelogica / Profit — Trades com cabeçalho reconhecido",
        has_header=True,
        header_line=physical_line,
        data_start_line=physical_line + 1,
        symbol_idx=_header_index(row, _ALIASES["symbol"]),
        date_idx=date_idx,
        time_idx=time_idx,
        timestamp_idx=timestamp_idx,
        buyer_idx=_header_index(row, _ALIASES["buyer"]),
        price_idx=price_idx,
        quantity_idx=quantity_idx,
        seller_idx=_header_index(row, _ALIASES["seller"]),
        aggressor_idx=_header_index(row, _ALIASES["aggressor"]),
    )


def _headerless_layout(*, physical_line: int, with_trade_id: bool = False) -> TradeCsvLayout:
    if with_trade_id:
        return TradeCsvLayout(
            profile="Nelogica / Profit — Trades sem cabeçalho (9 colunas, com Número do Negócio)",
            has_header=False,
            header_line=0,
            data_start_line=physical_line,
            symbol_idx=0,
            date_idx=1,
            time_idx=2,
            timestamp_idx=None,
            buyer_idx=4,
            price_idx=5,
            quantity_idx=6,
            seller_idx=7,
            aggressor_idx=8,
        )
    return TradeCsvLayout(
        profile="Nelogica / Profit — Trades sem cabeçalho (8 colunas)",
        has_header=False,
        header_line=0,
        data_start_line=physical_line,
        symbol_idx=0,
        date_idx=1,
        time_idx=2,
        timestamp_idx=None,
        buyer_idx=3,
        price_idx=4,
        quantity_idx=5,
        seller_idx=6,
        aggressor_idx=7,
    )


def _looks_like_profit_headerless_trade_with_id(row: list[str]) -> bool:
    if len(row) != 9:
        return False
    try:
        datetime.strptime(row[1].strip(), "%d/%m/%y")
        datetime.strptime(row[2].strip(), "%H:%M:%S")
        _decimal_number(row[5])
        qty = _decimal_number(row[6])
        if qty != qty.to_integral_value() or qty <= 0:
            return False
    except (ValueError, IndexError):
        return False
    return row[8].strip().lower() in {"comprador", "vendedor", "rlp", "indefinido", "undefined", ""}


def _detect_trade_layout(path: Path, *, encoding: str, dialect: csv.Dialect) -> TradeCsvLayout:
    first_nonblank: list[str] | None = None
    with path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.reader(handle, dialect=dialect)
        for physical_line, row in enumerate(reader, start=1):
            if not row or not any(cell.strip() for cell in row):
                continue
            if first_nonblank is None:
                first_nonblank = row
            if _looks_like_profit_headerless_trade(row):
                return _headerless_layout(physical_line=physical_line)
            if _looks_like_profit_headerless_trade_with_id(row):
                return _headerless_layout(physical_line=physical_line, with_trade_id=True)
            layout = _layout_from_header(row, physical_line=physical_line)
            if layout is not None:
                return layout
            if physical_line >= 50:
                break

    preview = " | ".join((first_nonblank or [])[:12])
    raise ValueError(
        "Não foi possível reconhecer o layout do CSV de Trades. "
        "O Candle Lab aceita layouts Profit sem cabeçalho de 8 ou 9 colunas, ou um CSV com cabeçalho "
        "contendo ao menos data/hora (ou timestamp), preço e quantidade. "
        f"Primeira linha não vazia observada: {preview!r}"
    )


def _probe(path: Path, max_rows: int = 100_000, *, symbol: str | None = None) -> SourceProbe:
    encoding = _detect_encoding(path)
    with path.open("r", encoding=encoding, newline="") as handle:
        sample = handle.read(8192)
    dialect = _detect_dialect(sample)
    layout = _detect_trade_layout(path, encoding=encoding, dialect=dialect)

    timestamps: list[datetime] = []
    symbols: set[str] = set()
    user_symbol = (symbol or "").strip().upper()

    with path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.reader(handle, dialect=dialect)
        for physical_line, row in enumerate(reader, start=1):
            if physical_line < layout.data_start_line:
                continue
            if not row or not any(cell.strip() for cell in row):
                continue
            try:
                ts = layout.timestamp(row)
            except (ValueError, IndexError) as exc:
                if timestamps:
                    raise ValueError(f"Linha {physical_line}: data/hora não reconhecida: {exc}") from exc
                continue

            file_symbol = layout.symbol(row)
            if file_symbol:
                symbols.add(file_symbol)
            timestamps.append(ts)
            distinct_times = len({item for item in timestamps})
            if len(timestamps) >= 2048 and distinct_times >= 3:
                break
            if len(timestamps) >= max_rows:
                break

    if not timestamps:
        raise ValueError("Nenhum negócio com data/hora válida foi encontrado no CSV")
    if len(symbols) > 1:
        raise ValueError(f"O arquivo contém mais de um ativo: {', '.join(sorted(symbols))}")

    file_symbol = next(iter(symbols), user_symbol)
    if not file_symbol:
        raise ValueError(
            "O CSV não contém coluna de ativo reconhecível. Informe o contrato no formulário (ex.: WINV26)."
        )
    if user_symbol and symbols and user_symbol != file_symbol:
        raise ValueError(f"Ativo informado ({user_symbol}) difere do arquivo ({file_symbol})")

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
        raise ValueError(
            f"Ordem temporal {order}; o recorte seletivo exige um arquivo monotônico "
            "(mais antigo→mais recente ou mais recente→mais antigo)."
        )
    return SourceProbe(
        encoding=encoding,
        dialect=dialect,
        symbol=file_symbol,
        source_order=order,
        layout=layout,
    )


def source_fingerprint(path: str | Path, block_size: int = 1024 * 1024) -> str:
    """Identidade rápida da fonte sem reler todo o CSV."""
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
    """Extrai [start, end) sem carregar o CSV inteiro e normaliza o recorte para 8 colunas Profit."""
    source = Path(str(source_path).strip().strip('"')).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {source}")
    if source.suffix.lower() != ".csv":
        raise ValueError("O arquivo de Trades precisa ser .csv")
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start e end precisam possuir timezone")
    if end <= start:
        raise ValueError("O final do intervalo deve ser posterior ao início")

    probe = _probe(source, symbol=symbol)
    encoding, dialect = probe.encoding, probe.dialect
    layout, source_order = probe.layout, probe.source_order
    file_symbol = probe.symbol
    symbol_used = (symbol or file_symbol).strip().upper()
    if file_symbol and symbol_used != file_symbol:
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
    physical_line = int(source_row_base)
    stopped_early = False
    first_source_row = 0
    last_source_row = 0
    source_size = source.stat().st_size
    source_id = source_fingerprint(source)
    indexed_seek = seek_byte_start is not None
    byte_begin = int(seek_byte_start or 0)
    byte_limit = int(seek_byte_end) if seek_byte_end is not None else source_size

    with source.open("rb") as src, output.open("w", encoding=encoding, newline="") as dst:
        if byte_begin:
            src.seek(byte_begin)
        writer = csv.writer(dst, dialect=csv.excel)
        while src.tell() < byte_limit:
            raw = src.readline()
            if not raw:
                break
            scanned += 1
            physical_line += 1
            decoded = raw.decode(encoding).rstrip("\r\n")
            if not decoded.strip():
                continue
            row = next(csv.reader([decoded], dialect=dialect))
            if not row or not any(cell.strip() for cell in row):
                continue

            # Em varredura desde o início, ignore metadados/cabeçalho anteriores aos negócios.
            if not indexed_seek and physical_line < layout.data_start_line:
                continue
            if layout.has_header and physical_line == layout.header_line:
                continue

            try:
                ts = layout.timestamp(row)
            except (ValueError, IndexError) as exc:
                raise ValueError(f"Linha-fonte {physical_line}: data/hora inválida: {exc}") from exc

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
                writer.writerow(layout.canonical_row(row, fallback_symbol=symbol_used))
                matched += 1
                if first_source_row == 0:
                    first_source_row = physical_line
                last_source_row = physical_line

            if progress and scanned % 100_000 == 0:
                progress({
                    "scanned_rows": scanned,
                    "source_row": physical_line,
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
        layout_profile=layout.profile,
        source_has_header=layout.has_header,
        source_header_line=layout.header_line,
        sha256=_sha256(output),
    )
