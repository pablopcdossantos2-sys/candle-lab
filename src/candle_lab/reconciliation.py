from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable

from .candles import build_candles, floor_time
from .importers import _decimal_number, _detect_dialect, _first, _norm_header, _parse_datetime, _read_text
from .models import Candle, Trade


@dataclass(frozen=True, slots=True)
class ReferenceCandle:
    symbol: str
    start: datetime
    interval_seconds: int
    open_ticks: int
    high_ticks: int
    low_ticks: int
    close_ticks: int
    volume: int | None = None
    trades: int | None = None
    source: str = "reference_csv"

    @property
    def end(self) -> datetime:
        return self.start + timedelta(seconds=self.interval_seconds)


@dataclass(frozen=True, slots=True)
class ReferenceImportReport:
    profile: str
    encoding: str
    delimiter: str
    source_rows: int
    imported_rows: int
    symbol_used: str
    interval_seconds: int
    first_start: str
    last_start: str
    session_dates: list[str]
    recognized_fields: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _br_formatted_number(raw: str) -> Decimal:
    text = raw.strip().replace(" ", "")
    if not text:
        raise ValueError("Número vazio")
    # Export formatado do Profit: ponto para milhar e vírgula para decimais.
    # Exemplos reais: 204.660 -> 204660; 1.058.515.234,00 -> 1058515234.00.
    normalized = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"Número inválido: {raw}") from exc


def _to_ticks(raw: str, tick_size: float, *, field: str, row_no: int, br_formatted: bool = False) -> int:
    tick = Decimal(str(tick_size))
    value = _br_formatted_number(raw) if br_formatted else _decimal_number(raw)
    ratio = value / tick
    ticks = int(ratio.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if abs(ratio - Decimal(ticks)) > Decimal("0.000001"):
        raise ValueError(f"Linha {row_no}: {field}={value} não é múltiplo do tick {tick}")
    return ticks


def _optional_int(raw: str | None, *, field: str, row_no: int, br_formatted: bool = False) -> int | None:
    if raw in (None, ""):
        return None
    value = _br_formatted_number(raw) if br_formatted else _decimal_number(raw)
    if value != value.to_integral_value():
        raise ValueError(f"Linha {row_no}: {field} deve ser inteiro")
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"Linha {row_no}: {field} não pode ser negativo")
    return parsed


def _is_profit_formatted_ohlc(fieldnames: list[str]) -> bool:
    normalized = {_norm_header(h) for h in fieldnames if h}
    required = {"ativo","data","hora","abertura","maximo","minimo","fechamento","volume","quantidade"}
    return required.issubset(normalized)


def import_reference_candles(
    path: str | Path, *, symbol: str | None, tick_size: float, interval_seconds: int, source: str = "reference_csv",
) -> tuple[list[ReferenceCandle], ReferenceImportReport]:
    if tick_size <= 0:
        raise ValueError("tick_size deve ser > 0")
    if interval_seconds <= 0:
        raise ValueError("interval_seconds deve ser > 0")

    text, encoding = _read_text(path)
    dialect = _detect_dialect(text)
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV de referência sem cabeçalho")

    profit_formatted = _is_profit_formatted_ohlc(reader.fieldnames)
    user_symbol = (symbol or "").strip().upper()
    refs: list[ReferenceCandle] = []
    recognized: set[str] = set()
    warnings: list[str] = []
    source_rows = 0
    seen: set[tuple[str, datetime, int]] = set()

    aliases = {
        "timestamp","datahora","data hora","datetime","data","date","pregao",
        "hora","tempo","time","horario","ativo","ticker","symbol","contrato",
        "abertura","open","maxima","maximo","high","minima","minimo","low","fechamento","close",
        "volume","quantidade","qtd","negocios","trades","numero de negocios","n negocios",
    }
    for header in reader.fieldnames:
        if header and _norm_header(header) in aliases:
            recognized.add(header)

    for row_no, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue
        source_rows += 1
        ts_raw = _first(row, ("timestamp","datahora","data hora","datetime"))
        date_raw = _first(row, ("data","date","pregao","session_date"))
        time_raw = _first(row, ("hora","tempo","time","horario","horário"))
        if not ts_raw and date_raw and not time_raw:
            time_raw = "00:00:00"
        start = floor_time(_parse_datetime(ts_raw, date_raw, time_raw), interval_seconds)

        file_symbol = _first(row, ("ativo","ticker","symbol","contrato","instrumento"))
        row_symbol = user_symbol or (file_symbol or "").strip().upper()
        if not row_symbol:
            raise ValueError(f"Linha {row_no}: ativo ausente; informe o contrato")

        open_raw = _first(row, ("open","abertura","preco abertura","preço abertura"))
        high_raw = _first(row, ("high","maxima","máxima","maximo","máximo","preco maximo","preço máximo"))
        low_raw = _first(row, ("low","minima","mínima","minimo","mínimo","preco minimo","preço mínimo"))
        close_raw = _first(row, ("close","fechamento","preco fechamento","preço fechamento"))
        if not all((open_raw, high_raw, low_raw, close_raw)):
            raise ValueError(f"Linha {row_no}: OHLC incompleto")

        # No CSV de 1 minuto formatado do Profit:
        #   Volume = volume financeiro
        #   Quantidade = contratos negociados
        # O volume interno do Candle Lab é quantidade de contratos.
        if profit_formatted:
            volume_raw = _first(row, ("quantidade","qtd","volume contratos"))
        else:
            volume_raw = _first(row, ("volume contratos","quantidade","qtd","volume"))
        trades_raw = _first(row, ("trades","negocios","negócios","numero de negocios","número de negócios","n negocios"))

        ref = ReferenceCandle(
            symbol=row_symbol,
            start=start,
            interval_seconds=interval_seconds,
            open_ticks=_to_ticks(open_raw, tick_size, field="abertura", row_no=row_no, br_formatted=profit_formatted),
            high_ticks=_to_ticks(high_raw, tick_size, field="máxima", row_no=row_no, br_formatted=profit_formatted),
            low_ticks=_to_ticks(low_raw, tick_size, field="mínima", row_no=row_no, br_formatted=profit_formatted),
            close_ticks=_to_ticks(close_raw, tick_size, field="fechamento", row_no=row_no, br_formatted=profit_formatted),
            volume=_optional_int(volume_raw, field="quantidade", row_no=row_no, br_formatted=profit_formatted),
            trades=_optional_int(trades_raw, field="negócios", row_no=row_no, br_formatted=profit_formatted),
            source=source,
        )
        if ref.low_ticks > min(ref.open_ticks, ref.close_ticks, ref.high_ticks) or ref.high_ticks < max(ref.open_ticks, ref.close_ticks, ref.low_ticks):
            raise ValueError(f"Linha {row_no}: OHLC logicamente inconsistente")
        key = (ref.symbol, ref.start, ref.interval_seconds)
        if key in seen:
            raise ValueError(f"Linha {row_no}: candle de referência duplicado para {ref.start.isoformat()}")
        seen.add(key)
        refs.append(ref)

    if not refs:
        raise ValueError("Nenhum candle de referência válido encontrado")

    if profit_formatted:
        warnings.append(
            "Layout Nelogica/Profit formatado detectado: 'Quantidade' foi usada como volume em contratos. "
            "A coluna 'Volume' financeiro foi preservada apenas na fonte e não é comparada ao volume interno do candle."
        )
    else:
        normalized_headers = {_norm_header(h) for h in (reader.fieldnames or []) if h}
        if "volume" in normalized_headers and not ({"quantidade","qtd","volume contratos"} & normalized_headers):
            warnings.append(
                "A coluna 'Volume' foi importada como volume de referência. Confirme se a fonte usa contratos, volume financeiro ou outra unidade."
            )
    refs.sort(key=lambda item: (item.symbol, item.start))

    report = ReferenceImportReport(
        profile="Nelogica / Profit — candles formatados" if profit_formatted else "Candles OHLC de referência",
        encoding=encoding,
        delimiter={";":"ponto e vírgula",",":"vírgula","\t":"tab","|":"pipe"}.get(dialect.delimiter,dialect.delimiter),
        source_rows=source_rows,
        imported_rows=len(refs),
        symbol_used=refs[0].symbol,
        interval_seconds=interval_seconds,
        first_start=refs[0].start.isoformat(),
        last_start=refs[-1].start.isoformat(),
        session_dates=sorted({ref.start.date().isoformat() for ref in refs}),
        recognized_fields=sorted(recognized),
        warnings=warnings,
    )
    return refs, report


def _tick_diff(actual: int, reference: int) -> int:
    return actual - reference


def reconcile_candles(
    trades: Iterable[Trade], references: Iterable[ReferenceCandle], *, interval_seconds: int, tick_size: float
) -> dict[str, object]:
    reconstructed = build_candles(list(trades), interval_seconds)
    actual_map: dict[tuple[str, datetime], Candle] = {(c.symbol, c.start): c for c in reconstructed}
    refs = sorted(list(references), key=lambda ref: (ref.symbol, ref.start))
    results: list[dict[str, object]] = []
    exact = ohlc_match = mismatch = missing_data = 0

    for ref in refs:
        actual = actual_map.get((ref.symbol, ref.start))
        if actual is None:
            missing_data += 1
            results.append({
                "symbol":ref.symbol,"start":ref.start.isoformat(),"status":"NO_DATA",
                "message":"Não há negócios suficientes para reconstruir este candle.",
                "reference":_reference_payload(ref,tick_size),"actual":None,"checks":[]
            })
            continue
        checks=[]
        for name, actual_value, reference_value in (
            ("open",actual.open_ticks,ref.open_ticks),("high",actual.high_ticks,ref.high_ticks),
            ("low",actual.low_ticks,ref.low_ticks),("close",actual.close_ticks,ref.close_ticks),
        ):
            delta=_tick_diff(actual_value,reference_value)
            checks.append({"field":name,"match":delta==0,"delta_ticks":delta,"delta_price":delta*tick_size})
        price_ok=all(bool(item["match"]) for item in checks)
        optional_ok=True
        if ref.volume is not None:
            delta=actual.volume-ref.volume
            checks.append({"field":"volume","match":delta==0,"delta":delta})
            optional_ok &= delta==0
        if ref.trades is not None:
            delta=actual.trades-ref.trades
            checks.append({"field":"trades","match":delta==0,"delta":delta})
            optional_ok &= delta==0

        if price_ok and optional_ok:
            status="EXACT"; exact+=1
        elif price_ok:
            status="OHLC_MATCH"; ohlc_match+=1
        else:
            status="MISMATCH"; mismatch+=1
        results.append({
            "symbol":ref.symbol,"start":ref.start.isoformat(),"status":status,
            "message":{
                "EXACT":"OHLC e campos opcionais informados coincidem.",
                "OHLC_MATCH":"OHLC coincide, mas volume e/ou número de negócios diverge.",
                "MISMATCH":"Há divergência de preço entre referência e reconstrução.",
            }[status],
            "reference":_reference_payload(ref,tick_size),"actual":_candle_payload(actual,tick_size),"checks":checks
        })

    total=len(refs); comparable=max(total-missing_data,0); price_matches=exact+ohlc_match
    return {
        "interval_seconds":interval_seconds,
        "summary":{
            "reference_candles":total,"reconstructed_candles":len(reconstructed),
            "exact":exact,"ohlc_match":ohlc_match,"mismatch":mismatch,"no_data":missing_data,
            "ohlc_match_rate":price_matches/comparable if comparable else 0.0,
            "exact_rate":exact/comparable if comparable else 0.0,
        },
        "results":results,
    }


def reconcile_available_candles(
    trades: Iterable[Trade], references: Iterable[ReferenceCandle], *, interval_seconds: int, tick_size: float
) -> dict[str, object]:
    """Reconcilia apenas candles que possuem negócios no conjunto seletivo.

    É o modo adequado quando vários recortes intencionais e não contíguos do mesmo
    pregão foram importados. Ausência fora dos recortes não é classificada como NO_DATA.
    """
    trades=list(trades)
    refs=list(references)
    reconstructed=build_candles(trades,interval_seconds)
    available={(c.symbol,c.start) for c in reconstructed}
    selected_refs=[ref for ref in refs if (ref.symbol,ref.start) in available]
    report=reconcile_candles(trades,selected_refs,interval_seconds=interval_seconds,tick_size=tick_size)
    report["coverage_mode"]="AVAILABLE_CANDLES_ONLY"
    report["reference_candles_skipped_outside_slices"]=len(refs)-len(selected_refs)
    report["selected_candle_starts"]=[ref.start.isoformat() for ref in selected_refs]
    return report


def reconcile_observed_window(
    trades: Iterable[Trade], references: Iterable[ReferenceCandle], *, interval_seconds: int, tick_size: float
) -> dict[str, object]:
    """Reconcilia apenas candles inteiramente cobertos pelo recorte de trades.

    Isso evita classificar como MISMATCH um candle de fronteira quando o arquivo termina
    no meio daquele minuto, situação observada no primeiro recorte real do WINV26.
    """
    trades = sorted(list(trades), key=lambda t: (t.ts, t.sequence_no or 0))
    refs = list(references)
    if not trades:
        return {
            "observed_window": None,
            "partial_boundary_references": [],
            **reconcile_candles([], [], interval_seconds=interval_seconds, tick_size=tick_size),
        }

    first_ts = trades[0].ts
    last_ts = trades[-1].ts
    complete_refs: list[ReferenceCandle] = []
    partial_refs: list[ReferenceCandle] = []
    first_bucket = floor_time(first_ts, interval_seconds)
    last_bucket = floor_time(last_ts, interval_seconds)
    boundary_tolerance = min(5.0, interval_seconds * 0.10)
    for ref in refs:
        overlaps = ref.end > first_ts and ref.start <= last_ts
        if not overlaps:
            continue

        if first_bucket < ref.start < last_bucket:
            complete_refs.append(ref)
            continue

        if ref.start == first_bucket and ref.start < last_bucket:
            # Um recorte iniciado praticamente na abertura do candle pode contê-lo por inteiro.
            if (first_ts - ref.start).total_seconds() <= boundary_tolerance:
                complete_refs.append(ref)
            else:
                partial_refs.append(ref)
            continue

        if ref.start == last_bucket:
            elapsed = (last_ts - ref.start).total_seconds()
            # O último candle só é aceito quando o arquivo alcança praticamente todo o intervalo.
            if elapsed >= interval_seconds - boundary_tolerance:
                complete_refs.append(ref)
            else:
                partial_refs.append(ref)
            continue

        if ref.start >= first_ts and ref.end <= last_ts:
            complete_refs.append(ref)
        else:
            partial_refs.append(ref)

    report = reconcile_candles(trades, complete_refs, interval_seconds=interval_seconds, tick_size=tick_size)
    report["observed_window"] = {
        "first_trade": first_ts.isoformat(),
        "last_trade": last_ts.isoformat(),
        "complete_reference_candles": len(complete_refs),
        "partial_boundary_candles": len(partial_refs),
    }
    report["partial_boundary_references"] = [
        {"symbol":ref.symbol,"start":ref.start.isoformat(),"end":ref.end.isoformat(),"status":"PARTIAL_SOURCE_WINDOW"}
        for ref in partial_refs
    ]
    return report


def _reference_payload(ref: ReferenceCandle, tick_size: float) -> dict[str, object]:
    return {
        "symbol":ref.symbol,"start":ref.start.isoformat(),"interval_seconds":ref.interval_seconds,
        "open":ref.open_ticks*tick_size,"high":ref.high_ticks*tick_size,"low":ref.low_ticks*tick_size,"close":ref.close_ticks*tick_size,
        "volume":ref.volume,"trades":ref.trades,"source":ref.source,
    }


def _candle_payload(candle: Candle, tick_size: float) -> dict[str, object]:
    return {
        "symbol":candle.symbol,"start":candle.start.isoformat(),"interval_seconds":candle.interval_seconds,
        "open":candle.open_ticks*tick_size,"high":candle.high_ticks*tick_size,"low":candle.low_ticks*tick_size,"close":candle.close_ticks*tick_size,
        "volume":candle.volume,"trades":candle.trades,
    }
