from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .importers import import_csv_with_report
from .quality import QUALITY_MODEL_VERSION, assess_library_quality
from .reconciliation import import_reference_candles, reconcile_candles, reconcile_observed_window
from .research import build_research_index, research_matches
from .trajectory import TRAJECTORY_MODEL_VERSION, analyze_trajectory_families
from .transitions import TRANSITION_MODEL_VERSION, analyze_stability_and_transitions


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
    p=sub.add_parser("quality");p.add_argument("--symbol",required=True);p.add_argument("--db",default="data/candle_lab.duckdb")
    p=sub.add_parser("research");p.add_argument("--symbol",required=True);p.add_argument("--start",required=True);p.add_argument("--interval",type=int,default=60);p.add_argument("--limit",type=int,default=8);p.add_argument("--same-time",action="store_true");p.add_argument("--time-tolerance",type=int,default=20);p.add_argument("--same-volatility",action="store_true");p.add_argument("--same-regime",action="store_true");p.add_argument("--same-context-regime",action="store_true");p.add_argument("--include-low-quality",action="store_true");p.add_argument("--include-same-session",action="store_true");p.add_argument("--reindex",action="store_true");p.add_argument("--db",default="data/candle_lab.duckdb")
    p=sub.add_parser("trajectory");p.add_argument("--symbol",required=True);p.add_argument("--interval",type=int,default=60);p.add_argument("--clusters",type=int,default=0);p.add_argument("--sample-points",type=int,default=25);p.add_argument("--include-low-quality",action="store_true");p.add_argument("--db",default="data/candle_lab.duckdb")
    p=sub.add_parser("transitions");p.add_argument("--symbol",required=True);p.add_argument("--interval",type=int,default=60);p.add_argument("--clusters",type=int,default=0);p.add_argument("--sample-points",type=int,default=25);p.add_argument("--start",default="");p.add_argument("--include-low-quality",action="store_true");p.add_argument("--db",default="data/candle_lab.duckdb")
    p=sub.add_parser("serve");p.add_argument("--host",default="127.0.0.1");p.add_argument("--port",type=int,default=8765);p.add_argument("--db",default=None)
    args=parser.parse_args()
    actions={"analyze":_analyze,"import":_import,"reconcile":_reconcile,"empirical-validate":_empirical_validate,"quality":_quality,"research":_research,"trajectory":_trajectory,"transitions":_transitions,"serve":_serve}
    actions.get(args.command,lambda _:parser.print_help())(args)

if __name__=="__main__":main()
