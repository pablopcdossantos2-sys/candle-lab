from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
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


def _read_text(path: str | Path) -> tuple[str, str]:
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            pass
    raise ValueError("Não foi possível identificar a codificação do CSV")


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
        return "Nelogica / Profit — Tick by Tick"
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


def import_csv_with_report(path: str | Path, *, symbol: str | None, tick_size: float, source: str = "csv") -> tuple[list[Trade], CSVImportReport]:
    if tick_size <= 0:
        raise ValueError("tick_size deve ser > 0")

    text, encoding = _read_text(path)
    dialect = _detect_dialect(text)
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV sem cabeçalho")

    tick = Decimal(str(tick_size))
    parsed: list[Trade] = []
    original_timestamps: list[datetime] = []
    file_symbols: set[str] = set()
    trade_ids_seen: set[tuple[str, str]] = set()
    duplicate_trade_ids = 0
    recognized: set[str] = set()
    source_rows = 0

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

        parsed.append(Trade(symbol=row_symbol,ts=ts,price_ticks=price_ticks,quantity=qty,trade_id=trade_id,
                            aggressor=_aggressor(agg_raw),source=source,buyer_id=buyer_id,seller_id=seller_id,
                            sequence_no=source_rows,flags=(f"after={after_raw}" if after_raw else None)))
        original_timestamps.append(ts)

    if not parsed:
        raise ValueError("Nenhum negócio encontrado no CSV")
    if len(file_symbols) > 1:
        raise ValueError(f"O CSV contém mais de um ativo ({', '.join(sorted(file_symbols))}); importe um contrato por vez")

    chronological_inversions=sum(1 for a,b in zip(original_timestamps,original_timestamps[1:]) if b<a)
    known_aggressors=sum(1 for t in parsed if t.aggressor != AggressorSide.NONE)
    buyer_seller_known=sum(1 for t in parsed if t.buyer_id and t.seller_id)
    sorted_trades=sorted(parsed,key=lambda t:(t.ts,t.sequence_no or 0))
    warnings=[]
    if chronological_inversions:
        warnings.append(f"Foram detectadas {chronological_inversions} inversões cronológicas no arquivo; a análise usa ordenação por timestamp e sequência da fonte.")
    if duplicate_trade_ids:
        warnings.append(f"Há {duplicate_trade_ids} ocorrência(s) repetida(s) de número de negócio dentro do mesmo pregão.")
    if known_aggressors == 0:
        warnings.append("A fonte não informou lado agressor reconhecível; métricas de agressão permanecerão indisponíveis.")
    if file_symbols and user_symbol and user_symbol not in file_symbols:
        warnings.append(f"O ativo informado ({user_symbol}) difere do ativo presente no arquivo ({next(iter(file_symbols))}). Foi usado o valor informado pelo usuário.")
    if user_symbol in {"WINFUT","WDOFUT","INDFUT","DOLFUT"}:
        warnings.append("O ticker informado parece ser uma série contínua. Para pesquisa histórica, prefira preservar o contrato efetivamente negociado (ex.: WINV26).")

    report=CSVImportReport(profile=_profile(reader.fieldnames),encoding=encoding,
        delimiter={";":"ponto e vírgula",",":"vírgula","\t":"tab","|":"pipe"}.get(dialect.delimiter,dialect.delimiter),
        source_rows=source_rows,imported_rows=len(sorted_trades),first_timestamp=sorted_trades[0].ts.isoformat(),
        last_timestamp=sorted_trades[-1].ts.isoformat(),session_dates=sorted({t.ts.date().isoformat() for t in sorted_trades}),
        symbols_in_file=sorted(file_symbols),symbol_used=sorted_trades[0].symbol,chronological_inversions=chronological_inversions,
        duplicate_trade_ids=duplicate_trade_ids,aggressor_known_pct=round(known_aggressors/len(sorted_trades)*100,2),
        buyer_seller_known_pct=round(buyer_seller_known/len(sorted_trades)*100,2),recognized_fields=sorted(recognized),warnings=warnings)
    return sorted_trades, report


def import_generic_csv(path: str | Path, *, symbol: str, tick_size: float, source: str = "csv") -> list[Trade]:
    trades, _ = import_csv_with_report(path, symbol=symbol, tick_size=tick_size, source=source)
    return trades
