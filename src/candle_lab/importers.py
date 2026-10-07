from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

from .models import AggressorSide, Trade


DEFAULT_TIMEZONE = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True, slots=True)
class CSVImportReport:
    profile: str
    encoding: str
    delimiter: str
    source_rows: int
    imported_rows: int
    first_timestamp: str
    last_timestamp: str
    session_dates: list[str]
    symbols_in_file: list[str]
    symbol_used: str
    chronological_inversions: int
    duplicate_trade_ids: int
    aggressor_known_pct: float
    buyer_seller_known_pct: float
    recognized_fields: list[str]
    warnings: list[str]
    source_order: str = "UNKNOWN"
    timestamp_precision: str = "UNKNOWN"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _norm_header(value: str) -> str:
    return (
        value.strip().lower()
        .replace("á", "a").replace("à", "a").replace("ã", "a").replace("â", "a")
        .replace("é", "e").replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o").replace("ô", "o").replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
        .replace("º", "o").replace("°", "o")
        .replace("_", " ")
    )


def _first(row: dict[str, str], names: tuple[str, ...]) -> str | None:
    normalized = {_norm_header(k): v for k, v in row.items() if k is not None}
    for name in names:
        key = _norm_header(name)
        if key in normalized and normalized[key] not in (None, ""):
            return str(normalized[key]).strip()
    return None


def _detect_encoding(path: str | Path) -> str:
    raw = Path(path).read_bytes()[:65536]
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            raw.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            pass
    raise ValueError("Não foi possível identificar a codificação do CSV")


def _read_text(path: str | Path) -> tuple[str, str]:
    """Compatibilidade para arquivos pequenos (referências OHLC). Trades usam leitura streaming."""
    encoding = _detect_encoding(path)
    return Path(path).read_text(encoding=encoding), encoding


def _decimal_number(raw: str) -> Decimal:
    text = raw.strip().replace(" ", "")
    if not text:
        raise ValueError("Número vazio")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Número inválido: {raw}") from exc


def _parse_datetime(ts_raw: str | None, date_raw: str | None, time_raw: str | None) -> datetime:
    candidates: list[str] = []
    if ts_raw:
        candidates.append(ts_raw.strip())
    if date_raw and time_raw:
        candidates.append(f"{date_raw.strip()} {time_raw.strip()}")

    formats = (
        "%d/%m/%Y %H:%M:%S.%f",
        "%d/%m/%Y %H:%M:%S,%f",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%y %H:%M:%S.%f",
        "%d/%m/%y %H:%M:%S,%f",
        "%d/%m/%y %H:%M:%S",
        "%d/%m/%y %H:%M",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S,%f",
        "%Y-%m-%d %H:%M:%S",
    )
    for value in candidates:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=DEFAULT_TIMEZONE)
        except ValueError:
            pass
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=DEFAULT_TIMEZONE)
            except ValueError:
                continue
    raise ValueError(f"Data/hora inválida: {candidates[0] if candidates else '<ausente>'}")


def _detect_dialect(text: str) -> csv.Dialect:
    sample = text[:8192]
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except csv.Error:
        return csv.excel


def _profile(fieldnames: list[str]) -> str:
    normalized = {_norm_header(x) for x in fieldnames}
    nelogica_core = {"ativo","data","tempo","numero do negocio","preco","quantidade","agressor"}
    if len(nelogica_core & normalized) >= 6:
        return "Nelogica / Profit — Tick by Tick com cabeçalho"
    if "timestamp" in normalized and ({"price", "preco"} & normalized) and ({"quantity", "quantidade", "qtd"} & normalized):
        return "CSV genérico — timestamp único"
    if ({"data", "date"} & normalized) and ({"hora", "tempo", "time", "horario"} & normalized):
        return "CSV genérico — data/hora separadas"
    return "CSV genérico"


def _aggressor(raw: str | None) -> AggressorSide:
    if not raw:
        return AggressorSide.NONE
    value = _norm_header(raw).strip().upper()
    buy_exact = {"BUY", "COMPRA", "C", "B", "BUYER", "COMPRADOR", "AGRESSAO COMPRA", "AGRESSOR COMPRADOR"}
    sell_exact = {"SELL", "VENDA", "V", "S", "SELLER", "VENDEDOR", "AGRESSAO VENDA", "AGRESSOR VENDEDOR"}
    if value in buy_exact or "COMPRA" in value or "COMPRADOR" in value:
        return AggressorSide.BUY
    if value in sell_exact or "VENDA" in value or "VENDEDOR" in value:
        return AggressorSide.SELL
    return AggressorSide.NONE


def _looks_like_profit_headerless_trade(row: list[str]) -> bool:
    if len(row) != 8:
        return False
    try:
        datetime.strptime(row[1].strip(), "%d/%m/%y")
        datetime.strptime(row[2].strip(), "%H:%M:%S")
        Decimal(row[4].strip())
        int(row[5].strip())
    except (ValueError, InvalidOperation):
        return False
    return row[7].strip().lower() in {"comprador", "vendedor", "rlp", "indefinido", "undefined", ""}


def _source_order(timestamps: list[datetime]) -> tuple[str, int]:
    asc = desc = 0
    for a, b in zip(timestamps, timestamps[1:]):
        if b > a:
            asc += 1
        elif b < a:
            desc += 1
    if desc and not asc:
        return "DESCENDING", desc
    if asc and not desc:
        return "ASCENDING", 0
    if not asc and not desc:
        return "SAME_TIMESTAMP", 0
    return "MIXED", desc


def _normalize_order(parsed: list[Trade], timestamps: list[datetime], warnings: list[str]) -> tuple[list[Trade], str, int]:
    order, inversions = _source_order(timestamps)
    if order == "DESCENDING":
        # Export real do Profit observado em 07/10/2026: arquivo mais recente -> mais antigo.
        # Reverter o arquivo também preserva a ordem intrassegundo que reconstruiu OHLC exatamente.
        normalized = list(reversed(parsed))
        normalized = [replace(t, sequence_no=i + 1) for i, t in enumerate(normalized)]
        warnings.append(
            "O arquivo estava em ordem cronológica inversa (mais recente → mais antigo). "
            "O Candle Lab reverteu a sequência completa antes da reconstrução."
        )
        return normalized, order, inversions
    if order == "ASCENDING":
        return [replace(t, sequence_no=i + 1) for i, t in enumerate(parsed)], order, inversions

    warnings.append(
        "A ordem temporal do arquivo é mista. O Candle Lab ordenou por timestamp; "
        "a ordem relativa de negócios com timestamp idêntico deve ser tratada com cautela."
    )
    ordered = sorted(parsed, key=lambda t: (t.ts, t.sequence_no or 0))
    return [replace(t, sequence_no=i + 1) for i, t in enumerate(ordered)], order, inversions


def _import_profit_headerless(
    path: str | Path, *, encoding: str, dialect: csv.Dialect, symbol: str | None,
    tick_size: float, source: str,
) -> tuple[list[Trade], CSVImportReport]:
    tick = Decimal(str(tick_size))
    parsed: list[Trade] = []
    timestamps: list[datetime] = []
    file_symbols: set[str] = set()
    warnings: list[str] = []
    raw_aggressors: dict[str, int] = {}
    user_symbol = (symbol or "").strip().upper()

    with Path(path).open("r", encoding=encoding, newline="") as handle:
        reader = csv.reader(handle, dialect=dialect)
        for row_no, row in enumerate(reader, start=1):
            if not row or not any(cell.strip() for cell in row):
                continue
            if len(row) != 8:
                raise ValueError(f"Linha {row_no}: layout Profit sem cabeçalho esperava 8 colunas; recebeu {len(row)}")
            file_symbol = row[0].strip().upper()
            file_symbols.add(file_symbol)
            row_symbol = user_symbol or file_symbol
            ts = _parse_datetime(None, row[1], row[2])
            try:
                price = _decimal_number(row[4])
                ratio = price / tick
                price_ticks = int(ratio.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                if abs(ratio - Decimal(price_ticks)) > Decimal("0.000001"):
                    raise ValueError(f"preço {price} não é múltiplo do tick {tick}")
                qty = int(row[5].strip())
                if qty <= 0:
                    raise ValueError("quantidade deve ser positiva")
            except ValueError as exc:
                raise ValueError(f"Linha {row_no}: {exc}") from exc

            raw_agg = row[7].strip()
            raw_aggressors[raw_agg] = raw_aggressors.get(raw_agg, 0) + 1
            parsed.append(
                Trade(
                    symbol=row_symbol,
                    ts=ts,
                    price_ticks=price_ticks,
                    quantity=qty,
                    trade_id=None,
                    aggressor=_aggressor(raw_agg),
                    source=source,
                    buyer_id=row[3].strip() or None,
                    seller_id=row[6].strip() or None,
                    sequence_no=len(parsed) + 1,
                    flags=f"raw_aggressor={raw_agg}" if raw_agg else None,
                )
            )
            timestamps.append(ts)

    if not parsed:
        raise ValueError("Nenhum negócio encontrado no CSV")
    if len(file_symbols) > 1:
        raise ValueError(f"O CSV contém mais de um ativo ({', '.join(sorted(file_symbols))}); importe um contrato por vez")

    normalized, source_order, inversions = _normalize_order(parsed, timestamps, warnings)
    known_aggressors = sum(1 for t in normalized if t.aggressor != AggressorSide.NONE)
    buyer_seller_known = sum(1 for t in normalized if t.buyer_id and t.seller_id)
    rlp_count = raw_aggressors.get("RLP", 0)
    if rlp_count:
        warnings.append(
            f"{rlp_count} registro(s) foram marcados como RLP pela fonte. "
            "Eles são preservados no campo de flags e não são convertidos artificialmente em BUY/SELL."
        )
    warnings.append(
        "Este layout não contém Número do Negócio e os timestamps têm precisão de 1 segundo. "
        "A sequência intrassegundo é preservada pela ordem do arquivo normalizada, mas não equivale a um identificador oficial de execução."
    )

    report = CSVImportReport(
        profile="Nelogica / Profit — Trades sem cabeçalho (8 colunas)",
        encoding=encoding,
        delimiter={";":"ponto e vírgula",",":"vírgula","\t":"tab","|":"pipe"}.get(dialect.delimiter,dialect.delimiter),
        source_rows=len(parsed),
        imported_rows=len(normalized),
        first_timestamp=normalized[0].ts.isoformat(),
        last_timestamp=normalized[-1].ts.isoformat(),
        session_dates=sorted({t.ts.date().isoformat() for t in normalized}),
        symbols_in_file=sorted(file_symbols),
        symbol_used=normalized[0].symbol,
        chronological_inversions=inversions,
        duplicate_trade_ids=0,
        aggressor_known_pct=round(known_aggressors / len(normalized) * 100, 2),
        buyer_seller_known_pct=round(buyer_seller_known / len(normalized) * 100, 2),
        recognized_fields=["Ativo","Data","Hora","Agente Comprador","Preço","Quantidade","Agente Vendedor","Agressor"],
        warnings=warnings,
        source_order=source_order,
        timestamp_precision="1 segundo",
    )
    return normalized, report


def import_csv_with_report(path: str | Path, *, symbol: str | None, tick_size: float, source: str = "csv") -> tuple[list[Trade], CSVImportReport]:
    if tick_size <= 0:
        raise ValueError("tick_size deve ser > 0")

    path = Path(path)
    encoding = _detect_encoding(path)
    with path.open("r", encoding=encoding, newline="") as probe:
        sample = probe.read(8192)
    dialect = _detect_dialect(sample)

    with path.open("r", encoding=encoding, newline="") as probe:
        first_row = next(csv.reader(probe, dialect=dialect), [])
    if _looks_like_profit_headerless_trade(first_row):
        return _import_profit_headerless(
            path, encoding=encoding, dialect=dialect, symbol=symbol, tick_size=tick_size, source=source
        )

    tick = Decimal(str(tick_size))
    parsed: list[Trade] = []
    original_timestamps: list[datetime] = []
    file_symbols: set[str] = set()
    trade_ids_seen: set[tuple[str, str]] = set()
    duplicate_trade_ids = 0
    recognized: set[str] = set()
    source_rows = 0
    warnings: list[str] = []

    with path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.DictReader(handle, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError("CSV sem cabeçalho")

        header_norm = {_norm_header(h): h for h in reader.fieldnames if h is not None}
        known_aliases = {
            "timestamp","datahora","data hora","datetime","data","date","session date","pregao",
            "hora","time","tempo","horario","preco","price","valor","preco negocio",
            "quantity","qtd","quantidade","qty","volume quantidade","numero do negocio","numero negocio",
            "trade id","tradeid","aggressor","agressor","aggression","lado agressor","ativo","ticker","symbol",
            "agente comprador","comprador","buyer","buyer id","agente vendedor","vendedor","seller","seller id","after",
        }
        for norm, original in header_norm.items():
            if norm in known_aliases:
                recognized.add(original)

        user_symbol = (symbol or "").strip().upper()
        inferred_file_symbol = ""

        for idx, row in enumerate(reader, start=2):
            if not any((v or "").strip() for v in row.values()):
                continue
            source_rows += 1
            ts_raw = _first(row, ("timestamp","datahora","data hora","datetime"))
            date_raw = _first(row, ("data","date","session_date","pregao"))
            time_raw = _first(row, ("hora","time","tempo","horario","horário"))
            price_raw = _first(row, ("price","preco","preço","valor","preco negocio","preço negócio"))
            qty_raw = _first(row, ("quantity","qtd","quantidade","qty","volume quantidade"))
            file_symbol = _first(row, ("ativo","ticker","symbol","instrumento","contrato"))
            if file_symbol:
                inferred_file_symbol = file_symbol.strip().upper()
                file_symbols.add(inferred_file_symbol)
            if not price_raw or not qty_raw:
                raise ValueError(f"Linha {idx}: preço/quantidade ausente")

            try:
                ts = _parse_datetime(ts_raw, date_raw, time_raw)
                price = _decimal_number(price_raw)
                price_ticks_decimal = price / tick
                price_ticks = int(price_ticks_decimal.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                if abs(price_ticks_decimal - Decimal(price_ticks)) > Decimal("0.000001"):
                    raise ValueError(f"Preço {price} não é múltiplo do tick {tick}")
                qty_decimal = _decimal_number(qty_raw)
                if qty_decimal != qty_decimal.to_integral_value():
                    raise ValueError(f"quantidade deve ser inteira: {qty_raw}")
                qty = int(qty_decimal)
                if qty <= 0:
                    raise ValueError("quantidade deve ser positiva")
            except ValueError as exc:
                raise ValueError(f"Linha {idx}: {exc}") from exc

            trade_id = _first(row, ("trade_id","trade id","tradeid","numero_negocio","numero negocio","numero do negocio","número do negócio","nº negocio","nro negocio","negocio","negócio"))
            if trade_id:
                key=(ts.date().isoformat(),trade_id)
                if key in trade_ids_seen:
                    duplicate_trade_ids += 1
                trade_ids_seen.add(key)

            buyer_id = _first(row, ("agente comprador","comprador","buyer","buyer_id","buyer id","corretora compradora"))
            seller_id = _first(row, ("agente vendedor","vendedor","seller","seller_id","seller id","corretora vendedora"))
            agg_raw = _first(row, ("aggressor","agressor","aggression","lado agressor","agressor lado"))
            after_raw = _first(row, ("after","after market","after-market"))
            row_symbol = user_symbol or inferred_file_symbol
            if not row_symbol:
                raise ValueError(f"Linha {idx}: símbolo/ativo ausente; informe o contrato no formulário")

            parsed.append(Trade(
                symbol=row_symbol, ts=ts, price_ticks=price_ticks, quantity=qty, trade_id=trade_id,
                aggressor=_aggressor(agg_raw), source=source, buyer_id=buyer_id, seller_id=seller_id,
                sequence_no=source_rows, flags=(f"after={after_raw}" if after_raw else None),
            ))
            original_timestamps.append(ts)

        profile = _profile(reader.fieldnames)

    if not parsed:
        raise ValueError("Nenhum negócio encontrado no CSV")
    if len(file_symbols) > 1:
        raise ValueError(f"O CSV contém mais de um ativo ({', '.join(sorted(file_symbols))}); importe um contrato por vez")

    normalized, source_order, inversions = _normalize_order(parsed, original_timestamps, warnings)
    known_aggressors = sum(1 for t in normalized if t.aggressor != AggressorSide.NONE)
    buyer_seller_known = sum(1 for t in normalized if t.buyer_id and t.seller_id)
    if duplicate_trade_ids:
        warnings.append(f"Há {duplicate_trade_ids} ocorrência(s) repetida(s) de número de negócio dentro do mesmo pregão.")
    if known_aggressors == 0:
        warnings.append("A fonte não informou lado agressor reconhecível; métricas de agressão permanecerão indisponíveis.")
    if file_symbols and (symbol or "").strip().upper() and (symbol or "").strip().upper() not in file_symbols:
        warnings.append("O ativo informado difere do ativo presente no arquivo. Foi usado o valor informado pelo usuário.")
    if normalized[0].symbol in {"WINFUT","WDOFUT","INDFUT","DOLFUT"}:
        warnings.append("O ticker parece ser uma série contínua. Prefira preservar o contrato efetivamente negociado (ex.: WINV26).")

    report = CSVImportReport(
        profile=profile,
        encoding=encoding,
        delimiter={";":"ponto e vírgula",",":"vírgula","\t":"tab","|":"pipe"}.get(dialect.delimiter,dialect.delimiter),
        source_rows=source_rows,
        imported_rows=len(normalized),
        first_timestamp=normalized[0].ts.isoformat(),
        last_timestamp=normalized[-1].ts.isoformat(),
        session_dates=sorted({t.ts.date().isoformat() for t in normalized}),
        symbols_in_file=sorted(file_symbols),
        symbol_used=normalized[0].symbol,
        chronological_inversions=inversions,
        duplicate_trade_ids=duplicate_trade_ids,
        aggressor_known_pct=round(known_aggressors/len(normalized)*100,2),
        buyer_seller_known_pct=round(buyer_seller_known/len(normalized)*100,2),
        recognized_fields=sorted(recognized),
        warnings=warnings,
        source_order=source_order,
        timestamp_precision="conforme fonte",
    )
    return normalized, report


def import_generic_csv(path: str | Path, *, symbol: str, tick_size: float, source: str = "csv") -> list[Trade]:
    trades, _ = import_csv_with_report(path, symbol=symbol, tick_size=tick_size, source=source)
    return trades
