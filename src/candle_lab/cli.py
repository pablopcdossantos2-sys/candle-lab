from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from .importers import import_csv_with_report
from .quality import QUALITY_MODEL_VERSION, assess_library_quality
from .reconciliation import import_reference_candles, reconcile_candles, reconcile_observed_window
from .research import build_research_index, research_matches
from .trajectory import TRAJECTORY_MODEL_VERSION, analyze_trajectory_families
from .transitions import TRANSITION_MODEL_VERSION, analyze_stability_and_transitions
from .bulk import bulk_import_profit_file, export_session_parquet, reconcile_store_references
from .slice import slice_profit_trades
from .time_index import ensure_time_index, index_summary, locate_candles, locate_interval


def _analyze(args):
    trades,report=import_csv_with_report(args.csv,symbol=args.symbol or None,tick_size=args.tick_size,source=args.source)
    from .candles import build_candles
    payload={"import_report":report.to_dict(),"candles":[c.__dict__ if hasattr(c,"__dict__") else {
        "symbol":c.symbol,"start":c.start.isoformat(),"open_ticks":c.open_ticks,"high_ticks":c.high_ticks,
        "low_ticks":c.low_ticks,"close_ticks":c.close_ticks,"volume":c.volume,"trades":c.trades}
        for c in build_candles(trades,args.interval)]}
    print(json.dumps(payload,default=str,ensure_ascii=False,indent=2))


def _import(args):
    from .storage import MarketStore
    store=MarketStore(args.db)
    trades,report=import_csv_with_report(args.csv,symbol=args.symbol or None,tick_size=args.tick_size,source=args.source)
    result=store.add_trades(trades,tick_size=args.tick_size)
    store.record_import_batch(data_kind="trades",source=args.source,file_name=Path(args.csv).name,symbol=trades[0].symbol,
        first_ts=trades[0].ts.isoformat(),last_ts=trades[-1].ts.isoformat(),rows_received=result["received"],
        rows_inserted=result["inserted"],duplicates=result["duplicates"],diagnostics=report.to_dict())
    store.replace_session_quality(trades[0].symbol,assess_library_quality(store.load_trades(trades[0].symbol)))
    parquet=store.export_parquet(args.parquet)
    print(json.dumps({**result,"symbol":trades[0].symbol,"parquet":str(parquet),"report":report.to_dict()},ensure_ascii=False,default=str,indent=2))


def _reconcile(args):
    trades,_=import_csv_with_report(args.trades_csv,symbol=args.symbol or None,tick_size=args.tick_size,source=args.trade_source)
    refs,_=import_reference_candles(args.reference_csv,symbol=args.symbol or None,tick_size=args.tick_size,
        interval_seconds=args.interval,source=args.reference_source)
    print(json.dumps(reconcile_candles(trades,refs,interval_seconds=args.interval,tick_size=args.tick_size),ensure_ascii=False,default=str,indent=2))


def _empirical_validate(args):
    trades, trade_report = import_csv_with_report(
        args.trades_csv, symbol=args.symbol or None, tick_size=args.tick_size, source=args.trade_source
    )
    refs, reference_report = import_reference_candles(
        args.reference_csv, symbol=args.symbol or None, tick_size=args.tick_size,
        interval_seconds=args.interval, source=args.reference_source
    )
    reconciliation = reconcile_observed_window(
        trades, refs, interval_seconds=args.interval, tick_size=args.tick_size
    )
    payload = {
        "method": "validação empírica v0.10 — somente candles totalmente cobertos pelo recorte de trades",
        "trade_import_report": trade_report.to_dict(),
        "reference_import_report": reference_report.to_dict(),
        "reconciliation": reconciliation,
        "limitations": [
            "Timestamps e sequência são limitados pela precisão e pelo layout da fonte exportada.",
            "Candles de fronteira incompletos são excluídos da taxa de reconciliação.",
            "Coincidência OHLC valida reconstrução contra esta referência; não certifica a fonte de mercado.",
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, default=str, indent=2))


def _index_progress(info: dict[str, object]) -> None:
    if info.get("phase") != "index":
        return
    print(
        f"\rIndexando: {float(info.get('percent') or 0):6.2f}% · "
        f"{int(info.get('rows') or 0):,} linhas · "
        f"{int(info.get('minutes_indexed') or 0):,} minutos",
        end="",flush=True,
    )


def _index_trades(args):
    index,built=ensure_time_index(
        args.trades_csv,index_dir=args.index_dir,symbol=args.symbol or None,progress=_index_progress
    )
    if built:print()
    print(json.dumps({"built_now":built,**index_summary(index)},ensure_ascii=False,default=str,indent=2))


def _locate_lines(args):
    start=datetime.fromisoformat(args.start)
    end=datetime.fromisoformat(args.end)
    index,built=ensure_time_index(
        args.trades_csv,index_dir=args.index_dir,symbol=args.symbol or None,progress=_index_progress
    )
    if built:print()
    payload={"built_now":built,"index":index_summary(index),"selection":locate_interval(index,start=start,end=end)}
    if args.interval:
        starts=[]
        cursor=start
        while cursor<end:
            starts.append(cursor);cursor+=timedelta(seconds=args.interval)
        payload["candles"]=locate_candles(index,candle_starts=starts,interval_seconds=args.interval)
    print(json.dumps(payload,ensure_ascii=False,default=str,indent=2))


def _slice_trades(args):
    start=datetime.fromisoformat(args.start)
    end=datetime.fromisoformat(args.end)
    index,built=ensure_time_index(
        args.trades_csv,index_dir=args.index_dir,symbol=args.symbol or None,progress=_index_progress
    )
    if built:print()
    located=locate_interval(index,start=start,end=end)
    result=slice_profit_trades(
        args.trades_csv,start=start,end=end,
        output_path=args.output or None,symbol=args.symbol or None,
        seek_byte_start=int(located["byte_start"]),seek_byte_end=int(located["byte_end"]),
        source_row_base=int(located["source_row_min"])-1,
    )
    print(json.dumps({
        "index_built_now":built,"index":index_summary(index),"locator":located,
        "slice":result.to_dict()
    },ensure_ascii=False,default=str,indent=2))


def _bulk_progress(info: dict[str, object]) -> None:
    phase = info.get("phase")
    if phase == "hash":
        print("[1/4] Calculando hash SHA-256 do arquivo...", flush=True)
        return
    if phase == "import":
        percent = float(info.get("percent") or 0.0)
        rows = int(info.get("processed_rows") or 0)
        inserted = int(info.get("inserted_rows") or 0)
        done = int(info.get("bytes_processed") or 0) / (1024 * 1024)
        total = int(info.get("bytes_total") or 0) / (1024 * 1024)
        print(
            f"\r[2/4] Importando: {percent:6.2f}% · {rows:,} linhas · "
            f"{done:,.1f}/{total:,.1f} MiB · inseridas {inserted:,}",
            end="",
            flush=True,
        )


def _write_bulk_report(payload: dict[str, object], output: Path) -> tuple[Path, Path]:
    output.parent.mkdir(parents=True, exist_ok=True)
    json_path = output.with_suffix(".json")
    html_path = output.with_suffix(".html")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, default=str, indent=2), encoding="utf-8")

    validations = list(payload.get("validations") or [])
    cards = []
    for validation in validations:
        summary = dict(validation.get("summary") or {})
        window = dict(validation.get("observed_window") or {})
        cards.append(f"""
        <section class="card">
          <h2>{validation.get('symbol')} · {validation.get('session_date')}</h2>
          <div class="kpis">
            <div><span>Trades</span><strong>{int(window.get('trade_rows') or 0):,}</strong></div>
            <div><span>Referências</span><strong>{int(summary.get('reference_candles') or 0):,}</strong></div>
            <div><span>EXACT</span><strong>{int(summary.get('exact') or 0):,}</strong></div>
            <div><span>Divergentes</span><strong>{int(summary.get('mismatch') or 0):,}</strong></div>
            <div><span>Taxa exata</span><strong>{float(summary.get('exact_rate') or 0)*100:.2f}%</strong></div>
          </div>
        </section>""")

    bulk = dict(payload.get("bulk_import") or {})
    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
    <title>Validação empírica Candle Lab</title>
    <style>body{{font-family:Segoe UI,Arial;background:#081018;color:#e5eef7;margin:0;padding:32px}}
    main{{max-width:1100px;margin:auto}}.card{{background:#101b26;border:1px solid #26394c;border-radius:14px;padding:20px;margin:14px 0}}
    .kpis{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}}.kpis div{{background:#09131d;padding:12px;border-radius:10px}}
    span{{display:block;color:#8fa2b5;font-size:12px}}strong{{font-size:22px}}code{{color:#7cc4ff}}
    @media(max-width:800px){{.kpis{{grid-template-columns:1fr 1fr}}}}</style></head>
    <body><main><h1>Candle Lab B3 — validação empírica v0.11</h1>
    <section class="card"><h2>Ingestão</h2><p>Arquivo: <code>{bulk.get('file_name','')}</code></p>
    <p>Linhas processadas: <strong>{int(bulk.get('processed_rows') or 0):,}</strong> ·
    Tempo: <strong>{float(bulk.get('elapsed_seconds') or 0):.1f}s</strong> ·
    Pico Python: <strong>{float(bulk.get('python_peak_memory_mb') or 0):.1f} MiB</strong></p></section>
    {''.join(cards)}
    <section class="card"><p>As frequências e coincidências são descritivas do conjunto importado.
    Este relatório não constitui recomendação ou previsão de mercado.</p></section>
    </main></body></html>"""
    html_path.write_text(html, encoding="utf-8")
    return json_path, html_path


def _bulk_import(args):
    from .storage import MarketStore
    store = MarketStore(args.db)
    result = bulk_import_profit_file(
        args.trades_csv,
        store=store,
        tick_size=args.tick_size,
        symbol=args.symbol or None,
        source=args.source,
        chunk_rows=args.chunk_rows,
        resume=not args.no_resume,
        progress=_bulk_progress,
    )
    print()
    print(json.dumps(result.to_dict(), ensure_ascii=False, default=str, indent=2))


def _bulk_validate(args):
    from .storage import MarketStore
    store = MarketStore(args.db)
    bulk = bulk_import_profit_file(
        args.trades_csv,
        store=store,
        tick_size=args.tick_size,
        symbol=args.symbol or None,
        source=args.trade_source,
        chunk_rows=args.chunk_rows,
        resume=not args.no_resume,
        progress=_bulk_progress,
    )
    print()
    print("[3/4] Importando referência OHLC e reconciliando...", flush=True)

    refs, reference_report = import_reference_candles(
        args.reference_csv,
        symbol=bulk.symbol,
        tick_size=args.tick_size,
        interval_seconds=args.interval,
        source=args.reference_source,
    )
    store.add_reference_candles(refs, tick_size=args.tick_size)

    validations = []
    parquet_files = []
    for session_date in bulk.session_dates:
        day_refs = [r for r in refs if r.start.date().isoformat() == session_date]
        if not day_refs:
            continue
        validation = reconcile_store_references(
            store,
            symbol=bulk.symbol,
            session_date=session_date,
            references=day_refs,
            interval_seconds=args.interval,
            tick_size=args.tick_size,
        )
        validations.append(validation)
        parquet_files.append(
            str(export_session_parquet(store, symbol=bulk.symbol, session_date=session_date, output_dir=args.parquet_dir))
        )

    payload = {
        "method": "Candle Lab v0.11 — ingestão massiva em chunks + reconciliação SQL",
        "bulk_import": bulk.to_dict(),
        "reference_report": reference_report.to_dict(),
        "validations": validations,
        "parquet_files": parquet_files,
        "limitations": [
            "A sequência intrassegundo deriva da ordem preservada pelo arquivo do Profit.",
            "O layout recebido não contém Número do Negócio.",
            "Candles de fronteira incompletos não entram na taxa de reconciliação.",
            "A coincidência valida a reconstrução contra a referência fornecida; não certifica a fonte de mercado.",
        ],
    }

    report_base = Path(args.report) if args.report else Path("data/reports") / f"{bulk.symbol}_validacao_v011"
    json_path, html_path = _write_bulk_report(payload, report_base)
    print(f"[4/4] Concluído. Relatórios: {json_path} | {html_path}")
    print(json.dumps({
        "bulk_import": bulk.to_dict(),
        "validations": [v["summary"] for v in validations],
        "report_json": str(json_path),
        "report_html": str(html_path),
        "parquet_files": parquet_files,
    }, ensure_ascii=False, default=str, indent=2))


def _ensure(store,symbol,interval,force=False):
    status=store.research_index_status(symbol,interval)
    if force or not status["indexed"] or status["stale"]:
        features=build_research_index(store.load_trades(symbol),interval);store.replace_research_index(symbol,interval,features)
    return store.load_research_index(symbol,interval)


def _research(args):
    from .storage import MarketStore
    store=MarketStore(args.db);symbol=args.symbol.upper();features=_ensure(store,symbol,args.interval,args.reindex)
    result=research_matches(features,target_start=datetime.fromisoformat(args.start),limit=args.limit,same_time=args.same_time,
        time_tolerance_minutes=args.time_tolerance,same_volatility=args.same_volatility,same_regime=args.same_regime,
        same_context_regime=args.same_context_regime,quality_only=not args.include_low_quality,
        other_sessions_only=not args.include_same_session)
    print(json.dumps(result,ensure_ascii=False,default=str,indent=2))


def _quality(args):
    from .storage import MarketStore
    store=MarketStore(args.db);symbol=args.symbol.upper();qualities=assess_library_quality(store.load_trades(symbol))
    store.replace_session_quality(symbol,qualities)
    print(json.dumps({"symbol":symbol,"quality_model_version":QUALITY_MODEL_VERSION,"sessions":[q.to_record() for q in qualities]},ensure_ascii=False,default=str,indent=2))


def _trajectory(args):
    from .storage import MarketStore
    store=MarketStore(args.db);symbol=args.symbol.upper();trades=store.load_trades(symbol);features=_ensure(store,symbol,args.interval)
    result=analyze_trajectory_families(trades,interval_seconds=args.interval,research_features=features,
        quality_only=not args.include_low_quality,clusters=args.clusters or None,sample_points=args.sample_points)
    result["trajectory_model_version"]=TRAJECTORY_MODEL_VERSION
    print(json.dumps(result,ensure_ascii=False,default=str,indent=2))


def _transitions(args):
    from .storage import MarketStore
    store=MarketStore(args.db);symbol=args.symbol.upper();trades=store.load_trades(symbol);features=_ensure(store,symbol,args.interval)
    result=analyze_stability_and_transitions(trades,interval_seconds=args.interval,research_features=features,
        quality_only=not args.include_low_quality,clusters=args.clusters or None,sample_points=args.sample_points,
        target_start=datetime.fromisoformat(args.start) if args.start else None)
    result["transition_model_version"]=TRANSITION_MODEL_VERSION
    print(json.dumps(result,ensure_ascii=False,default=str,indent=2))


def _serve(args):
    import os,uvicorn
    if args.db:os.environ["CANDLE_LAB_DB"]=str(Path(args.db).resolve())
    uvicorn.run("candle_lab.web.app:app",host=args.host,port=args.port,reload=False)


def main():
    parser=argparse.ArgumentParser(description="Candle Lab B3")
    sub=parser.add_subparsers(dest="command")
    p=sub.add_parser("analyze");p.add_argument("csv");p.add_argument("--symbol",default="");p.add_argument("--tick-size",type=float,required=True);p.add_argument("--interval",type=int,default=60);p.add_argument("--source",default="csv")
    p=sub.add_parser("import");p.add_argument("csv");p.add_argument("--symbol",default="");p.add_argument("--tick-size",type=float,required=True);p.add_argument("--source",default="csv");p.add_argument("--db",default="data/candle_lab.duckdb");p.add_argument("--parquet",default="data/parquet/trades.parquet")
    p=sub.add_parser("reconcile");p.add_argument("trades_csv");p.add_argument("reference_csv");p.add_argument("--symbol",default="");p.add_argument("--tick-size",type=float,required=True);p.add_argument("--interval",type=int,required=True);p.add_argument("--trade-source",default="profit_csv");p.add_argument("--reference-source",default="profit_ohlc_reference")
    p=sub.add_parser("empirical-validate");p.add_argument("trades_csv");p.add_argument("reference_csv");p.add_argument("--symbol",default="");p.add_argument("--tick-size",type=float,required=True);p.add_argument("--interval",type=int,default=60);p.add_argument("--trade-source",default="profit_csv");p.add_argument("--reference-source",default="profit_ohlc_reference")
    p=sub.add_parser("index-trades");p.add_argument("trades_csv");p.add_argument("--symbol",default="");p.add_argument("--index-dir",default="data/indexes")
    p=sub.add_parser("locate-lines");p.add_argument("trades_csv");p.add_argument("--start",required=True);p.add_argument("--end",required=True);p.add_argument("--symbol",default="");p.add_argument("--interval",type=int,default=60);p.add_argument("--index-dir",default="data/indexes")
    p=sub.add_parser("slice-trades");p.add_argument("trades_csv");p.add_argument("--start",required=True);p.add_argument("--end",required=True);p.add_argument("--symbol",default="");p.add_argument("--output",default="");p.add_argument("--index-dir",default="data/indexes")
    p=sub.add_parser("bulk-import");p.add_argument("trades_csv");p.add_argument("--symbol",default="");p.add_argument("--tick-size",type=float,required=True);p.add_argument("--source",default="profit_bulk_csv");p.add_argument("--chunk-rows",type=int,default=100000);p.add_argument("--no-resume",action="store_true");p.add_argument("--db",default="data/candle_lab.duckdb")
    p=sub.add_parser("bulk-validate");p.add_argument("trades_csv");p.add_argument("reference_csv");p.add_argument("--symbol",default="");p.add_argument("--tick-size",type=float,required=True);p.add_argument("--interval",type=int,default=60);p.add_argument("--chunk-rows",type=int,default=100000);p.add_argument("--trade-source",default="profit_bulk_csv");p.add_argument("--reference-source",default="profit_ohlc_reference");p.add_argument("--no-resume",action="store_true");p.add_argument("--db",default="data/candle_lab.duckdb");p.add_argument("--parquet-dir",default="data/parquet");p.add_argument("--report",default="")
    p=sub.add_parser("quality");p.add_argument("--symbol",required=True);p.add_argument("--db",default="data/candle_lab.duckdb")
    p=sub.add_parser("research");p.add_argument("--symbol",required=True);p.add_argument("--start",required=True);p.add_argument("--interval",type=int,default=60);p.add_argument("--limit",type=int,default=8);p.add_argument("--same-time",action="store_true");p.add_argument("--time-tolerance",type=int,default=20);p.add_argument("--same-volatility",action="store_true");p.add_argument("--same-regime",action="store_true");p.add_argument("--same-context-regime",action="store_true");p.add_argument("--include-low-quality",action="store_true");p.add_argument("--include-same-session",action="store_true");p.add_argument("--reindex",action="store_true");p.add_argument("--db",default="data/candle_lab.duckdb")
    p=sub.add_parser("trajectory");p.add_argument("--symbol",required=True);p.add_argument("--interval",type=int,default=60);p.add_argument("--clusters",type=int,default=0);p.add_argument("--sample-points",type=int,default=25);p.add_argument("--include-low-quality",action="store_true");p.add_argument("--db",default="data/candle_lab.duckdb")
    p=sub.add_parser("transitions");p.add_argument("--symbol",required=True);p.add_argument("--interval",type=int,default=60);p.add_argument("--clusters",type=int,default=0);p.add_argument("--sample-points",type=int,default=25);p.add_argument("--start",default="");p.add_argument("--include-low-quality",action="store_true");p.add_argument("--db",default="data/candle_lab.duckdb")
    p=sub.add_parser("serve");p.add_argument("--host",default="127.0.0.1");p.add_argument("--port",type=int,default=8765);p.add_argument("--db",default=None)
    args=parser.parse_args()
    actions={"analyze":_analyze,"import":_import,"reconcile":_reconcile,"empirical-validate":_empirical_validate,"index-trades":_index_trades,"locate-lines":_locate_lines,"slice-trades":_slice_trades,"bulk-import":_bulk_import,"bulk-validate":_bulk_validate,"quality":_quality,"research":_research,"trajectory":_trajectory,"transitions":_transitions,"serve":_serve}
    actions.get(args.command,lambda _:parser.print_help())(args)

if __name__=="__main__":main()
