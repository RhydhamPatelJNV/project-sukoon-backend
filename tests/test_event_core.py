import os
import sys
import unittest
from datetime import datetime, timezone

# Ensure backend root is on sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from sukoon.core.events import EventEnvelope, EventType
from sukoon.core.ledger import EventLedger
from sukoon.core.clock import SukoonClock
from sukoon.data.quality import DataQualityEngine, DataQualityStatus

class TestEventCore(unittest.TestCase):
    def test_canonical_envelope_hash_and_immutability(self):
        payload = {"symbol": "AAPL", "price": 185.50, "qty": 10}
        event = EventEnvelope.create(
            event_type=EventType.MARKET_QUOTE_RECEIVED,
            source="alpaca_market_data",
            payload=payload,
            environment="PAPER"
        )
        
        self.assertTrue(event.event_id)
        self.assertTrue(event.payload_hash)
        self.assertEqual(event.environment, "PAPER")
        
        # Test serialization
        serialized = event.serialize()
        self.assertIn("AAPL", serialized)
        self.assertIn(event.payload_hash, serialized)

    def test_event_ledger_append_and_query(self):
        ledger = EventLedger(":memory:")
        self.assertEqual(ledger.count(), 0)

        e1 = EventEnvelope.create(
            event_type=EventType.SYSTEM_STARTED,
            source="system_boot",
            payload={"version": "0.1.0"},
            environment="RESEARCH"
        )
        seq1 = ledger.append(e1, destinations=["cortex_queue"])
        self.assertEqual(seq1, 1)
        self.assertEqual(ledger.count(), 1)

        e2 = EventEnvelope.create(
            event_type=EventType.ORDER_CREATED,
            source="strategy_alpha",
            payload={"order_id": "ord-001", "symbol": "MSFT"},
            environment="PAPER"
        )
        seq2 = ledger.append(e2)
        self.assertEqual(seq2, 2)
        self.assertEqual(ledger.count(), 2)

        # Retrieve by event ID
        retrieved = ledger.get_by_event_id(e1.event_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.event_id, e1.event_id)
        self.assertEqual(retrieved.payload_hash, e1.payload_hash)

        # Filter by environment
        paper_events = ledger.get_events(environment="PAPER")
        self.assertEqual(len(paper_events), 1)
        self.assertEqual(paper_events[0].event_id, e2.event_id)

    def test_clock_live_and_simulated(self):
        clock = SukoonClock()
        self.assertFalse(clock.is_simulated)
        now_live = clock.now()
        self.assertIsNotNone(now_live)

        t_sim = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        sim_clock = SukoonClock(simulated_start_utc=t_sim)
        self.assertTrue(sim_clock.is_simulated)
        self.assertEqual(sim_clock.now(), t_sim)

        t_future = datetime(2025, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        sim_clock.advance_to(t_future)
        self.assertEqual(sim_clock.now(), t_future)

        # Rejects backwards time travel
        with self.assertRaises(ValueError):
            sim_clock.advance_to(t_sim)

    def test_data_quality_validations(self):
        dq = DataQualityEngine(max_quote_spread_pct=0.05, max_single_tick_jump_pct=0.10)

        # Normal quote
        status, _ = dq.validate_quote(100.0, 100.05, 500, 500, prev_close=100.0)
        self.assertEqual(status, DataQualityStatus.VALIDATED)

        # Inverted market
        status, reasons = dq.validate_quote(105.0, 100.0, 100, 100)
        self.assertEqual(status, DataQualityStatus.SUSPECT)
        self.assertIn("Inverted market", reasons[0])

        # Negative price -> quarantined
        status, reasons = dq.validate_quote(-10.0, 100.0, 100, 100)
        self.assertEqual(status, DataQualityStatus.QUARANTINED)

        # Valid Bar
        b_status, _ = dq.validate_bar(100.0, 105.0, 99.0, 103.0, 10000)
        self.assertEqual(b_status, DataQualityStatus.VALIDATED)

        # Corrupt Bar (Low > High)
        b_status_bad, _ = dq.validate_bar(100.0, 95.0, 105.0, 102.0, 10000)
        self.assertEqual(b_status_bad, DataQualityStatus.QUARANTINED)

if __name__ == "__main__":
    unittest.main()
