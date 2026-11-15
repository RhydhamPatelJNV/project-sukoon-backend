import os
import sys
import unittest

backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from sukoon.evolution.sandbox import EvolutionSandbox
from sukoon.evolution.mutator import ProposalGenerator

class TestEvolutionSandbox(unittest.TestCase):
    def test_air_gap_prohibits_network_and_broker_access(self):
        sandbox = EvolutionSandbox(network_isolated=True)

        # Malicious or buggy mutant code trying to reach socket or broker
        rogue_code = "import socket\ndef run(): socket.connect(('api.alpaca.markets', 443))"
        result = sandbox.run_shadow_evaluation(
            candidate_id="cand-001",
            mutant_code=rogue_code,
            historical_dataset=[0.01, -0.01, 0.02]
        )
        self.assertEqual(result.execution_status, "VIOLATION_DETECTED")
        self.assertFalse(result.promoted_to_production)
        self.assertTrue(any("socket" in v for v in result.violations))

    def test_clean_candidate_shadow_eval_no_auto_deploy(self):
        sandbox = EvolutionSandbox(network_isolated=True)
        clean_code = "def calculate_rsi(prices, period=14): return 50.0"
        result = sandbox.run_shadow_evaluation(
            candidate_id="cand-002",
            mutant_code=clean_code,
            historical_dataset=[0.01, -0.01, 0.02]
        )
        self.assertEqual(result.execution_status, "SUCCESS")
        self.assertFalse(result.promoted_to_production) # MUST BE FALSE

    def test_proposal_formatting_and_hashes(self):
        prop = ProposalGenerator.create_proposal(
            target="G02-R01",
            mutation_type="PROMPT_MUTATION",
            original_code="System: Detect trend.",
            proposed_code="System: Detect multi-timeframe trend with exhaustion checks.",
            rationale="Reduces false breakouts in choppy regimes.",
            shadow_sharpe_delta=0.25
        )
        md = prop.to_markdown()
        self.assertIn("G02-R01", md)
        self.assertIn("+0.25", md)
        self.assertIn("Automated deployment is strictly disabled", md)

if __name__ == "__main__":
    unittest.main()
