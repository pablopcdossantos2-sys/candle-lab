import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

from candle_lab.aggression import aggression_analysis
from candle_lab.aggression_waves import aggression_wave_analysis
from candle_lab.interpretation import interpret_candle
from candle_lab.historical_validation import validate_historical_hypotheses
from candle_lab.candles import build_candles
from candle_lab.counterfactual import generate_ohlc_path
from candle_lab.metrics import candle_dna
from candle_lab.models import AggressorSide, Trade
from candle_lab.importers import import_csv_with_report, _decimal_number, _profit_decimal_number
from candle_lab.reconciliation import import_reference_candles, reconcile_observed_window, reconcile_available_candles
from candle_lab.sample import generate_builtin_sample
from candle_lab.quality import assess_library_quality
from candle_lab.storage import MarketStore
from candle_lab.services import candle_detail_payload
from candle_lab.trajectory import classify_rule_family, deterministic_kmeans
from candle_lab.transitions import analyze_stability_and_transitions
from candle_lab.bulk import bulk_import_profit_file, aggregate_candles_sql, reconcile_store_references, export_session_parquet
from candle_lab.reconciliation import ReferenceCandle
from candle_lab.slice import slice_profit_trades
from candle_lab.time_index import build_time_index, ensure_time_index, locate_candles, locate_interval

UTC = timezone.utc


def trades_from_prices(start, prices, symbol="WINTEST"):
    step = 58 / max(len(prices) - 1, 1)
    return [
        Trade(
            symbol=symbol,
            ts=start + timedelta(seconds=i * step),
            price_ticks=int(price),
            quantity=1,
            trade_id=str(i + 1),
            sequence_no=i + 1,
        )
        for i, price in enumerate(prices)
    ]


class AggressionAnalysisTests(unittest.TestCase):
    def test_identifies_top_agents_and_price_level_intensity(self):
        tz=ZoneInfo("America/Sao_Paulo")
        start=datetime(2026,10,7,14,40,tzinfo=tz)
        trades=[
            Trade("WINAGG",start+timedelta(seconds=1),100,80,aggressor=AggressorSide.BUY,buyer_id="A",seller_id="P1",sequence_no=1),
            Trade("WINAGG",start+timedelta(seconds=2),100,40,aggressor=AggressorSide.BUY,buyer_id="A",seller_id="P2",sequence_no=2),
            Trade("WINAGG",start+timedelta(seconds=3),100,20,aggressor=AggressorSide.SELL,buyer_id="P3",seller_id="S1",sequence_no=3),
            Trade("WINAGG",start+timedelta(seconds=10),101,30,aggressor=AggressorSide.BUY,buyer_id="B",seller_id="P4",sequence_no=4),
            Trade("WINAGG",start+timedelta(seconds=20),102,12,aggressor=AggressorSide.SELL,buyer_id="P5",seller_id="S2",sequence_no=5),
            Trade("WINAGG",start+timedelta(seconds=30),103,5,aggressor=AggressorSide.BUY,buyer_id="C",seller_id="P6",sequence_no=6),
        ]
        report=aggression_analysis(trades,5.0)
        self.assertEqual(report["summary"]["buy_aggression"],155)
        self.assertEqual(report["summary"]["sell_aggression"],32)
        self.assertEqual(report["summary"]["delta"],123)
        self.assertEqual(report["top_buy_aggressors"][0]["agent"],"A")
        self.assertEqual(report["top_buy_aggressors"][0]["quantity"],120)
        level100=next(x for x in report["levels"] if x["price_ticks"]==100)
        self.assertEqual(level100["buy_aggression"],120)
        self.assertEqual(level100["sell_aggression"],20)
        self.assertEqual(level100["top_buy_aggressors"][0]["agent"],"A")
        self.assertIn(level100["intensity"],{"ALTA","EXTREMA"})
        self.assertGreater(level100["dominance"],0.70)

    def test_sell_aggressor_uses_seller_identity_and_rlp_stays_separate(self):
        tz=ZoneInfo("America/Sao_Paulo")
        start=datetime(2026,10,7,14,40,tzinfo=tz)
        trades=[
            Trade("WINAGG",start,200,50,aggressor=AggressorSide.SELL,buyer_id="PASSIVO",seller_id="VENDEDOR_X",sequence_no=1),
            Trade("WINAGG",start+timedelta(seconds=1),200,25,aggressor=AggressorSide.NONE,buyer_id="RLP_B",seller_id="RLP_S",flags="raw_aggressor=RLP",sequence_no=2),
            Trade("WINAGG",start+timedelta(seconds=2),201,10,aggressor=AggressorSide.NONE,buyer_id="U1",seller_id="U2",sequence_no=3),
        ]
        report=aggression_analysis(trades,5.0)
        self.assertEqual(report["top_sell_aggressors"][0]["agent"],"VENDEDOR_X")
        self.assertEqual(report["summary"]["sell_aggression"],50)
        self.assertEqual(report["summary"]["rlp_volume"],25)
        self.assertEqual(report["summary"]["unknown_volume"],10)
        self.assertEqual(report["summary"]["directed_aggression"],50)
        self.assertAlmostEqual(report["summary"]["aggressor_coverage"],50/85)

    def test_candle_aggression_composition_and_price_flow_divergence(self):
        tz=ZoneInfo("America/Sao_Paulo")
        start=datetime(2026,10,8,10,0,tzinfo=tz)
        trades=[
            Trade("WINDIV",start+timedelta(seconds=1),102,60,aggressor=AggressorSide.BUY,buyer_id="BUYER_A",sequence_no=1),
            Trade("WINDIV",start+timedelta(seconds=2),101,30,aggressor=AggressorSide.BUY,buyer_id="BUYER_B",sequence_no=2),
            Trade("WINDIV",start+timedelta(seconds=3),100,20,aggressor=AggressorSide.SELL,seller_id="SELLER_A",sequence_no=3),
            Trade("WINDIV",start+timedelta(seconds=4),99,10,aggressor=AggressorSide.NONE,flags="raw_aggressor=RLP",sequence_no=4),
        ]
        report=aggression_analysis(trades,5.0)
        sm=report["summary"]
        self.assertEqual(sm["total_volume"],120)
        self.assertAlmostEqual(sm["buy_share_total_volume"],90/120)
        self.assertAlmostEqual(sm["sell_share_total_volume"],20/120)
        self.assertAlmostEqual(sm["rlp_share_total_volume"],10/120)
        self.assertAlmostEqual(sm["buy_share_directed"],90/110)
        self.assertEqual(sm["price_direction"],"BAIXA")
        self.assertEqual(sm["direction"],"COMPRA")
        self.assertEqual(sm["price_flow_relation"],"DIVERGENTE")
        self.assertIn(sm["study_priority"],{"MODERADA","ALTA"})

    def test_possible_absorption_is_only_heuristic_label(self):
        tz=ZoneInfo("America/Sao_Paulo")
        start=datetime(2026,10,7,14,40,tzinfo=tz)
        trades=[
            Trade("WINAGG",start+timedelta(seconds=1),100,100,aggressor=AggressorSide.BUY,buyer_id="A",sequence_no=1),
            Trade("WINAGG",start+timedelta(seconds=2),100,100,aggressor=AggressorSide.BUY,buyer_id="A",sequence_no=2),
            Trade("WINAGG",start+timedelta(seconds=3),101,5,aggressor=AggressorSide.SELL,seller_id="S",sequence_no=3),
            Trade("WINAGG",start+timedelta(seconds=4),100,10,aggressor=AggressorSide.BUY,buyer_id="A",sequence_no=4),
            Trade("WINAGG",start+timedelta(seconds=5),99,5,aggressor=AggressorSide.SELL,seller_id="S2",sequence_no=5),
        ]
        report=aggression_analysis(trades,5.0)
        level100=next(x for x in report["levels"] if x["price_ticks"]==100)
        self.assertEqual(level100["response"],"POSSIVEL_ABSORCAO")
        self.assertIn("não prova causal",report["limitations"])


    def test_no_future_observation_does_not_claim_absorption(self):
        tz=ZoneInfo("America/Sao_Paulo")
        start=datetime(2026,10,7,14,40,tzinfo=tz)
        trades=[
            Trade("WINAGG",start,100,5,aggressor=AggressorSide.SELL,seller_id="S",sequence_no=1),
            Trade("WINAGG",start+timedelta(seconds=1),101,100,aggressor=AggressorSide.BUY,buyer_id="A",sequence_no=2),
            Trade("WINAGG",start+timedelta(seconds=2),101,100,aggressor=AggressorSide.BUY,buyer_id="A",sequence_no=3),
        ]
        report=aggression_analysis(trades,5.0)
        level101=next(x for x in report["levels"] if x["price_ticks"]==101)
        self.assertEqual(level101["response"],"SEM_JANELA_POS_AGRESSAO")
        self.assertEqual(level101["future_observations"],0)

class AggressionWaveTests(unittest.TestCase):
    def _trade(self,start,i,price,side,qty=10,agent="A"):
        return Trade(
            "WINWAVE",
            start+timedelta(seconds=i),
            price,
            qty,
            aggressor=side,
            buyer_id=agent if side==AggressorSide.BUY else "PASSIVO",
            seller_id=agent if side==AggressorSide.SELL else "PASSIVO",
            sequence_no=i+1,
        )

    def test_detects_buy_aggression_exhaustion_causally(self):
        tz=ZoneInfo("America/Sao_Paulo")
        start=datetime(2026,10,8,10,0,tzinfo=tz)
        trades=[]
        for i in range(10):
            trades.append(self._trade(start,i,100+i//3,AggressorSide.BUY,10,"BUYER_A"))
        for i in range(10,18):
            trades.append(self._trade(start,i,103,AggressorSide.NONE,10,"NONE"))
        report=aggression_wave_analysis(
            trades,5.0,window_trades=5,activation_confirmations=2,release_confirmations=2,
            post_event_horizon_trades=5,
        )
        self.assertTrue(report["causal_detection"])
        self.assertGreaterEqual(len(report["termination_events"]),1)
        event=report["termination_events"][0]
        self.assertEqual(event["side"],"BUY")
        self.assertEqual(event["termination_type"],"EXAUSTAO")
        self.assertGreater(event["pressure_decay"],0.5)
        self.assertEqual(event["top_aggressors"][0]["agent"],"BUYER_A")

    def test_detects_control_handoff_to_opposite_side(self):
        tz=ZoneInfo("America/Sao_Paulo")
        start=datetime(2026,10,8,10,0,tzinfo=tz)
        trades=[]
        for i in range(10):
            trades.append(self._trade(start,i,100+i//4,AggressorSide.BUY,10,"BUYER_A"))
        for i in range(10,20):
            # Tomada abrupta: cada negócio vendedor supera com folga o volume
            # comprador remanescente na janela, evitando uma fase prévia de neutralização.
            trades.append(self._trade(start,i,102-(i-10)//3,AggressorSide.SELL,100,"SELLER_B"))
        report=aggression_wave_analysis(
            trades,5.0,window_trades=5,activation_confirmations=2,release_confirmations=2,
            opposite_takeover=0.40,post_event_horizon_trades=5,
        )
        event=report["termination_events"][0]
        self.assertEqual(event["termination_type"],"TROCA_CONTROLE")
        self.assertLess(event["end_signed_dominance"],0)

    def test_detection_index_does_not_change_when_future_is_appended(self):
        tz=ZoneInfo("America/Sao_Paulo")
        start=datetime(2026,10,8,10,0,tzinfo=tz)
        prefix=[]
        for i in range(10):
            prefix.append(self._trade(start,i,100+i//3,AggressorSide.BUY,10,"BUYER_A"))
        for i in range(10,18):
            prefix.append(self._trade(start,i,103,AggressorSide.NONE,10,"NONE"))
        future=[
            self._trade(start,18+i,102-i//2,AggressorSide.SELL,10,"SELLER_B")
            for i in range(8)
        ]
        kwargs=dict(window_trades=5,activation_confirmations=2,release_confirmations=2,post_event_horizon_trades=5)
        a=aggression_wave_analysis(prefix,5.0,**kwargs)
        b=aggression_wave_analysis(prefix+future,5.0,**kwargs)
        self.assertEqual(a["termination_events"][0]["end_index"],b["termination_events"][0]["end_index"])
        self.assertEqual(a["termination_events"][0]["termination_type"],b["termination_events"][0]["termination_type"])

    def test_post_event_outcome_is_explicitly_marked_as_future_data(self):
        tz=ZoneInfo("America/Sao_Paulo")
        start=datetime(2026,10,8,10,0,tzinfo=tz)
        trades=[]
        for i in range(10):
            trades.append(self._trade(start,i,100+i//3,AggressorSide.BUY,10,"BUYER_A"))
        for i in range(10,18):
            trades.append(self._trade(start,i,103,AggressorSide.NONE,10,"NONE"))
        for i in range(18,24):
            trades.append(self._trade(start,i,102-(i-18),AggressorSide.SELL,10,"SELLER_B"))
        report=aggression_wave_analysis(
            trades,5.0,window_trades=5,activation_confirmations=2,release_confirmations=2,
            post_event_horizon_trades=6,reversal_ticks=2,
        )
        post=report["termination_events"][0]["post_event"]
        self.assertTrue(post["uses_future_data"])
        self.assertEqual(post["outcome"],"REVERSAO_COMPATIVEL")


class CandleInterpretationTests(unittest.TestCase):
    def _report(self,trades,tick_size=5.0):
        ordered=sorted(trades,key=lambda t:(t.ts,t.sequence_no or 0))
        candle=build_candles(ordered,60)[0]
        dna=candle_dna(ordered,interval_seconds=60)
        aggression=aggression_analysis(ordered,tick_size)
        waves=aggression_wave_analysis(ordered,tick_size,window_trades=5,activation_confirmations=2,release_confirmations=2)
        return interpret_candle(
            ordered,candle=candle,dna=dna,aggression=aggression,waves=waves,tick_size=tick_size
        )

    def test_directional_bull_candle_produces_aligned_aggression_hypothesis(self):
        tz=ZoneInfo("America/Sao_Paulo")
        start=datetime(2026,10,8,11,0,tzinfo=tz)
        trades=[
            Trade("WININT",start+timedelta(seconds=i),100+i//2,10,
                  aggressor=AggressorSide.BUY,buyer_id="BUYER_A",seller_id="PASSIVO",sequence_no=i+1)
            for i in range(12)
        ]
        report=self._report(trades)
        self.assertEqual(report["geometry"]["direction"],"ALTA")
        self.assertGreater(len(report["observed_facts"]),2)
        codes={h["code"] for h in report["hypotheses"]}
        self.assertIn("AGRESSAO_ALINHADA_ALTA",codes)
        self.assertIn("hipóteses explicativas",report["closing_synthesis"].lower())
        self.assertEqual(len(report["phase_analysis"]),3)

    def test_price_up_with_negative_delta_generates_absorption_hypothesis_not_fact(self):
        tz=ZoneInfo("America/Sao_Paulo")
        start=datetime(2026,10,8,11,0,tzinfo=tz)
        trades=[]
        prices=[100,100,101,101,102,102,103,103,104,104,105,105]
        for i,p in enumerate(prices):
            side=AggressorSide.SELL if i<9 else AggressorSide.BUY
            trades.append(Trade(
                "WININT",start+timedelta(seconds=i),p,10,aggressor=side,
                buyer_id="B",seller_id="SELLER_X",sequence_no=i+1
            ))
        report=self._report(trades)
        hypothesis=next(h for h in report["hypotheses"] if h["code"]=="ALTA_COM_DELTA_VENDEDOR")
        self.assertIn("hipótese",hypothesis["explanation"].lower())
        self.assertIn("não constituem demonstração causal",report["closing_synthesis"].lower())
        observed_text=" ".join(x["text"] for x in report["observed_facts"]).lower()
        self.assertNotIn("absorção comprovada",observed_text)

    def test_low_aggressor_coverage_reduces_evidence_quality(self):
        tz=ZoneInfo("America/Sao_Paulo")
        start=datetime(2026,10,8,11,0,tzinfo=tz)
        trades=[]
        for i in range(30):
            side=AggressorSide.BUY if i<3 else AggressorSide.NONE
            flags=None if side==AggressorSide.BUY else "raw_aggressor=RLP"
            trades.append(Trade(
                "WININT",start+timedelta(seconds=i),100+i//10,5,aggressor=side,
                buyer_id="A",seller_id="B",flags=flags,sequence_no=i+1
            ))
        report=self._report(trades)
        self.assertEqual(report["evidence_quality"]["label"],"LIMITADA")
        self.assertIn("qualidade da evidência",report["limitations"][0].lower())

    def test_missing_aggressor_data_is_not_reported_as_zero_aggression(self):
        tz=ZoneInfo("America/Sao_Paulo")
        start=datetime(2026,10,8,11,0,tzinfo=tz)
        trades=[
            Trade(
                "WININT",start+timedelta(seconds=i),100+(i%3),5,
                aggressor=AggressorSide.NONE,buyer_id="B",seller_id="S",sequence_no=i+1
            )
            for i in range(12)
        ]
        report=self._report(trades)
        observed={x["code"]:x["text"] for x in report["observed_facts"]}
        self.assertIn("AGRESSAO_TOTAL",observed)
        self.assertIn("dado de agressão indisponível",observed["AGRESSAO_TOTAL"].lower())
        self.assertNotIn("NIVEL_MAIS_AGREDIDO",observed)
        self.assertEqual(report["evidence_quality"]["label"],"INDISPONIVEL")
        self.assertTrue(all(x["direction"]=="SEM_DADOS_AGRESSOR" for x in report["phase_analysis"]))

    def test_interpretation_marks_price_flow_divergence_for_study(self):
        tz=ZoneInfo("America/Sao_Paulo")
        start=datetime(2026,10,8,11,0,tzinfo=tz)
        trades=[
            Trade("WININT",start+timedelta(seconds=0),105,50,aggressor=AggressorSide.BUY,buyer_id="B1",sequence_no=1),
            Trade("WININT",start+timedelta(seconds=10),104,40,aggressor=AggressorSide.BUY,buyer_id="B1",sequence_no=2),
            Trade("WININT",start+timedelta(seconds=20),103,10,aggressor=AggressorSide.SELL,seller_id="S1",sequence_no=3),
            Trade("WININT",start+timedelta(seconds=30),102,10,aggressor=AggressorSide.SELL,seller_id="S1",sequence_no=4),
        ]
        report=self._report(trades)
        facts={x["code"]:x for x in report["observed_facts"]}
        self.assertIn("COMPOSICAO_AGRESSAO",facts)
        self.assertIn("DIVERGENCIA_PRECO_FLUXO",facts)
        self.assertEqual(facts["DIVERGENCIA_PRECO_FLUXO"]["data"]["price_direction"],"BAIXA")
        self.assertEqual(facts["DIVERGENCIA_PRECO_FLUXO"]["data"]["flow_direction"],"COMPRA")

    def test_candle_detail_payload_contains_interpretation(self):
        tz=ZoneInfo("America/Sao_Paulo")
        start=datetime(2026,10,8,11,0,tzinfo=tz)
        trades=[
            Trade("WININT",start+timedelta(seconds=i),100+(i%4),2,
                  aggressor=AggressorSide.BUY if i%3 else AggressorSide.SELL,
                  buyer_id="B1",seller_id="S1",sequence_no=i+1)
            for i in range(30)
        ]
        payload=candle_detail_payload(trades,60,5.0)
        self.assertIn("interpretation",payload)
        self.assertIn("closing_synthesis",payload["interpretation"])
        self.assertTrue(payload["interpretation"]["label"].startswith("RELATORIO_INTERPRETATIVO"))


class HistoricalValidationTests(unittest.TestCase):
    def _rising_library(self, *, source="profit_selected_slice", candles=8):
        tz=ZoneInfo("America/Sao_Paulo")
        start=datetime(2026,10,8,9,0,tzinfo=tz)
        trades=[]
        seq=1
        for c in range(candles):
            base=100+c*2
            candle_start=start+timedelta(minutes=c)
            for i in range(30):
                price=base+(i//10)
                trades.append(Trade(
                    "WINHIST",
                    candle_start+timedelta(seconds=i*2),
                    price,
                    2,
                    aggressor=AggressorSide.BUY,
                    source=source,
                    buyer_id="BUYER_A",
                    seller_id="PASSIVE",
                    sequence_no=seq,
                ))
                seq+=1
        built=build_candles(trades,60)
        refs=[
            ReferenceCandle(
                symbol=c.symbol,start=c.start,interval_seconds=60,
                open_ticks=c.open_ticks,high_ticks=c.high_ticks,low_ticks=c.low_ticks,
                close_ticks=c.close_ticks,volume=c.volume,trades=c.trades,source="test_reference"
            )
            for c in built
        ]
        return trades,refs

    def test_historical_validation_measures_external_outcome_against_baseline(self):
        trades,refs=self._rising_library(candles=8)
        report=validate_historical_hypotheses(
            trades,interval_seconds=60,tick_size=5.0,reference_candles=refs,horizons=(1,)
        )
        self.assertEqual(report["reference_mode"],"REFERENCE_EXACT_REQUIRED")
        self.assertEqual(report["input"]["eligible_candles"],8)
        row=next(
            x for x in report["directional_results"]
            if x["hypothesis_code"]=="AGRESSAO_ALINHADA_ALTA" and x["horizon_candles"]==1
        )
        self.assertEqual(row["with_contiguous_outcome"],7)
        self.assertEqual(row["directional_hit_rate"],1.0)
        self.assertEqual(row["baseline_rate"],1.0)
        self.assertEqual(row["sample_status"],"AMOSTRA_INSUFICIENTE")
        self.assertIn("Não valida como verdadeira",report["scope"])

    def test_reference_mismatch_is_excluded(self):
        trades,refs=self._rising_library(candles=5)
        bad=list(refs)
        first=bad[0]
        bad[0]=ReferenceCandle(
            symbol=first.symbol,start=first.start,interval_seconds=first.interval_seconds,
            open_ticks=first.open_ticks,high_ticks=first.high_ticks+1,low_ticks=first.low_ticks,
            close_ticks=first.close_ticks,volume=first.volume,trades=first.trades,source=first.source
        )
        report=validate_historical_hypotheses(
            trades,interval_seconds=60,tick_size=5.0,reference_candles=bad,horizons=(1,)
        )
        self.assertEqual(report["input"]["eligible_candles"],4)
        self.assertEqual(report["input"]["excluded"]["REFERENCE_MISMATCH"],1)

    def test_synthetic_data_is_excluded_by_default(self):
        trades,refs=self._rising_library(source="synthetic_sample_test",candles=4)
        report=validate_historical_hypotheses(
            trades,interval_seconds=60,tick_size=5.0,reference_candles=refs,horizons=(1,)
        )
        self.assertEqual(report["input"]["eligible_candles"],0)
        self.assertEqual(report["input"]["excluded"]["SYNTHETIC"],4)

    def test_future_outcome_does_not_cross_session_boundary(self):
        trades,refs=self._rising_library(candles=2)
        tz=ZoneInfo("America/Sao_Paulo")
        seq=max(t.sequence_no or 0 for t in trades)+1
        next_day=datetime(2026,10,9,9,0,tzinfo=tz)
        for i in range(30):
            trades.append(Trade(
                "WINHIST",next_day+timedelta(seconds=i*2),110+i//10,2,
                aggressor=AggressorSide.BUY,source="profit_selected_slice",
                buyer_id="BUYER_A",seller_id="PASSIVE",sequence_no=seq+i
            ))
        c=build_candles([t for t in trades if t.ts.date()==next_day.date()],60)[0]
        refs.append(ReferenceCandle(
            symbol=c.symbol,start=c.start,interval_seconds=60,
            open_ticks=c.open_ticks,high_ticks=c.high_ticks,low_ticks=c.low_ticks,
            close_ticks=c.close_ticks,volume=c.volume,trades=c.trades,source="test_reference"
        ))
        report=validate_historical_hypotheses(
            trades,interval_seconds=60,tick_size=5.0,reference_candles=refs,horizons=(1,)
        )
        row=next(x for x in report["directional_results"] if x["hypothesis_code"]=="AGRESSAO_ALINHADA_ALTA")
        self.assertEqual(row["with_contiguous_outcome"],1)


class CoreTests(unittest.TestCase):
    def test_build_candle(self):
        start = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
        candles = build_candles(trades_from_prices(start, [100, 105, 95, 102]), 60)
        self.assertEqual(len(candles), 1)
        c = candles[0]
        self.assertEqual((c.open_ticks, c.high_ticks, c.low_ticks, c.close_ticks), (100, 105, 95, 102))

    def test_counterfactual_preserves_ohlc(self):
        path = generate_ohlc_path(100, 110, 95, 108, points=40, seed=42)
        self.assertEqual(path[0], 100)
        self.assertEqual(path[-1], 108)
        self.assertEqual(max(path), 110)
        self.assertEqual(min(path), 95)

    def test_builtin_sample_shape(self):
        trades = generate_builtin_sample()
        self.assertEqual(len(trades), 2880)
        self.assertEqual(len({t.ts.date() for t in trades}), 6)
        self.assertEqual(len(build_candles(trades, 60)), 72)


class TrajectoryTests(unittest.TestCase):
    def test_direct_impulse(self):
        start = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
        family, confidence = classify_rule_family(trades_from_prices(start, list(range(100, 111))), 60)
        self.assertEqual(family, "DIRECT_IMPULSE_UP")
        self.assertGreaterEqual(confidence, 0.6)

    def test_low_sweep_reversal(self):
        start = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
        family, confidence = classify_rule_family(
            trades_from_prices(start, [100, 97, 94, 92, 95, 99, 103, 107, 110, 109]), 60
        )
        self.assertEqual(family, "SWEEP_LOW_REVERSAL")
        self.assertGreaterEqual(confidence, 0.5)

    def test_kmeans_is_deterministic(self):
        vectors = [(0.0, 0.0), (0.1, 0.1), (0.9, 0.9), (1.0, 1.0)]
        a1, c1 = deterministic_kmeans(vectors, 2)
        a2, c2 = deterministic_kmeans(vectors, 2)
        self.assertEqual(a1, a2)
        self.assertEqual(c1, c2)


class TransitionTests(unittest.TestCase):
    def test_does_not_cross_session_boundary(self):
        up = [100, 101, 102, 103, 104, 105, 106]
        down = [106, 105, 104, 103, 102, 101, 100]
        s1 = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
        s2 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
        trades = trades_from_prices(s1, up) + trades_from_prices(s1 + timedelta(minutes=1), down)
        trades += trades_from_prices(s2, up)
        result = analyze_stability_and_transitions(trades, interval_seconds=60, quality_only=False, clusters=2)
        self.assertEqual(sum(x["count"] for x in result["family_transitions"]), 1)

    def test_gap_does_not_create_transition(self):
        start = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
        up = [100, 101, 102, 103, 104, 105, 106]
        trades = trades_from_prices(start, up) + trades_from_prices(start + timedelta(minutes=2), up)
        result = analyze_stability_and_transitions(trades, interval_seconds=60, quality_only=False, clusters=1)
        self.assertEqual(result["family_transitions"], [])

    def test_triplet_is_counted(self):
        start = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
        patterns = [
            [100, 101, 102, 103, 104, 105, 106],
            [106, 105, 104, 103, 102, 101, 100],
            [100, 97, 94, 92, 96, 101, 108],
        ]
        trades = []
        for i, pattern in enumerate(patterns):
            trades += trades_from_prices(start + timedelta(minutes=i), pattern)
        result = analyze_stability_and_transitions(trades, interval_seconds=60, quality_only=False, clusters=2)
        self.assertEqual(sum(x["count"] for x in result["family_motifs"]), 1)


class ProfitExportTests(unittest.TestCase):
    def test_headerless_profit_reverse_order_preserves_identical_trades(self):
        content = (
            "WINTEST,07/10/26,10:01:00,3 - Comprador,1005,1,85 - Vendedor,Comprador\n"
            "WINTEST,07/10/26,10:00:59,3 - Comprador,1000,1,85 - Vendedor,RLP\n"
            "WINTEST,07/10/26,10:00:00,3 - Comprador,995,2,85 - Vendedor,Vendedor\n"
            "WINTEST,07/10/26,10:00:00,3 - Comprador,995,2,85 - Vendedor,Vendedor\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profit_trades.csv"
            path.write_text(content, encoding="ascii")
            trades, report = import_csv_with_report(path, symbol=None, tick_size=5.0, source="profit_csv")
        self.assertEqual(report.profile, "Nelogica / Profit — Trades sem cabeçalho (8 colunas)")
        self.assertEqual(report.source_order, "DESCENDING")
        self.assertEqual(report.timestamp_precision, "1 segundo")
        self.assertEqual(len(trades), 4)
        self.assertEqual([t.price_ticks for t in trades], [199, 199, 200, 201])
        self.assertEqual([t.sequence_no for t in trades], [1, 2, 3, 4])
        self.assertEqual(sum(t.quantity for t in trades), 6)
        self.assertIn("raw_aggressor=RLP", trades[2].flags or "")

    def test_profit_header_agressao_alias_is_recognized(self):
        content = (
            "Ativo;Data;Hora;Agente Comprador;Preço;Quantidade;Agente Vendedor;Agressão\n"
            "WINTEST;08/10/2026;10:00:00;3 - Comprador;1.000;2;85 - Vendedor;Comprador\n"
            "WINTEST;08/10/2026;10:00:01;3 - Comprador;1.005;3;85 - Vendedor;Vendedor\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profit_header_agressao.csv"
            path.write_text(content, encoding="cp1252")
            trades, report = import_csv_with_report(path, symbol=None, tick_size=5.0, source="profit_csv")
        self.assertEqual(report.aggressor_known_pct,100.0)
        self.assertEqual(trades[0].aggressor,AggressorSide.BUY)
        self.assertEqual(trades[1].aggressor,AggressorSide.SELL)

    def test_formatted_profit_reference_uses_quantidade_not_financial_volume(self):
        content = (
            "Ativo;Data;Hora;Abertura;Máximo;Mínimo;Fechamento;Volume;Quantidade\n"
            "WINTEST;07/10/2026;10:00:00;204.660;204.705;204.500;204.500;1.058.515.234,00;25.878\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profit_1min.csv"
            path.write_text(content, encoding="cp1252")
            refs, report = import_reference_candles(
                path, symbol=None, tick_size=5.0, interval_seconds=60, source="profit_ohlc_reference"
            )
        self.assertEqual(report.profile, "Nelogica / Profit — candles formatados")
        self.assertEqual(len(refs), 1)
        ref = refs[0]
        self.assertEqual(ref.open_ticks, 40932)
        self.assertEqual(ref.high_ticks, 40941)
        self.assertEqual(ref.low_ticks, 40900)
        self.assertEqual(ref.close_ticks, 40900)
        self.assertEqual(ref.volume, 25878)
        self.assertIsNone(ref.trades)

    def test_observed_window_excludes_partial_last_candle(self):
        start = datetime(2026, 10, 7, 10, 0, tzinfo=UTC)
        trades = [
            Trade("WINTEST", start, 200, 2, sequence_no=1),
            Trade("WINTEST", start + timedelta(seconds=59), 201, 3, sequence_no=2),
            Trade("WINTEST", start + timedelta(minutes=1), 201, 1, sequence_no=3),
        ]
        from candle_lab.reconciliation import ReferenceCandle
        refs = [
            ReferenceCandle("WINTEST", start, 60, 200, 201, 200, 201, volume=5),
            ReferenceCandle("WINTEST", start + timedelta(minutes=1), 60, 201, 205, 199, 202, volume=50),
        ]
        report = reconcile_observed_window(trades, refs, interval_seconds=60, tick_size=5.0)
        self.assertEqual(report["summary"]["reference_candles"], 1)
        self.assertEqual(report["summary"]["exact"], 1)
        self.assertEqual(report["observed_window"]["partial_boundary_candles"], 1)
        self.assertEqual(report["partial_boundary_references"][0]["status"], "PARTIAL_SOURCE_WINDOW")


class BulkImportTests(unittest.TestCase):
    def test_chunked_profit_import_reconcile_and_skip_same_file(self):
        content = (
            "WINTEST,07/10/26,10:01:59,3 - Comprador,1010,2,85 - Vendedor,Comprador\n"
            "WINTEST,07/10/26,10:01:30,3 - Comprador,1000,1,85 - Vendedor,RLP\n"
            "WINTEST,07/10/26,10:01:00,3 - Comprador,1005,3,85 - Vendedor,Vendedor\n"
            "WINTEST,07/10/26,10:00:59,3 - Comprador,1000,1,85 - Vendedor,Comprador\n"
            "WINTEST,07/10/26,10:00:30,3 - Comprador,995,2,85 - Vendedor,Vendedor\n"
            "WINTEST,07/10/26,10:00:00,3 - Comprador,990,3,85 - Vendedor,Vendedor\n"
        )
        tz = ZoneInfo("America/Sao_Paulo")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "WINTEST_TRADES.csv"
            csv_path.write_text(content, encoding="cp1252")
            store = MarketStore(root / "lab.duckdb")

            progress = []
            result = bulk_import_profit_file(
                csv_path, store=store, tick_size=5.0, chunk_rows=1000,
                progress=lambda info: progress.append(info),
            )
            self.assertEqual(result.status, "COMPLETED")
            self.assertEqual(result.processed_rows, 6)
            self.assertEqual(result.inserted_rows, 6)
            self.assertFalse(result.already_imported)
            self.assertEqual(result.source_order, "DESCENDING")
            self.assertEqual(result.rlp_rows, 1)
            self.assertTrue(any(x.get("phase") == "import" for x in progress))

            candles = aggregate_candles_sql(
                store, symbol="WINTEST", session_date="2026-10-07", interval_seconds=60
            )
            self.assertEqual(len(candles), 2)
            self.assertEqual(
                (candles[0]["open_ticks"], candles[0]["high_ticks"], candles[0]["low_ticks"], candles[0]["close_ticks"]),
                (198, 200, 198, 200),
            )
            self.assertEqual(candles[0]["volume"], 6)

            refs = [
                ReferenceCandle(
                    "WINTEST", datetime(2026,10,7,10,0,tzinfo=tz), 60,
                    198, 200, 198, 200, volume=6,
                ),
                ReferenceCandle(
                    "WINTEST", datetime(2026,10,7,10,1,tzinfo=tz), 60,
                    201, 202, 200, 202, volume=6,
                ),
            ]
            reconciliation = reconcile_store_references(
                store, symbol="WINTEST", session_date="2026-10-07",
                references=refs, interval_seconds=60, tick_size=5.0,
            )
            self.assertEqual(reconciliation["summary"]["exact"], 2)
            self.assertEqual(reconciliation["summary"]["mismatch"], 0)
            self.assertEqual(reconciliation["summary"]["exact_rate"], 1.0)

            second = bulk_import_profit_file(
                csv_path, store=store, tick_size=5.0, chunk_rows=1000
            )
            self.assertTrue(second.already_imported)
            self.assertEqual(len(store.load_trades("WINTEST")), 6)

            parquet = export_session_parquet(
                store, symbol="WINTEST", session_date="2026-10-07", output_dir=root / "parquet"
            )
            self.assertTrue(parquet.exists())
            self.assertGreater(parquet.stat().st_size, 0)


    def test_bulk_import_resumes_after_interruption(self):
        start = datetime(2026, 10, 7, 10, 16, 40)
        lines = []
        for i in range(1001):
            ts = start - timedelta(seconds=i)
            lines.append(
                f"WINRESUME,{ts.strftime('%d/%m/%y')},{ts.strftime('%H:%M:%S')},"
                f"3 - Comprador,{1000 + (i % 3) * 5},1,85 - Vendedor,Comprador\n"
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "WINRESUME_TRADES.csv"
            csv_path.write_text("".join(lines), encoding="cp1252")
            store = MarketStore(root / "lab.duckdb")
            interrupted = {"done": False}

            def stop_after_first_chunk(info):
                if info.get("phase") == "import" and not interrupted["done"]:
                    interrupted["done"] = True
                    raise RuntimeError("interrupcao simulada")

            with self.assertRaises(RuntimeError):
                bulk_import_profit_file(
                    csv_path, store=store, tick_size=5.0, chunk_rows=1000,
                    progress=stop_after_first_chunk,
                )

            with store.connect() as con:
                status = con.execute(
                    "SELECT status,processed_rows,byte_offset FROM bulk_imports"
                ).fetchone()
            self.assertEqual(status[0], "FAILED")
            self.assertEqual(status[1], 1000)
            self.assertGreater(status[2], 0)
            self.assertEqual(len(store.load_trades("WINRESUME")), 1000)

            resumed = bulk_import_profit_file(
                csv_path, store=store, tick_size=5.0, chunk_rows=1000
            )
            self.assertEqual(resumed.resumed_from_row, 1000)
            self.assertEqual(resumed.processed_rows, 1001)
            self.assertEqual(len(store.load_trades("WINRESUME")), 1001)


class ProfitNumberTests(unittest.TestCase):
    def test_profit_dot_grouped_price_uses_brazilian_thousands(self):
        self.assertEqual(str(_profit_decimal_number("205.935")), "205935")
        self.assertEqual(str(_profit_decimal_number("5.321,5")), "5321.5")
        self.assertEqual(str(_profit_decimal_number("205935")), "205935")
        # A regra genérica continua diferente: ponto isolado permanece decimal.
        self.assertEqual(str(_decimal_number("205.935")), "205.935")

    def test_profit_dot_grouped_price_is_valid_for_win_tick(self):
        content = (
            "WINBR,07/10/26,10:01:00,3 - Comprador,205.935,1,85 - Vendedor,Comprador\n"
            "WINBR,07/10/26,10:00:59,3 - Comprador,205.930,2,85 - Vendedor,Vendedor\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"WINBR.csv"
            path.write_text(content,encoding="cp1252")
            trades,report=import_csv_with_report(path,symbol="WINBR",tick_size=5.0,source="profit_csv")
            self.assertEqual(len(trades),2)
            self.assertEqual([t.price_ticks for t in trades],[41186,41187])
            self.assertEqual(report.source_order,"DESCENDING")


class SelectiveSliceTests(unittest.TestCase):
    def test_selective_slice_uses_half_open_interval_and_preserves_profit_order(self):
        content = (
            "WINSEL,07/10/26,10:03:00,3 - Comprador,1030,1,85 - Vendedor,Comprador\n"
            "WINSEL,07/10/26,10:02:30,3 - Comprador,1025,2,85 - Vendedor,Comprador\n"
            "WINSEL,07/10/26,10:02:00,3 - Comprador,1020,1,85 - Vendedor,Vendedor\n"
            "WINSEL,07/10/26,10:01:59,3 - Comprador,1015,3,85 - Vendedor,RLP\n"
            "WINSEL,07/10/26,10:01:00,3 - Comprador,1010,2,85 - Vendedor,Vendedor\n"
            "WINSEL,07/10/26,10:00:59,3 - Comprador,1005,1,85 - Vendedor,Comprador\n"
        )
        tz = ZoneInfo("America/Sao_Paulo")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "WINSEL_FULL.csv"
            output = root / "slice.csv"
            source.write_text(content, encoding="cp1252")

            slice_progress=[]
            result = slice_profit_trades(
                source,
                start=datetime(2026,10,7,10,1,tzinfo=tz),
                end=datetime(2026,10,7,10,3,tzinfo=tz),
                output_path=output,
                symbol="WINSEL",
                progress=slice_progress.append,
            )
            self.assertTrue(slice_progress)
            self.assertEqual(slice_progress[0]["percent"],0.0)
            self.assertEqual(slice_progress[-1]["percent"],100.0)
            self.assertEqual(slice_progress[-1]["bytes_processed"],slice_progress[-1]["bytes_total"])
            self.assertEqual(result.matched_rows, 4)
            self.assertEqual(result.source_order, "DESCENDING")
            self.assertTrue(result.stopped_early)
            raw = output.read_text(encoding="cp1252")
            self.assertNotIn("10:03:00", raw)
            self.assertNotIn("10:00:59", raw)

            trades, report = import_csv_with_report(
                output, symbol="WINSEL", tick_size=5.0, source="selected_slice"
            )
            self.assertEqual(report.source_order, "DESCENDING")
            self.assertEqual([t.ts.strftime("%H:%M:%S") for t in trades],
                             ["10:01:00","10:01:59","10:02:00","10:02:30"])
            self.assertEqual((result.first_source_row,result.last_source_row),(2,5))

            store=MarketStore(root/"lab.duckdb")
            rows1=range(result.last_source_row,result.first_source_row-1,-1)
            first_insert=store.add_selected_slice_trades(
                trades,tick_size=5.0,source_fingerprint=result.source_fingerprint,source_rows=rows1
            )
            self.assertEqual(first_insert["inserted"],4)

            output2=root/"slice2.csv"
            result2=slice_profit_trades(
                source,
                start=datetime(2026,10,7,10,2,tzinfo=tz),
                end=datetime(2026,10,7,10,4,tzinfo=tz),
                output_path=output2,
                symbol="WINSEL",
            )
            trades2,_=import_csv_with_report(output2,symbol="WINSEL",tick_size=5.0,source="selected_slice")
            rows2=range(result2.last_source_row,result2.first_source_row-1,-1)
            second_insert=store.add_selected_slice_trades(
                trades2,tick_size=5.0,source_fingerprint=result2.source_fingerprint,source_rows=rows2
            )
            self.assertEqual(second_insert["inserted"],1)
            self.assertEqual(second_insert["duplicates"],2)
            self.assertEqual(len(store.load_trades("WINSEL")),5)

    def test_selected_slice_reimport_enriches_missing_aggressor(self):
        tz=ZoneInfo("America/Sao_Paulo")
        ts=datetime(2026,10,7,10,0,tzinfo=tz)
        fingerprint="abc123"
        source_rows=[42]
        with tempfile.TemporaryDirectory() as tmp:
            store=MarketStore(Path(tmp)/"lab.duckdb")
            old=[
                Trade(
                    "WINFIX",ts,40000,7,aggressor=AggressorSide.NONE,
                    buyer_id=None,seller_id=None,sequence_no=1,source="profit_selected_slice"
                )
            ]
            first=store.add_selected_slice_trades(
                old,tick_size=5.0,source_fingerprint=fingerprint,source_rows=source_rows
            )
            self.assertEqual(first["inserted"],1)

            repaired=[
                Trade(
                    "WINFIX",ts,40000,7,aggressor=AggressorSide.BUY,
                    buyer_id="3 - XP",seller_id="85 - BTG",sequence_no=1,
                    flags="raw_aggressor=Comprador",source="profit_selected_slice"
                )
            ]
            second=store.add_selected_slice_trades(
                repaired,tick_size=5.0,source_fingerprint=fingerprint,source_rows=source_rows
            )
            self.assertEqual(second["inserted"],0)
            self.assertEqual(second["duplicates"],1)
            self.assertEqual(second["enriched"],1)
            stored=store.load_trades("WINFIX")
            self.assertEqual(stored[0].aggressor,AggressorSide.BUY)
            self.assertEqual(stored[0].buyer_id,"3 - XP")
            self.assertEqual(stored[0].seller_id,"85 - BTG")
            self.assertIn("raw_aggressor=Comprador",stored[0].flags or "")

    def test_headered_profit_file_with_extra_column_is_indexed_and_sliced(self):
        content = (
            "Ativo;Data;Hora;Número do Negócio;Agente Comprador;Preço;Quantidade;Agente Vendedor;Agressor\n"
            "WINHDR;07/10/26;10:03:00;1006;3 - Comprador;1.030,00;1;85 - Vendedor;Comprador\n"
            "WINHDR;07/10/26;10:02:30;1005;3 - Comprador;1.025,00;2;85 - Vendedor;Comprador\n"
            "WINHDR;07/10/26;10:02:00;1004;3 - Comprador;1.020,00;1;85 - Vendedor;Vendedor\n"
            "WINHDR;07/10/26;10:01:59;1003;3 - Comprador;1.015,00;3;85 - Vendedor;RLP\n"
            "WINHDR;07/10/26;10:01:00;1002;3 - Comprador;1.010,00;2;85 - Vendedor;Vendedor\n"
            "WINHDR;07/10/26;10:00:59;1001;3 - Comprador;1.005,00;1;85 - Vendedor;Comprador\n"
        )
        tz = ZoneInfo("America/Sao_Paulo")
        start = datetime(2026,10,7,10,1,tzinfo=tz)
        end = datetime(2026,10,7,10,3,tzinfo=tz)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "WINHDR_FULL.csv"
            source.write_text(content, encoding="cp1252")

            index = build_time_index(source,index_dir=root/"indexes",symbol="WINHDR")
            self.assertEqual(index.rows,6)
            self.assertTrue(index.source_has_header)
            self.assertEqual(index.source_header_line,1)
            self.assertIn("cabeçalho",index.layout_profile)
            self.assertEqual(index.source_order,"DESCENDING")

            located = locate_interval(index,start=start,end=end)
            self.assertEqual((located["source_row_min"],located["source_row_max"]),(3,6))
            self.assertEqual((located["chronological_open_row"],located["chronological_close_row"]),(6,3))
            self.assertEqual(located["trades"],4)

            output = root / "slice.csv"
            sliced = slice_profit_trades(
                source,start=start,end=end,output_path=output,symbol="WINHDR",
                seek_byte_start=located["byte_start"],seek_byte_end=located["byte_end"],
                source_row_base=located["source_row_min"]-1,
            )
            self.assertTrue(sliced.source_has_header)
            self.assertEqual((sliced.first_source_row,sliced.last_source_row),(3,6))
            trades, report = import_csv_with_report(
                output,symbol="WINHDR",tick_size=5.0,source="selected_slice"
            )
            self.assertEqual(len(trades),4)
            self.assertEqual(report.source_order,"DESCENDING")
            self.assertEqual([t.ts.strftime("%H:%M:%S") for t in trades],
                             ["10:01:00","10:01:59","10:02:00","10:02:30"])

    def test_headerless_profit_file_with_trade_id_column_is_supported(self):
        content = (
            "WINID,07/10/26,10:02:00,1003,3 - Comprador,1020,1,85 - Vendedor,Vendedor\n"
            "WINID,07/10/26,10:01:30,1002,3 - Comprador,1015,2,85 - Vendedor,Comprador\n"
            "WINID,07/10/26,10:01:00,1001,3 - Comprador,1010,3,85 - Vendedor,RLP\n"
            "WINID,07/10/26,10:00:59,1000,3 - Comprador,1005,1,85 - Vendedor,Comprador\n"
        )
        tz=ZoneInfo("America/Sao_Paulo")
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"WINID.csv"
            source.write_text(content,encoding="cp1252")
            index=build_time_index(source,index_dir=root/"indexes",symbol="WINID")
            self.assertIn("9 colunas",index.layout_profile)
            located=locate_interval(
                index,
                start=datetime(2026,10,7,10,1,tzinfo=tz),
                end=datetime(2026,10,7,10,2,tzinfo=tz),
            )
            self.assertEqual(located["trades"],2)
            output=root/"slice.csv"
            sliced=slice_profit_trades(
                source,
                start=datetime(2026,10,7,10,1,tzinfo=tz),
                end=datetime(2026,10,7,10,2,tzinfo=tz),
                output_path=output,
                symbol="WINID",
                seek_byte_start=located["byte_start"],
                seek_byte_end=located["byte_end"],
                source_row_base=located["source_row_min"]-1,
            )
            trades,report=import_csv_with_report(output,symbol="WINID",tick_size=5.0,source="selected_slice")
            self.assertEqual(len(trades),2)
            self.assertEqual([t.ts.strftime("%H:%M:%S") for t in trades],["10:01:00","10:01:30"])

    def test_time_index_locates_exact_rows_and_indexed_slice_matches(self):
        content = (
            "WINIDX,07/10/26,10:03:00,3 - Comprador,1030,1,85 - Vendedor,Comprador\n"
            "WINIDX,07/10/26,10:02:30,3 - Comprador,1025,2,85 - Vendedor,Comprador\n"
            "WINIDX,07/10/26,10:02:00,3 - Comprador,1020,1,85 - Vendedor,Vendedor\n"
            "WINIDX,07/10/26,10:01:59,3 - Comprador,1015,3,85 - Vendedor,RLP\n"
            "WINIDX,07/10/26,10:01:00,3 - Comprador,1010,2,85 - Vendedor,Vendedor\n"
            "WINIDX,07/10/26,10:00:59,3 - Comprador,1005,1,85 - Vendedor,Comprador\n"
        )
        tz = ZoneInfo("America/Sao_Paulo")
        start = datetime(2026,10,7,10,1,tzinfo=tz)
        end = datetime(2026,10,7,10,3,tzinfo=tz)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "WINIDX_FULL.csv"
            source.write_text(content, encoding="cp1252")

            progress=[]
            index = build_time_index(source,index_dir=root/"indexes",symbol="WINIDX",progress=progress.append)
            self.assertEqual(index.rows,6)
            self.assertTrue(progress)
            self.assertEqual(progress[-1]["percent"],100.0)
            self.assertEqual(progress[-1]["bytes_processed"],progress[-1]["bytes_total"])
            self.assertEqual(index.source_order,"DESCENDING")
            self.assertEqual(len(index.buckets),4)

            located = locate_interval(index,start=start,end=end)
            self.assertEqual(located["source_row_min"],2)
            self.assertEqual(located["source_row_max"],5)
            self.assertEqual(located["chronological_open_row"],5)
            self.assertEqual(located["chronological_close_row"],2)
            self.assertEqual(located["trades"],4)

            mapped = locate_candles(
                index,
                candle_starts=[start,start+timedelta(minutes=1)],
                interval_seconds=60,
            )
            self.assertEqual((mapped[0]["source_row_min"],mapped[0]["source_row_max"]),(4,5))
            self.assertEqual((mapped[0]["chronological_open_row"],mapped[0]["chronological_close_row"]),(5,4))
            self.assertEqual((mapped[1]["source_row_min"],mapped[1]["source_row_max"]),(2,3))
            self.assertEqual((mapped[1]["chronological_open_row"],mapped[1]["chronological_close_row"]),(3,2))

            mapped_m2 = locate_candles(index,candle_starts=[start],interval_seconds=120)
            self.assertEqual((mapped_m2[0]["source_row_min"],mapped_m2[0]["source_row_max"]),(2,5))
            self.assertEqual(mapped_m2[0]["trades"],4)

            with self.assertRaises(ValueError):
                locate_interval(
                    index,
                    start=start+timedelta(seconds=30),
                    end=end,
                )

            full_output = root / "full_scan.csv"
            full = slice_profit_trades(source,start=start,end=end,output_path=full_output,symbol="WINIDX")

            indexed_output = root / "indexed.csv"
            indexed = slice_profit_trades(
                source,start=start,end=end,output_path=indexed_output,symbol="WINIDX",
                seek_byte_start=located["byte_start"],seek_byte_end=located["byte_end"],
                source_row_base=located["source_row_min"]-1,
            )
            self.assertTrue(indexed.indexed_seek)
            self.assertEqual(indexed.scanned_rows,4)
            self.assertEqual((indexed.first_source_row,indexed.last_source_row),(2,5))
            self.assertEqual(full_output.read_bytes(),indexed_output.read_bytes())

            cached,built_now = ensure_time_index(source,index_dir=root/"indexes",symbol="WINIDX")
            self.assertFalse(built_now)
            self.assertEqual(cached.source_sha256,index.source_sha256)

    def test_time_index_aggregates_m15_from_m1_buckets(self):
        tz = ZoneInfo("America/Sao_Paulo")
        lines=[]
        for minute in range(15,-1,-1):
            ts=datetime(2026,10,7,9,minute,tzinfo=tz)
            lines.append(
                f"WINM15,07/10/26,{ts.strftime('%H:%M:%S')},3 - Comprador,"
                f"{1000+minute*5},1,85 - Vendedor,Comprador\n"
            )
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"WINM15.csv"
            source.write_text("".join(lines),encoding="cp1252")
            index=build_time_index(source,index_dir=root/"indexes",symbol="WINM15")
            start=datetime(2026,10,7,9,0,tzinfo=tz)
            mapped=locate_candles(index,candle_starts=[start],interval_seconds=900)
            self.assertEqual(mapped[0]["status"],"FOUND")
            self.assertEqual(mapped[0]["trades"],15)
            self.assertEqual((mapped[0]["source_row_min"],mapped[0]["source_row_max"]),(2,16))
            self.assertEqual((mapped[0]["chronological_open_row"],mapped[0]["chronological_close_row"]),(16,2))

    def test_slice_aware_reconciliation_skips_unselected_gaps(self):
        tz = ZoneInfo("America/Sao_Paulo")
        trades = [
            Trade("WINSEL",datetime(2026,10,7,10,0,0,tzinfo=tz),200,1,source="profit_selected_slice",sequence_no=1),
            Trade("WINSEL",datetime(2026,10,7,10,0,59,tzinfo=tz),201,1,source="profit_selected_slice",sequence_no=2),
            Trade("WINSEL",datetime(2026,10,7,10,2,0,tzinfo=tz),202,1,source="profit_selected_slice",sequence_no=3),
            Trade("WINSEL",datetime(2026,10,7,10,2,59,tzinfo=tz),203,1,source="profit_selected_slice",sequence_no=4),
        ]
        refs = [
            ReferenceCandle("WINSEL",datetime(2026,10,7,10,0,tzinfo=tz),60,200,201,200,201,volume=2),
            ReferenceCandle("WINSEL",datetime(2026,10,7,10,1,tzinfo=tz),60,205,206,204,205,volume=99),
            ReferenceCandle("WINSEL",datetime(2026,10,7,10,2,tzinfo=tz),60,202,203,202,203,volume=2),
        ]
        report = reconcile_available_candles(trades,refs,interval_seconds=60,tick_size=5.0)
        self.assertEqual(report["summary"]["reference_candles"],2)
        self.assertEqual(report["summary"]["exact"],2)
        self.assertEqual(report["summary"]["no_data"],0)
        self.assertEqual(report["reference_candles_skipped_outside_slices"],1)

    def test_reference_overview_works_without_any_tick_trades(self):
        tz = ZoneInfo("America/Sao_Paulo")
        with tempfile.TemporaryDirectory() as tmp:
            store = MarketStore(Path(tmp) / "lab.duckdb")
            refs = [
                ReferenceCandle("WINONLY", datetime(2026,10,7,10,0,tzinfo=tz), 60, 200,202,199,201,volume=10),
                ReferenceCandle("WINONLY", datetime(2026,10,7,10,1,tzinfo=tz), 60, 201,203,200,202,volume=11),
            ]
            store.add_reference_candles(refs, tick_size=5.0)
            self.assertEqual(store.list_sessions("WINONLY"), [])
            sessions = store.list_reference_sessions("WINONLY")
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["candles"], 2)
            overview = store.reference_overview()
            self.assertEqual(overview[0]["symbol"], "WINONLY")
            self.assertEqual(overview[0]["interval_seconds"], 60)


class UiContractTests(unittest.TestCase):
    def test_precise_interval_selection_controls_are_wired(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "src" / "candle_lab" / "web" / "static" / "index.html").read_text(encoding="utf-8")
        js = (root / "src" / "candle_lab" / "web" / "static" / "app.js").read_text(encoding="utf-8")
        required_ids = [
            "zoomRange","zoomInBtn","zoomOutBtn","panLeftBtn","panRightBtn","resetZoomBtn",
            "startTimeInput","endTimeInput","applyTimeSelectionBtn","zoomSelectionBtn",
            "dayCanvas","selectionLabel","selectionCount","locateBtn","sliceBtn",
            "indexProgressWrap","indexProgressPct","indexProgressText","indexProgressBar",
            "sliceProgressWrap","sliceProgressPct","sliceProgressText","sliceProgressBar",
            "aggressionKpis","topBuyAggressors","topSellAggressors","aggressionBody","aggressionMethod",
            "waveSummary","openWaveBox","waveBody","waveMethod",
            "interpretationReplayNotice","interpretationContent","interpretationQuality",
            "closingSynthesis","processDescription","observedFacts","hypothesisList",
            "interpretationLimitations","copyInterpretationBtn",
            "validationHorizons","historicalValidationBtn","validationSummary","validationNotice",
            "historicalValidationBody","descriptiveValidation","validationWarnings",
        ]
        for control_id in required_ids:
            self.assertIn(f'id="{control_id}"', html)
            self.assertIn(f"$('{control_id}')", js)
        self.assertIn("Gráfico diário para seleção", html)
        self.assertIn("INÍCIO", js)
        self.assertIn("FIM", js)
        self.assertIn("Ctrl", html)
        self.assertIn("/api/time-index/start", js)
        self.assertIn("/api/time-index/jobs/", js)
        self.assertIn("/api/slice-import/start", js)
        self.assertIn("/api/slice-import/jobs/", js)
        self.assertIn("renderAggressionWaves", js)
        self.assertIn("drawWaveTerminationMarkers", js)
        self.assertIn("renderInterpretation", js)
        self.assertIn("copyInterpretation", js)
        self.assertIn("historicalValidation", js)
        self.assertIn("/api/research/hypothesis-validation", js)

class SessionQualityPersistenceTests(unittest.TestCase):
    def test_replace_session_quality_persists_payload_without_parameter_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            store=MarketStore(root/"lab.duckdb")
            trades=generate_builtin_sample("WINQUAL")
            qualities=assess_library_quality(trades)
            self.assertGreater(len(qualities),0)
            inserted=store.replace_session_quality("WINQUAL",qualities)
            self.assertEqual(inserted,len(qualities))
            first=qualities[0]
            payload=store.get_session_quality("WINQUAL",first.session_date)
            self.assertIsNotNone(payload)
            self.assertTrue(payload["model_version"])
            with store.connect() as con:
                row=con.execute(
                    "SELECT quality_key,symbol,session_date,model_version,payload_json,updated_at "
                    "FROM session_quality WHERE symbol=? ORDER BY session_date LIMIT 1",
                    ["WINQUAL"],
                ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[1],"WINQUAL")
            self.assertIsNotNone(row[4])
            self.assertIsNotNone(row[5])


class StorageTests(unittest.TestCase):
    def test_duckdb_and_parquet_roundtrip(self):
        start = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
        trades = trades_from_prices(start, [100, 101, 102, 103])
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "lab.duckdb"
            parquet = Path(tmp) / "trades.parquet"
            store = MarketStore(db)
            inserted = store.add_trades(trades, tick_size=5.0)
            self.assertEqual(inserted["inserted"], 4)
            loaded = store.load_trades("WINTEST")
            self.assertEqual(len(loaded), 4)
            store.export_parquet(parquet)
            self.assertTrue(parquet.exists())
            self.assertGreater(parquet.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
