from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .models import AggressorSide, Trade

TZ=ZoneInfo("America/Sao_Paulo")


def generate_builtin_sample(symbol:str="WINLAB06")->list[Trade]:
    """Gera 2.880 negócios sintéticos: 6 pregões × 12 candles × 40 negócios."""
    sessions=[
        (datetime(2026,10,1,10,0,tzinfo=TZ), 2.0, 0.7),
        (datetime(2026,10,2,10,0,tzinfo=TZ),-2.0, 0.8),
        (datetime(2026,10,3,10,0,tzinfo=TZ), 0.0, 1.3),
        (datetime(2026,10,4,10,0,tzinfo=TZ), 0.8, 2.0),
        (datetime(2026,10,5,10,0,tzinfo=TZ),-0.7, 2.8),
        (datetime(2026,10,6,10,0,tzinfo=TZ), 0.1, 0.35),
    ]
    rng=random.Random(9062026)
    trades=[];global_id=1
    base_price=29000
    for session_i,(start,drift,vol) in enumerate(sessions):
        price=base_price+session_i*22
        for minute in range(12):
            candle_start=start+timedelta(minutes=minute)
            # diferentes formas intrabar: impulso, V, varredura e oscilação
            mode=(minute+session_i)%6
            anchor=price
            for i in range(40):
                x=i/39
                if mode==0: shape=drift*x+0.35*math.sin(x*math.pi)
                elif mode==1: shape=-2.5*vol*math.sin(x*math.pi)+drift*x
                elif mode==2: shape=2.5*vol*math.sin(x*math.pi)+drift*x
                elif mode==3: shape=1.4*vol*math.sin(x*math.pi*4)+drift*x
                elif mode==4: shape=(-2.2*vol if x<.28 else 2.5*vol*(x-.28))+drift*x
                else: shape=(2.2*vol if x<.28 else -2.3*vol*(x-.28))+drift*x
                jitter=rng.choice([-1,0,0,0,1])*.25*vol
                ticks=int(round(anchor+shape+jitter))
                if i>0:
                    previous=trades[-1].price_ticks
                    aggressor=AggressorSide.BUY if ticks>previous else AggressorSide.SELL if ticks<previous else AggressorSide.NONE
                else: aggressor=AggressorSide.NONE
                ts=candle_start+timedelta(seconds=(58.8*i/39))
                trades.append(Trade(symbol=symbol,ts=ts,price_ticks=ticks,quantity=1+(i+minute)%5,
                    trade_id=str(global_id),aggressor=aggressor,source="synthetic_sample_v09",
                    buyer_id=f"B{(i%5)+1}",seller_id=f"S{(i%7)+1}",sequence_no=global_id))
                global_id+=1
            price=trades[-1].price_ticks
    return trades
