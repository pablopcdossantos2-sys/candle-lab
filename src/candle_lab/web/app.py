from __future__ import annotations

from datetime import date, datetime, timedelta
import os
import threading
import uuid
from typing import Callable
from pathlib import Path
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..candles import build_candles, floor_time
from ..importers import import_csv_with_report, import_generic_csv
from ..reconciliation import ReferenceCandle, import_reference_candles, reconcile_candles, reconcile_observed_window, reconcile_available_candles
from ..research import build_research_index, intrabar_comparison_payload, research_matches
from ..quality import assess_library_quality
from ..services import candle_detail_payload, candle_payload, similar_candles_payload
from ..trajectory import analyze_trajectory_families
from ..transitions import analyze_stability_and_transitions
from ..storage import MarketStore
from ..sample import generate_builtin_sample
from ..slice import slice_profit_trades
from ..time_index import ensure_time_index, index_summary, locate_candles, locate_interval

PACKAGE_DIR=Path(__file__).resolve().parent
STATIC_DIR=PACKAGE_DIR/"static"
PROJECT_ROOT=Path(__file__).resolve().parents[3]
DEFAULT_DB=Path(os.environ.get("CANDLE_LAB_DB",PROJECT_ROOT/"data"/"candle_lab.duckdb"))
DEFAULT_PARQUET=Path(os.environ.get("CANDLE_LAB_PARQUET",PROJECT_ROOT/"data"/"parquet"/"trades.parquet"))
VERSION="0.17.0"


class TimeIndexRequest(BaseModel):
    source_path: str
    symbol: str
    start: datetime
    end: datetime
    interval_seconds: int = 60
    candle_starts: list[datetime] = Field(default_factory=list)


class SliceImportRequest(BaseModel):
    source_path: str
    symbol: str
    start: datetime
    end: datetime
    tick_size: float = 5.0
    interval_seconds: int = 60
    candle_starts: list[datetime] = Field(default_factory=list)


def create_app(db_path:str|Path=DEFAULT_DB)->FastAPI:
    app=FastAPI(title="Candle Lab B3",version=VERSION)
    store=MarketStore(db_path);app.state.store=store
    index_jobs:dict[str,dict[str,object]]={}
    index_jobs_lock=threading.Lock()
    slice_jobs:dict[str,dict[str,object]]={}
    slice_jobs_lock=threading.Lock()
    app.state.index_jobs=index_jobs
    app.state.slice_jobs=slice_jobs
    app.mount("/static",StaticFiles(directory=STATIC_DIR),name="static")

    def _set_index_job(job_id:str,**changes:object)->None:
        with index_jobs_lock:
            current=index_jobs.setdefault(job_id,{"job_id":job_id})
            current.update(changes)

    def _get_index_job(job_id:str)->dict[str,object]|None:
        with index_jobs_lock:
            current=index_jobs.get(job_id)
            return dict(current) if current is not None else None

    def _set_slice_job(job_id:str,**changes:object)->None:
        with slice_jobs_lock:
            current=slice_jobs.setdefault(job_id,{"job_id":job_id})
            current.update(changes)

    def _get_slice_job(job_id:str)->dict[str,object]|None:
        with slice_jobs_lock:
            current=slice_jobs.get(job_id)
            return dict(current) if current is not None else None

    @app.get("/")
    def root():return FileResponse(STATIC_DIR/"index.html")

    @app.get("/api/status")
    def status():return {"version":VERSION,**store.stats()}

    @app.get("/api/symbols")
    def symbols():return store.list_symbols()

    @app.get("/api/sessions")
    def sessions(symbol:str):return store.list_sessions(symbol.strip().upper())

    @app.get("/api/reference-overview")
    def reference_overview():return store.reference_overview()

    @app.get("/api/reference-sessions")
    def reference_sessions(symbol:str):return store.list_reference_sessions(symbol.strip().upper())

    @app.get("/api/reference-candles")
    def reference_candles(symbol:str,session_date:date,interval_seconds:int=Query(60,ge=1,le=3600)):
        symbol=symbol.strip().upper()
        refs=store.load_reference_candles(symbol,session_date=session_date,interval_seconds=interval_seconds)
        tick=store.tick_size(symbol)
        return [{
            "symbol":r.symbol,"start":r.start.isoformat(),"end":r.end.isoformat(),
            "open":r.open_ticks*tick,"high":r.high_ticks*tick,"low":r.low_ticks*tick,"close":r.close_ticks*tick,
            "volume":r.volume,"trades":r.trades,"source":r.source
        } for r in refs]

    @app.get("/api/session-quality")
    def session_quality(symbol:str,session_date:date):
        symbol=symbol.strip().upper();payload=store.get_session_quality(symbol,session_date)
        if payload is not None:return payload
        session_trades=store.load_trades(symbol,session_date=session_date)
        if not session_trades:raise HTTPException(status_code=404,detail="Pregão não encontrado")
        qualities=assess_library_quality(store.load_trades(symbol));store.replace_session_quality(symbol,qualities)
        return next(q for q in qualities if q.session_date==session_date).to_record()

    @app.get("/api/library")
    def library():return store.library_overview()

    @app.get("/api/import-batches")
    def import_batches(limit:int=Query(30,ge=1,le=500)):return store.list_import_batches(limit)

    async def _save_upload(file: UploadFile, suffix: str) -> Path:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            while True:
                chunk = await file.read(8 * 1024 * 1024)
                if not chunk:
                    break
                temp.write(chunk)
            return Path(temp.name)

    @app.post("/api/import-csv")
    async def import_csv(file:UploadFile=File(...),symbol:str=Form(""),tick_size:float=Form(...),source:str=Form("profit_csv")):
        suffix=Path(file.filename or "trades.csv").suffix or ".csv"
        temp_path = await _save_upload(file, suffix)
        try:
            trades,report=import_csv_with_report(temp_path,symbol=symbol or None,tick_size=tick_size,source=source)
            result=store.add_trades(trades,tick_size=tick_size)
            batch_id=store.record_import_batch(data_kind="trades",source=source,file_name=file.filename or "trades.csv",
                symbol=trades[0].symbol,first_ts=trades[0].ts.isoformat(),last_ts=trades[-1].ts.isoformat(),
                rows_received=result["received"],rows_inserted=result["inserted"],duplicates=result["duplicates"],diagnostics=report.to_dict())
            all_symbol_trades=store.load_trades(trades[0].symbol)
            store.replace_session_quality(trades[0].symbol,assess_library_quality(all_symbol_trades))
            parquet=store.export_parquet(DEFAULT_PARQUET)
            return {**result,"batch_id":batch_id,"symbol":trades[0].symbol,"sessions":report.session_dates,"parquet":str(parquet),"report":report.to_dict()}
        except Exception as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
        finally:temp_path.unlink(missing_ok=True)

    @app.post("/api/import-reference")
    async def import_reference(file:UploadFile=File(...),symbol:str=Form(""),tick_size:float=Form(...),
        interval_seconds:int=Form(...),source:str=Form("profit_ohlc_reference")):
        suffix=Path(file.filename or "reference.csv").suffix or ".csv"
        temp_path = await _save_upload(file, suffix)
        try:
            refs,report=import_reference_candles(temp_path,symbol=symbol or None,tick_size=tick_size,interval_seconds=interval_seconds,source=source)
            result=store.add_reference_candles(refs,tick_size=tick_size)
            batch_id=store.record_import_batch(data_kind="reference",source=source,file_name=file.filename or "reference.csv",
                symbol=refs[0].symbol,first_ts=refs[0].start.isoformat(),last_ts=refs[-1].start.isoformat(),
                rows_received=result["received"],rows_inserted=result["inserted"],duplicates=result["duplicates"],diagnostics=report.to_dict())
            return {**result,"batch_id":batch_id,"symbol":refs[0].symbol,"report":report.to_dict()}
        except Exception as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
        finally:temp_path.unlink(missing_ok=True)

    @app.post("/api/time-index/start")
    def time_index_start(request:TimeIndexRequest):
        symbol=request.symbol.strip().upper()
        if not symbol:raise HTTPException(status_code=400,detail="Informe o contrato real.")
        if request.end <= request.start:raise HTTPException(status_code=400,detail="O fim precisa ser posterior ao início.")
        if request.interval_seconds <= 0:raise HTTPException(status_code=400,detail="interval_seconds deve ser positivo.")

        job_id=uuid.uuid4().hex
        _set_index_job(job_id,status="queued",progress={
            "phase":"queued","percent":0.0,"rows":0,"bytes_processed":0,"bytes_total":0,"minutes_indexed":0
        })

        source_path=request.source_path
        start=request.start
        end=request.end
        interval_seconds=request.interval_seconds
        candle_starts=list(request.candle_starts)

        def worker():
            _set_index_job(job_id,status="running")
            try:
                def on_progress(info:dict[str,object])->None:
                    _set_index_job(job_id,status="running",progress=dict(info))

                index,built=ensure_time_index(
                    source_path,index_dir=PROJECT_ROOT/"data"/"indexes",symbol=symbol,progress=on_progress
                )
                interval=locate_interval(index,start=start,end=end)
                starts=candle_starts or [start]
                candles=locate_candles(index,candle_starts=starts,interval_seconds=interval_seconds)
                result={
                    "index_built_now":built,
                    "index":index_summary(index),
                    "selection":interval,
                    "candles":candles,
                    "rule":"Uma linha pertence ao candle quando candle_start <= timestamp < candle_end.",
                }
                _set_index_job(job_id,status="completed",progress={
                    "phase":"completed","percent":100.0,"rows":index.rows,
                    "bytes_processed":index.source_size,"bytes_total":index.source_size,
                    "minutes_indexed":len(index.buckets)
                },result=result)
            except Exception as exc:
                _set_index_job(job_id,status="failed",error=str(exc))

        threading.Thread(target=worker,name=f"candle-lab-index-{job_id[:8]}",daemon=True).start()
        return {"job_id":job_id,"status":"queued"}

    @app.get("/api/time-index/jobs/{job_id}")
    def time_index_job(job_id:str):
        payload=_get_index_job(job_id)
        if payload is None:raise HTTPException(status_code=404,detail="Tarefa de indexação não encontrada.")
        return payload

    @app.post("/api/time-index/locate")
    def time_index_locate(request:TimeIndexRequest):
        symbol=request.symbol.strip().upper()
        if not symbol:raise HTTPException(status_code=400,detail="Informe o contrato real.")
        if request.end <= request.start:raise HTTPException(status_code=400,detail="O fim precisa ser posterior ao início.")
        if request.interval_seconds <= 0:raise HTTPException(status_code=400,detail="interval_seconds deve ser positivo.")
        try:
            index,built=ensure_time_index(
                request.source_path,index_dir=PROJECT_ROOT/"data"/"indexes",symbol=symbol
            )
            interval=locate_interval(index,start=request.start,end=request.end)
            starts=request.candle_starts or [request.start]
            candles=locate_candles(index,candle_starts=starts,interval_seconds=request.interval_seconds)
            return {
                "index_built_now":built,
                "index":index_summary(index),
                "selection":interval,
                "candles":candles,
                "rule":"Uma linha pertence ao candle quando candle_start <= timestamp < candle_end.",
            }
        except Exception as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc

    def _validate_slice_request(request:SliceImportRequest)->str:
        symbol=request.symbol.strip().upper()
        if not symbol:raise ValueError("Informe o contrato real.")
        if request.end <= request.start:raise ValueError("O fim precisa ser posterior ao início.")
        duration=(request.end-request.start).total_seconds()
        if duration > 3*60*60:
            raise ValueError("Selecione no máximo 3 horas por recorte para a análise profunda.")
        return symbol

    def _execute_slice_import(
        request:SliceImportRequest,
        progress:Callable[[dict[str,object]],None]|None=None,
    )->dict[str,object]:
        symbol=_validate_slice_request(request)

        def emit(percent:float,phase:str,message:str,**details:object)->None:
            if progress:
                progress({
                    "percent":round(max(0.0,min(100.0,float(percent))),2),
                    "phase":phase,
                    "message":message,
                    **details,
                })

        emit(1,"preparing","Validando o índice temporal e a seleção.")
        def index_progress(info:dict[str,object])->None:
            p=float(info.get("percent") or 0.0)
            emit(
                1 + p*0.14,"index",
                "Reconstruindo o índice temporal necessário ao recorte.",
                index_percent=p,
                bytes_processed=info.get("bytes_processed",0),
                bytes_total=info.get("bytes_total",0),
                rows=info.get("rows",0),
            )

        index,built=ensure_time_index(
            request.source_path,index_dir=PROJECT_ROOT/"data"/"indexes",
            symbol=symbol,progress=index_progress
        )
        emit(15,"locating","Índice pronto. Localizando os bytes exatos do intervalo.",
             index_built_now=built)
        located=locate_interval(index,start=request.start,end=request.end)

        output_dir=PROJECT_ROOT/"data"/"slices"
        output_name=f"{symbol}_{request.start.strftime('%Y%m%d-%H%M%S')}_{request.end.strftime('%H%M%S')}_TRADES.csv"

        def extract_progress(info:dict[str,object])->None:
            p=float(info.get("percent") or 0.0)
            emit(
                15 + p*0.60,"extract",
                "Extraindo os negócios do intervalo localizado.",
                extract_percent=p,
                bytes_processed=info.get("bytes_processed",0),
                bytes_total=info.get("bytes_total",0),
                scanned_rows=info.get("scanned_rows",0),
                matched_rows=info.get("matched_rows",0),
            )

        sliced=slice_profit_trades(
            request.source_path,start=request.start,end=request.end,
            output_path=output_dir/output_name,symbol=symbol,
            seek_byte_start=int(located["byte_start"]),
            seek_byte_end=int(located["byte_end"]),
            source_row_base=int(located["source_row_min"])-1,
            progress=extract_progress,
        )

        emit(
            80,"normalize","Recorte criado. Normalizando e validando os negócios.",
            matched_rows=sliced.matched_rows,
            output_bytes=sliced.output_size,
        )
        trades,report=import_csv_with_report(
            sliced.output_path,symbol=symbol,tick_size=request.tick_size,source="profit_selected_slice"
        )

        emit(90,"store","Negócios validados. Gravando o recorte na biblioteca local.",
             trades=len(trades))
        if sliced.source_order=="DESCENDING":
            source_rows=range(sliced.last_source_row,sliced.first_source_row-1,-1)
        else:
            source_rows=range(sliced.first_source_row,sliced.last_source_row+1)
        result=store.add_selected_slice_trades(
            trades,tick_size=request.tick_size,
            source_fingerprint=index.source_sha256,source_rows=source_rows
        )

        emit(96,"catalog","Gravação concluída. Atualizando metadados e mapa de candles.",
             inserted=result["inserted"],duplicates=result["duplicates"])
        store.record_import_batch(
            data_kind="selected_slice",source="profit_selected_slice",file_name=Path(sliced.output_path).name,
            symbol=symbol,first_ts=trades[0].ts.isoformat(),last_ts=trades[-1].ts.isoformat(),
            rows_received=result["received"],rows_inserted=result["inserted"],duplicates=result["duplicates"],
            diagnostics={"slice":sliced.to_dict(),"import":report.to_dict()}
        )
        starts=request.candle_starts or [request.start]
        line_map=locate_candles(index,candle_starts=starts,interval_seconds=request.interval_seconds)
        payload={
            "slice":sliced.to_dict(),"import":result,"report":report.to_dict(),
            "time_index":{"built_now":built,**index_summary(index)},
            "selection_locator":located,
            "candle_line_map":line_map,
            "message":"Recorte indexado criado e importado. A extração saltou diretamente para a região de bytes do intervalo selecionado."
        }
        emit(
            100,"completed","Recorte criado, validado e importado com sucesso.",
            matched_rows=sliced.matched_rows,inserted=result["inserted"],duplicates=result["duplicates"]
        )
        return payload

    @app.post("/api/slice-import/start")
    def slice_import_start(request:SliceImportRequest):
        try:
            _validate_slice_request(request)
        except ValueError as exc:
            raise HTTPException(status_code=400,detail=str(exc)) from exc

        job_id=uuid.uuid4().hex
        request_copy=request.model_copy(deep=True)
        _set_slice_job(job_id,status="queued",progress={
            "phase":"queued","percent":0.0,"message":"Aguardando início do recorte."
        })

        def worker():
            _set_slice_job(job_id,status="running")
            try:
                def on_progress(info:dict[str,object])->None:
                    _set_slice_job(job_id,status="running",progress=dict(info))
                result=_execute_slice_import(request_copy,progress=on_progress)
                _set_slice_job(job_id,status="completed",progress={
                    "phase":"completed","percent":100.0,
                    "message":"Recorte criado, validado e importado com sucesso."
                },result=result)
            except Exception as exc:
                _set_slice_job(job_id,status="failed",error=str(exc))

        threading.Thread(target=worker,name=f"candle-lab-slice-{job_id[:8]}",daemon=True).start()
        return {"job_id":job_id,"status":"queued"}

    @app.get("/api/slice-import/jobs/{job_id}")
    def slice_import_job(job_id:str):
        payload=_get_slice_job(job_id)
        if payload is None:raise HTTPException(status_code=404,detail="Tarefa de recorte não encontrada.")
        return payload

    @app.post("/api/slice-import")
    def slice_import(request:SliceImportRequest):
        try:
            return _execute_slice_import(request)
        except Exception as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc

    @app.post("/api/load-sample")
    def load_sample():
        try:
            store.reset_builtin_sample("WINLAB06")
            trades=generate_builtin_sample("WINLAB06")
            result=store.add_trades(trades,tick_size=5.0)
            refs=[ReferenceCandle(symbol=c.symbol,start=c.start,interval_seconds=60,open_ticks=c.open_ticks,high_ticks=c.high_ticks,
                low_ticks=c.low_ticks,close_ticks=c.close_ticks,volume=c.volume,trades=c.trades,source="synthetic_truth_v09")
                for c in build_candles(trades,60)]
            ref_result=store.add_reference_candles(refs,tick_size=5.0)
            store.record_import_batch(data_kind="trades",source="synthetic_sample_v09",file_name="synthetic_win.csv",symbol="WINLAB06",
                rows_received=result["received"],rows_inserted=result["inserted"],duplicates=result["duplicates"],
                first_ts=trades[0].ts.isoformat(),last_ts=trades[-1].ts.isoformat(),diagnostics={"note":"Amostra sintética interna para teste funcional v0.9."})
            features=build_research_index(trades,60);store.replace_research_index("WINLAB06",60,features)
            store.replace_session_quality("WINLAB06",assess_library_quality(trades))
            store.export_parquet(DEFAULT_PARQUET)
            return {**result,"reference_inserted":ref_result["inserted"],"symbol":"WINLAB06","session_date":trades[0].ts.date().isoformat()}
        except Exception as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc

    @app.get("/api/candles")
    def candles(symbol:str,session_date:date,interval_seconds:int=Query(60,ge=1,le=3600)):
        trades=store.load_trades(symbol.strip().upper(),session_date=session_date)
        return candle_payload(trades,interval_seconds,store.tick_size(symbol.strip().upper())) if trades else []

    @app.get("/api/reconciliation")
    def reconciliation(symbol:str,session_date:date,interval_seconds:int=Query(60,ge=1,le=3600)):
        symbol=symbol.strip().upper();trades=store.load_trades(symbol,session_date=session_date)
        refs=store.load_reference_candles(symbol,session_date=session_date,interval_seconds=interval_seconds)
        if not refs:return {"interval_seconds":interval_seconds,"summary":{"reference_candles":0,"reconstructed_candles":len(build_candles(trades,interval_seconds)),
            "exact":0,"ohlc_match":0,"mismatch":0,"no_data":0,"ohlc_match_rate":0.0,"exact_rate":0.0},"results":[],
            "message":"Nenhuma referência OHLC importada para este ativo/pregão/intervalo."}
        if any(t.source=="profit_selected_slice" for t in trades):
            return reconcile_available_candles(trades,refs,interval_seconds=interval_seconds,tick_size=store.tick_size(symbol))
        return reconcile_observed_window(trades,refs,interval_seconds=interval_seconds,tick_size=store.tick_size(symbol))

    def _ensure_research_index(symbol:str,interval_seconds:int,*,force:bool=False):
        status=store.research_index_status(symbol,interval_seconds);refreshed=False
        if force or not status["indexed"] or status["stale"]:
            trades=store.load_trades(symbol)
            if not trades:raise HTTPException(status_code=404,detail="Nenhum negócio disponível para indexar")
            features=build_research_index(trades,interval_seconds);store.replace_research_index(symbol,interval_seconds,features)
            store.replace_session_quality(symbol,assess_library_quality(trades));refreshed=True;status=store.research_index_status(symbol,interval_seconds)
        return store.load_research_index(symbol,interval_seconds),status,refreshed

    @app.get("/api/research/index-status")
    def research_index_status(symbol:str,interval_seconds:int=Query(60,ge=1,le=3600)):
        return store.research_index_status(symbol.strip().upper(),interval_seconds)

    @app.post("/api/research/reindex")
    def research_reindex(symbol:str,interval_seconds:int=Query(60,ge=1,le=3600)):
        features,status,_=_ensure_research_index(symbol.strip().upper(),interval_seconds,force=True)
        return {"status":status,"features":len(features),"message":"Índice de pesquisa reconstruído a partir dos negócios armazenados."}

    @app.get("/api/research/search")
    def research_search(symbol:str,start:datetime,interval_seconds:int=Query(60,ge=1,le=3600),limit:int=Query(8,ge=1,le=50),
        same_time:bool=False,time_tolerance_minutes:int=Query(20,ge=0,le=360),same_volatility:bool=False,same_regime:bool=False,
        same_context_regime:bool=False,quality_only:bool=True,other_sessions_only:bool=True):
        symbol=symbol.strip().upper();aligned=floor_time(start,interval_seconds);features,status,refreshed=_ensure_research_index(symbol,interval_seconds)
        try:
            payload=research_matches(features,target_start=aligned,limit=limit,same_time=same_time,time_tolerance_minutes=time_tolerance_minutes,
                same_volatility=same_volatility,same_regime=same_regime,same_context_regime=same_context_regime,
                quality_only=quality_only,other_sessions_only=other_sessions_only)
            payload["index_status"]=status;payload["index_refreshed"]=refreshed;return payload
        except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc

    @app.get("/api/research/compare")
    def research_compare(symbol:str,target_start:datetime,candidate_start:datetime,interval_seconds:int=Query(60,ge=1,le=3600)):
        symbol=symbol.strip().upper();target_start=floor_time(target_start,interval_seconds);candidate_start=floor_time(candidate_start,interval_seconds)
        target=store.load_trades(symbol,start=target_start,end=target_start+timedelta(seconds=interval_seconds))
        candidate=store.load_trades(symbol,start=candidate_start,end=candidate_start+timedelta(seconds=interval_seconds))
        if not target or not candidate:raise HTTPException(status_code=404,detail="Negócios insuficientes para comparar os dois candles")
        features,_,_=_ensure_research_index(symbol,interval_seconds)
        tf=next((f for f in features if f.candle.start==target_start),None);cf=next((f for f in features if f.candle.start==candidate_start),None)
        return intrabar_comparison_payload(target,candidate,interval_seconds=interval_seconds,tick_size=store.tick_size(symbol),target_feature=tf,candidate_feature=cf)

    @app.get("/api/trajectory/families")
    def trajectory_families(symbol:str,interval_seconds:int=Query(60,ge=1,le=3600),clusters:int=Query(0,ge=0,le=20),
        quality_only:bool=True,sample_points:int=Query(25,ge=9,le=81)):
        symbol=symbol.strip().upper();trades=store.load_trades(symbol)
        if not trades:raise HTTPException(status_code=404,detail="Nenhum negócio disponível para analisar trajetórias")
        features,status,refreshed=_ensure_research_index(symbol,interval_seconds)
        payload=analyze_trajectory_families(trades,interval_seconds=interval_seconds,research_features=features,quality_only=quality_only,
            clusters=clusters or None,sample_points=sample_points);payload["research_index_status"]=status;payload["research_index_refreshed"]=refreshed;return payload

    @app.get("/api/trajectory/transitions")
    def trajectory_transitions(symbol:str,interval_seconds:int=Query(60,ge=1,le=3600),clusters:int=Query(0,ge=0,le=20),
        quality_only:bool=True,sample_points:int=Query(25,ge=9,le=81),target_start:datetime|None=None):
        symbol=symbol.strip().upper();trades=store.load_trades(symbol)
        if not trades:raise HTTPException(status_code=404,detail="Nenhum negócio disponível para analisar transições")
        features,status,refreshed=_ensure_research_index(symbol,interval_seconds)
        aligned=floor_time(target_start,interval_seconds) if target_start else None
        payload=analyze_stability_and_transitions(trades,interval_seconds=interval_seconds,research_features=features,quality_only=quality_only,
            clusters=clusters or None,sample_points=sample_points,target_start=aligned)
        payload["research_index_status"]=status;payload["research_index_refreshed"]=refreshed;return payload

    @app.get("/api/candle-detail")
    def candle_detail(symbol:str,start:datetime,interval_seconds:int=Query(60,ge=1,le=3600),seed:int=42):
        symbol=symbol.strip().upper();aligned=floor_time(start,interval_seconds)
        trades=store.load_trades(symbol,start=aligned,end=aligned+timedelta(seconds=interval_seconds))
        if not trades:raise HTTPException(status_code=404,detail="Nenhum negócio no candle selecionado")
        return candle_detail_payload(trades,interval_seconds,store.tick_size(symbol),seed=seed)

    @app.get("/api/similar-candles")
    def similar_candles(symbol:str,session_date:date,start:datetime,interval_seconds:int=Query(60,ge=1,le=3600),limit:int=Query(8,ge=1,le=50)):
        symbol=symbol.strip().upper();aligned=floor_time(start,interval_seconds);trades=store.load_trades(symbol,session_date=session_date)
        if not trades:raise HTTPException(status_code=404,detail="Nenhum negócio no pregão selecionado")
        return similar_candles_payload(trades,target_start=aligned,interval_seconds=interval_seconds,tick_size=store.tick_size(symbol),limit=limit)

    return app

app=create_app()
