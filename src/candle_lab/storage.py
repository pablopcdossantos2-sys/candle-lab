from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from .models import AggressorSide, Trade
from .quality import QUALITY_MODEL_VERSION, SessionQuality
from .reconciliation import ReferenceCandle
from .research import RESEARCH_INDEX_VERSION, ResearchCandle


class MarketStore:
    def __init__(self, db_path: str | Path="data/candle_lab.duckdb") -> None:
        self.db_path=Path(db_path)
        self.db_path.parent.mkdir(parents=True,exist_ok=True)
        self.init_schema()

    def connect(self):
        import duckdb
        return duckdb.connect(str(self.db_path))

    def init_schema(self)->None:
        with self.connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS instruments(
                symbol VARCHAR PRIMARY KEY, tick_size DOUBLE NOT NULL, updated_at TIMESTAMP DEFAULT current_timestamp)""")
            con.execute("""CREATE TABLE IF NOT EXISTS trades(
                event_key VARCHAR PRIMARY KEY, symbol VARCHAR, ts TIMESTAMPTZ, session_date DATE,
                price_ticks BIGINT, quantity BIGINT, trade_id VARCHAR, aggressor VARCHAR, source VARCHAR,
                buyer_id VARCHAR, seller_id VARCHAR, sequence_no BIGINT, flags VARCHAR)""")
            trade_columns={row[1] for row in con.execute("PRAGMA table_info('trades')").fetchall()}
            if "source_file_hash" not in trade_columns:
                con.execute("ALTER TABLE trades ADD COLUMN source_file_hash VARCHAR")
            if "source_row" not in trade_columns:
                con.execute("ALTER TABLE trades ADD COLUMN source_row BIGINT")
            con.execute("""CREATE TABLE IF NOT EXISTS reference_candles(
                reference_key VARCHAR PRIMARY KEY, symbol VARCHAR, start TIMESTAMPTZ, session_date DATE,
                interval_seconds INTEGER, open_ticks BIGINT, high_ticks BIGINT, low_ticks BIGINT, close_ticks BIGINT,
                volume BIGINT, trades BIGINT, source VARCHAR, imported_at TIMESTAMP DEFAULT current_timestamp)""")
            con.execute("""CREATE TABLE IF NOT EXISTS import_batches(
                batch_id VARCHAR PRIMARY KEY, data_kind VARCHAR, source VARCHAR, file_name VARCHAR, symbol VARCHAR,
                first_ts VARCHAR, last_ts VARCHAR, rows_received BIGINT, rows_inserted BIGINT, duplicates BIGINT,
                diagnostics_json VARCHAR, created_at TIMESTAMP DEFAULT current_timestamp)""")
            con.execute("""CREATE TABLE IF NOT EXISTS session_quality(
                quality_key VARCHAR PRIMARY KEY, symbol VARCHAR, session_date DATE, model_version VARCHAR,
                payload_json VARCHAR, updated_at TIMESTAMP DEFAULT current_timestamp)""")
            con.execute("""CREATE TABLE IF NOT EXISTS research_index(
                feature_key VARCHAR PRIMARY KEY, symbol VARCHAR, start TIMESTAMPTZ, session_date DATE,
                interval_seconds INTEGER, index_version VARCHAR, payload_json VARCHAR,
                updated_at TIMESTAMP DEFAULT current_timestamp)""")
            con.execute("""CREATE TABLE IF NOT EXISTS bulk_imports(
                file_hash VARCHAR PRIMARY KEY, file_name VARCHAR, file_path VARCHAR, file_size BIGINT,
                source VARCHAR, symbol VARCHAR, tick_size DOUBLE, source_order VARCHAR, status VARCHAR,
                processed_rows BIGINT, inserted_rows BIGINT, byte_offset BIGINT,
                first_ts VARCHAR, last_ts VARCHAR, elapsed_seconds DOUBLE,
                diagnostics_json VARCHAR, started_at TIMESTAMP DEFAULT current_timestamp,
                updated_at TIMESTAMP DEFAULT current_timestamp, completed_at TIMESTAMP)""")

    @staticmethod
    def _event_key(trade:Trade,sequence_no:int|None=None)->str:
        raw="|".join([trade.symbol,trade.ts.isoformat(),str(trade.price_ticks),str(trade.quantity),
            trade.trade_id or "",trade.source or "",str(sequence_no if sequence_no is not None else trade.sequence_no or "")])
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _reference_key(ref:ReferenceCandle)->str:
        raw=f"{ref.symbol}|{ref.start.isoformat()}|{ref.interval_seconds}|{ref.source}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def reset_builtin_sample(self,symbol:str="WINLAB06")->None:
        """Remove somente a demonstração interna; nunca apaga dados reais do usuário."""
        with self.connect() as con:
            con.execute("DELETE FROM trades WHERE source LIKE 'synthetic_sample_%' OR symbol='WINLAB06'")
            con.execute("DELETE FROM reference_candles WHERE source LIKE 'synthetic_truth_%' OR symbol='WINLAB06'")
            con.execute("DELETE FROM research_index WHERE symbol='WINLAB06'")
            con.execute("DELETE FROM session_quality WHERE symbol='WINLAB06'")
            con.execute("DELETE FROM instruments WHERE symbol='WINLAB06'")

    def upsert_instrument(self,symbol:str,tick_size:float)->None:
        with self.connect() as con:
            con.execute("""INSERT INTO instruments(symbol,tick_size) VALUES (?,?)
                ON CONFLICT(symbol) DO UPDATE SET tick_size=excluded.tick_size,updated_at=now()""",[symbol,tick_size])

    def add_trades(self,trades:Iterable[Trade],*,tick_size:float)->dict[str,int]:
        trades=list(trades)
        if not trades:return {"received":0,"inserted":0,"duplicates":0}
        symbols={t.symbol for t in trades}
        if len(symbols)!=1:raise ValueError("Importe um contrato por vez")
        self.upsert_instrument(trades[0].symbol,tick_size)
        inserted=0
        with self.connect() as con:
            for t in trades:
                key=self._event_key(t)
                exists=con.execute("SELECT 1 FROM trades WHERE event_key=?",[key]).fetchone()
                if exists:continue
                con.execute("""INSERT INTO trades(
                    event_key,symbol,ts,session_date,price_ticks,quantity,trade_id,aggressor,source,
                    buyer_id,seller_id,sequence_no,flags
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",[
                    key,t.symbol,t.ts,t.ts.date(),t.price_ticks,t.quantity,t.trade_id,t.aggressor.value,t.source,
                    t.buyer_id,t.seller_id,t.sequence_no,t.flags])
                inserted+=1
        return {"received":len(trades),"inserted":inserted,"duplicates":len(trades)-inserted}

    def add_selected_slice_trades(
        self,trades:Iterable[Trade],*,tick_size:float,source_fingerprint:str,source_rows:Iterable[int]
    )->dict[str,int]:
        trades=list(trades);rows=list(source_rows)
        if len(trades)!=len(rows):
            raise ValueError("Quantidade de trades e posições da fonte não coincide")
        if not trades:return {"received":0,"inserted":0,"duplicates":0}
        symbols={t.symbol for t in trades}
        if len(symbols)!=1:raise ValueError("Importe um contrato por vez")
        self.upsert_instrument(trades[0].symbol,tick_size)
        inserted=0
        with self.connect() as con:
            for t,source_row in zip(trades,rows):
                key=hashlib.sha256(f"{source_fingerprint}:{source_row}".encode()).hexdigest()
                exists=con.execute("SELECT 1 FROM trades WHERE event_key=?",[key]).fetchone()
                if exists:continue
                con.execute("""INSERT INTO trades(
                    event_key,symbol,ts,session_date,price_ticks,quantity,trade_id,aggressor,source,
                    buyer_id,seller_id,sequence_no,flags,source_file_hash,source_row
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",[
                    key,t.symbol,t.ts,t.ts.date(),t.price_ticks,t.quantity,t.trade_id,t.aggressor.value,t.source,
                    t.buyer_id,t.seller_id,t.sequence_no,t.flags,source_fingerprint,int(source_row)])
                inserted+=1
        return {"received":len(trades),"inserted":inserted,"duplicates":len(trades)-inserted}

    def add_reference_candles(self,references:Iterable[ReferenceCandle],*,tick_size:float)->dict[str,int]:
        refs=list(references)
        if not refs:return {"received":0,"inserted":0,"duplicates":0}
        self.upsert_instrument(refs[0].symbol,tick_size)
        inserted=0
        with self.connect() as con:
            for r in refs:
                key=self._reference_key(r)
                if con.execute("SELECT 1 FROM reference_candles WHERE reference_key=?",[key]).fetchone():continue
                con.execute("""INSERT INTO reference_candles(reference_key,symbol,start,session_date,interval_seconds,
                    open_ticks,high_ticks,low_ticks,close_ticks,volume,trades,source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    [key,r.symbol,r.start,r.start.date(),r.interval_seconds,r.open_ticks,r.high_ticks,r.low_ticks,r.close_ticks,r.volume,r.trades,r.source])
                inserted+=1
        return {"received":len(refs),"inserted":inserted,"duplicates":len(refs)-inserted}

    def record_import_batch(self,*,data_kind:str,source:str,file_name:str,symbol:str,first_ts:str,last_ts:str,
        rows_received:int,rows_inserted:int,duplicates:int,diagnostics:dict[str,object]|None=None)->str:
        raw=f"{data_kind}|{source}|{file_name}|{symbol}|{first_ts}|{last_ts}|{datetime.now().isoformat()}"
        batch_id=hashlib.sha256(raw.encode()).hexdigest()[:20]
        with self.connect() as con:
            con.execute("INSERT INTO import_batches VALUES (?,?,?,?,?,?,?,?,?,?,?,current_timestamp)",
                [batch_id,data_kind,source,file_name,symbol,first_ts,last_ts,rows_received,rows_inserted,duplicates,
                 json.dumps(diagnostics or {},ensure_ascii=False,default=str)])
        return batch_id

    def list_import_batches(self,limit:int=50)->list[dict[str,object]]:
        with self.connect() as con:
            rows=con.execute("""SELECT batch_id,data_kind,source,file_name,symbol,first_ts,last_ts,rows_received,
                rows_inserted,duplicates,diagnostics_json,created_at FROM import_batches ORDER BY created_at DESC LIMIT ?""",[limit]).fetchall()
        keys=["batch_id","data_kind","source","file_name","symbol","first_ts","last_ts","rows_received","rows_inserted","duplicates","diagnostics","created_at"]
        out=[]
        for row in rows:
            item=dict(zip(keys,row)); item["diagnostics"]=json.loads(item["diagnostics"] or "{}"); out.append(item)
        return out

    def list_symbols(self)->list[dict[str,object]]:
        with self.connect() as con:
            rows=con.execute("""SELECT i.symbol,i.tick_size,count(t.event_key) trades,min(t.ts) first_ts,max(t.ts) last_ts
                FROM instruments i LEFT JOIN trades t ON i.symbol=t.symbol GROUP BY i.symbol,i.tick_size ORDER BY i.symbol""").fetchall()
        return [{"symbol":r[0],"tick_size":r[1],"trades":r[2],"first_ts":r[3],"last_ts":r[4]} for r in rows]

    def list_sessions(self,symbol:str)->list[dict[str,object]]:
        with self.connect() as con:
            rows=con.execute("""SELECT session_date,count(*),min(ts),max(ts),sum(quantity)
                FROM trades WHERE symbol=? GROUP BY session_date ORDER BY session_date""",[symbol]).fetchall()
        return [{"session_date":str(r[0]),"trades":r[1],"first_ts":r[2],"last_ts":r[3],"volume":r[4]} for r in rows]

    def list_reference_sessions(self,symbol:str)->list[dict[str,object]]:
        with self.connect() as con:
            rows=con.execute("""SELECT session_date,interval_seconds,count(*),min(start),max(start),min(source)
                FROM reference_candles WHERE symbol=?
                GROUP BY session_date,interval_seconds
                ORDER BY session_date,interval_seconds""",[symbol]).fetchall()
        return [{"session_date":str(r[0]),"interval_seconds":int(r[1]),"candles":int(r[2]),
                 "first_start":r[3],"last_start":r[4],"source":r[5]} for r in rows]

    def reference_overview(self)->list[dict[str,object]]:
        with self.connect() as con:
            rows=con.execute("""SELECT r.symbol,i.tick_size,r.session_date,r.interval_seconds,count(*),min(r.start),max(r.start)
                FROM reference_candles r
                JOIN instruments i ON i.symbol=r.symbol
                GROUP BY r.symbol,i.tick_size,r.session_date,r.interval_seconds
                ORDER BY r.symbol,r.session_date,r.interval_seconds""").fetchall()
        return [{"symbol":r[0],"tick_size":float(r[1]),"session_date":str(r[2]),"interval_seconds":int(r[3]),
                 "candles":int(r[4]),"first_start":r[5],"last_start":r[6]} for r in rows]

    def library_overview(self)->list[dict[str,object]]:
        result=[]
        for item in self.list_symbols():
            sessions=self.list_sessions(str(item["symbol"]))
            for session in sessions:
                quality=self.get_session_quality(str(item["symbol"]),str(session["session_date"]))
                result.append({**session,"symbol":item["symbol"],"tick_size":item["tick_size"],"quality":quality})
        return result

    def get_session_quality(self,symbol:str,session_date:date|str)->dict[str,object]|None:
        with self.connect() as con:
            row=con.execute("SELECT model_version,payload_json FROM session_quality WHERE symbol=? AND session_date=?",
                [symbol,str(session_date)]).fetchone()
        if not row:return None
        payload=json.loads(row[1]); payload["model_version"]=row[0]; return payload

    def replace_session_quality(self,symbol:str,qualities)->int:
        qualities=list(qualities)
        with self.connect() as con:
            con.execute("DELETE FROM session_quality WHERE symbol=?",[symbol])
            for q in qualities:
                key=f"{symbol}|{q.session_date.isoformat()}"
                con.execute("""INSERT INTO session_quality(
                    quality_key,symbol,session_date,model_version,payload_json,updated_at
                ) VALUES (?,?,?,?,?,current_timestamp)""",
                    [key,symbol,q.session_date,QUALITY_MODEL_VERSION,
                     json.dumps(q.to_record(),ensure_ascii=False,default=str)])
        return len(qualities)

    def tick_size(self,symbol:str)->float:
        with self.connect() as con:
            row=con.execute("SELECT tick_size FROM instruments WHERE symbol=?",[symbol]).fetchone()
        if not row:raise KeyError(f"Ativo {symbol} não cadastrado")
        return float(row[0])

    def load_trades(self,symbol:str,session_date:date|str|None=None,start:datetime|None=None,end:datetime|None=None)->list[Trade]:
        sql="""SELECT symbol,ts,price_ticks,quantity,trade_id,aggressor,source,buyer_id,seller_id,sequence_no,flags
               FROM trades WHERE symbol=?"""; params=[symbol]
        if session_date is not None:sql+=" AND session_date=?";params.append(str(session_date))
        if start is not None:sql+=" AND ts>=?";params.append(start)
        if end is not None:sql+=" AND ts<?";params.append(end)
        sql+=" ORDER BY ts,sequence_no,trade_id"
        with self.connect() as con:rows=con.execute(sql,params).fetchall()
        result=[]
        for r in rows:
            try:agg=AggressorSide(r[5])
            except Exception:agg=AggressorSide.NONE
            result.append(Trade(symbol=r[0],ts=r[1],price_ticks=int(r[2]),quantity=int(r[3]),trade_id=r[4],aggressor=agg,
                source=r[6],buyer_id=r[7],seller_id=r[8],sequence_no=int(r[9]) if r[9] is not None else None,flags=r[10]))
        return result

    def load_reference_candles(self,symbol:str,interval_seconds:int|None=None,session_date:date|str|None=None)->list[ReferenceCandle]:
        sql="""SELECT symbol,start,interval_seconds,open_ticks,high_ticks,low_ticks,close_ticks,volume,trades,source
               FROM reference_candles WHERE symbol=?""";params=[symbol]
        if interval_seconds is not None:sql+=" AND interval_seconds=?";params.append(interval_seconds)
        if session_date is not None:sql+=" AND session_date=?";params.append(str(session_date))
        sql+=" ORDER BY start,imported_at"
        with self.connect() as con:rows=con.execute(sql,params).fetchall()
        return [ReferenceCandle(symbol=r[0],start=r[1],interval_seconds=int(r[2]),open_ticks=int(r[3]),high_ticks=int(r[4]),
            low_ticks=int(r[5]),close_ticks=int(r[6]),volume=int(r[7]) if r[7] is not None else None,
            trades=int(r[8]) if r[8] is not None else None,source=r[9]) for r in rows]

    @staticmethod
    def _feature_key(feature:ResearchCandle)->str:
        return f"{feature.candle.symbol}|{feature.candle.start.isoformat()}|{feature.candle.interval_seconds}"

    def research_index_status(self,symbol:str,interval_seconds:int)->dict[str,object]:
        with self.connect() as con:
            row=con.execute("""SELECT count(*),max(index_version) FROM research_index WHERE symbol=? AND interval_seconds=?""",
                [symbol,interval_seconds]).fetchone()
            trade_count=con.execute("SELECT count(*) FROM trades WHERE symbol=?",[symbol]).fetchone()[0]
        count=int(row[0]); version=row[1]
        return {"indexed":count>0,"features":count,"index_version":version,"expected_version":RESEARCH_INDEX_VERSION,
                "stale":count==0 or version!=RESEARCH_INDEX_VERSION,"trade_count":int(trade_count)}

    def replace_research_index(self,symbol:str,interval_seconds:int,features:Iterable[ResearchCandle])->dict[str,int]:
        features=list(features)
        with self.connect() as con:
            con.execute("DELETE FROM research_index WHERE symbol=? AND interval_seconds=?",[symbol,interval_seconds])
            for f in features:
                con.execute("INSERT INTO research_index VALUES (?,?,?,?,?,?,?,current_timestamp)",[
                    self._feature_key(f),symbol,f.candle.start,f.candle.start.date(),interval_seconds,RESEARCH_INDEX_VERSION,
                    json.dumps(f.to_record(),ensure_ascii=False,default=str)])
        return {"inserted":len(features)}

    def load_research_index(self,symbol:str,interval_seconds:int)->list[ResearchCandle]:
        with self.connect() as con:
            rows=con.execute("""SELECT payload_json FROM research_index WHERE symbol=? AND interval_seconds=? ORDER BY start""",
                [symbol,interval_seconds]).fetchall()
        return [ResearchCandle.from_record(json.loads(row[0])) for row in rows]

    def stats(self)->dict[str,int]:
        with self.connect() as con:
            t=int(con.execute("SELECT count(*) FROM trades").fetchone()[0])
            r=int(con.execute("SELECT count(*) FROM reference_candles").fetchone()[0])
            s=int(con.execute("SELECT count(DISTINCT symbol) FROM trades").fetchone()[0])
        return {"trades":t,"reference_candles":r,"symbols":s}

    def export_parquet(self,parquet_path:str|Path="data/parquet/trades.parquet")->Path:
        path=Path(parquet_path);path.parent.mkdir(parents=True,exist_ok=True)
        escaped=str(path.resolve()).replace("'","''")
        with self.connect() as con:
            con.execute(f"COPY (SELECT * FROM trades ORDER BY symbol,ts,sequence_no) TO '{escaped}' (FORMAT PARQUET)")
        return path
