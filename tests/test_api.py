import os
import sys
import unittest
from starlette.testclient import TestClient

backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from sukoon.api.main import app

class TestFastApiEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_and_readiness(self):
        res_h = self.client.get("/api/v1/system/health")
        self.assertEqual(res_h.status_code, 200)
        data_h = res_h.json()
        self.assertEqual(data_h["status"], "HEALTHY")
        self.assertEqual(data_h["environment"], "PAPER")

        res_r = self.client.get("/api/v1/system/readiness")
        self.assertEqual(res_r.status_code, 200)
        self.assertTrue(res_r.json()["ready"])

    def test_system_resources_12gb_ceiling(self):
        res = self.client.get("/api/v1/system/resources")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["cloud_ceiling_mb"], 12288)
        self.assertGreater(data["memory_headroom_pct"], 0)
        self.assertEqual(data["llama_concurrency_slots"], 1)

    def test_agents_catalog_endpoint(self):
        res = self.client.get("/api/v1/agents")
        self.assertEqual(res.status_code, 200)
        agents = res.json()
        self.assertEqual(len(agents), 100)

        # Filter by group G15
        res_g15 = self.client.get("/api/v1/agents?group_id=G15")
        self.assertEqual(res_g15.status_code, 200)
        self.assertEqual(len(res_g15.json()), 15)

    def test_paper_order_submission_with_guardian(self):
        # Setting a marketable limit price ($505.00) that fills against simulated market ($500.00)
        order_payload = {
            "strategy_id": "trend_spy",
            "strategy_version": "1.0.0",
            "symbol": "SPY",
            "action": "BUY",
            "quantity": 5,
            "limit_price": 505.0,
            "order_type": "LIMIT",
            "idempotency_key": "api-test-key-101"
        }
        res = self.client.post("/api/v1/orders/paper-submit", json=order_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "EXECUTED")
        self.assertTrue(data["order_id"])

        # Check portfolio endpoint
        res_p = self.client.get("/api/v1/portfolio/paper")
        self.assertEqual(res_p.status_code, 200)
        p_data = res_p.json()
        self.assertEqual(p_data["positions"].get("SPY"), 5)

if __name__ == "__main__":
    unittest.main()
