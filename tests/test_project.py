import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
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
from candle_lab.bulk import bulk_import_profit_file, aggregate_candles_sql, reconcile_store_references, export_session_parquet
from candle_lab.reconciliation import ReferenceCandle
from candle_lab.slice import slice_profit_trades

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

            result = slice_profit_trades(
                source,
                start=datetime(2026,10,7,10,1,tzinfo=tz),
                end=datetime(2026,10,7,10,3,tzinfo=tz),
                output_path=output,
                symbol="WINSEL",
            )
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
