import os
import sys
import unittest

backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from sukoon.cortex.catalog import list_all_specialists, get_specialist
from sukoon.cortex.schemas import (
    UniversalAgentOutput, AgentStatus, Finding, FindingKind, FindingSeverity,
    Uncertainty, Recommendation, RecommendationAction
)
from sukoon.cortex.runtime import CortexRuntime
from sukoon.cortex.scheduler import CortexScheduler
from sukoon.cortex.arbitrator import MasterMarketJudgeArbitrator

class TestCortexSpecialistsAndScheduler(unittest.TestCase):
    def test_specialist_catalog_count_and_groups(self):
        specialists = list_all_specialists()
        self.assertEqual(len(specialists), 100, f"Expected 100 roles, found {len(specialists)}")

        # Check groups 01 through 15 are all present
        groups = {s.group_id for s in specialists}
        expected_groups = {f"G{i:02d}" for i in range(1, 16)}
        self.assertEqual(groups, expected_groups)

        # Check SAIG has 15 roles
        saig_roles = [s for s in specialists if s.group_id == "G15"]
        self.assertEqual(len(saig_roles), 15)

    def test_universal_output_schema_validation(self):
        # Valid output
        output = UniversalAgentOutput(
            agent_id="G01-R01",
            task_id="tsk-12345",
            status=AgentStatus.COMPLETED,
            started_at_utc="2026-11-15T09:00:00Z",
            completed_at_utc="2026-11-15T09:00:01Z",
            findings=[
                Finding(
                    claim="Symbol verified in official universe",
                    kind=FindingKind.CALCULATION,
                    severity=FindingSeverity.INFO
                )
            ],
            uncertainty=Uncertainty(description="Deterministic certainty"),
            recommendation=Recommendation(
                action=RecommendationAction.NONE,
                rationale="No issues detected"
            )
        )
        self.assertEqual(output.agent_id, "G01-R01")

        # Invalid agent_id regex pattern should raise ValueError
        with self.assertRaises(ValueError):
            UniversalAgentOutput(
                agent_id="INVALID_AGENT",
                task_id="tsk-123",
                status=AgentStatus.COMPLETED,
                started_at_utc="2026-11-15T09:00:00Z",
                completed_at_utc="2026-11-15T09:00:01Z",
                uncertainty=Uncertainty(description="test"),
                recommendation=Recommendation(action=RecommendationAction.NONE, rationale="ok")
            )

    def test_cortex_runtime_and_scheduler_priority(self):
        runtime = CortexRuntime(mock_mode=True)
        scheduler = CortexScheduler(runtime=runtime)

        # Enqueue low priority discovery task (priority=10)
        t_low = scheduler.enqueue_task("G08-R01", {"symbol": "AAPL"}, priority=10)
        
        # Enqueue urgent risk task (priority=1)
        t_high = scheduler.enqueue_task("G12-R01", {"symbol": "AAPL"}, priority=1)

        # Process next task: High priority (priority=1) must execute first!
        first_out = scheduler.process_next_task()
        self.assertIsNotNone(first_out)
        self.assertEqual(first_out.task_id, t_high)
        self.assertEqual(first_out.agent_id, "G12-R01")

        # Second task: Low priority executes second
        second_out = scheduler.process_next_task()
        self.assertIsNotNone(second_out)
        self.assertEqual(second_out.task_id, t_low)
        self.assertEqual(second_out.agent_id, "G08-R01")

    def test_arbitrator_critical_dissent_preservation(self):
        runtime = CortexRuntime(mock_mode=True)
        role_quant = get_specialist("G03-R01")
        role_saig = get_specialist("G15-R01")

        out1 = runtime.execute_specialist_task(role_quant, "tsk-1", {})
        out2 = runtime.execute_specialist_task(role_saig, "tsk-2", {})
        
        # Inject critical dissent from SAIG red-team
        out2.findings.append(
            Finding(
                claim="Data leakage detected in feature pipeline",
                kind=FindingKind.OBSERVATION,
                severity=FindingSeverity.CRITICAL
            )
        )

        synth = MasterMarketJudgeArbitrator.arbitrate("strat-alpha", "SPY", [out1, out2])
        self.assertTrue(synth.critical_dissent_found)
        self.assertEqual(synth.decision, "VETO_DISAGREEMENT")
        self.assertIn("G15-R01 CRITICAL: Data leakage detected", synth.dissenting_claims[0])

if __name__ == "__main__":
    unittest.main()
