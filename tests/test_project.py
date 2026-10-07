import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from candle_lab.candles import build_candles
from candle_lab.counterfactual import generate_ohlc_path
from candle_lab.models import Trade
from candle_lab.importers import import_csv_with_report
from candle_lab.reconciliation import import_reference_candles, reconcile_observed_window
from candle_lab.sample import generate_builtin_sample
from candle_lab.storage import MarketStore
from candle_lab.trajectory import classify_rule_family, deterministic_kmeans
from candle_lab.transitions import analyze_stability_and_transitions

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
