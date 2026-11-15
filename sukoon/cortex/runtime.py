"""
Project Sukoon — Cortex Shared llama.cpp Inference Runtime
Complying with SUK-ARCH-0001, SUK-ARCH-0003, and ADR-001.
One instance, single concurrency slot, shared model weights.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, Optional
import httpx
from sukoon.cortex.catalog import SpecialistRoleCard
from sukoon.cortex.schemas import (
    AgentStatus,
    CalibrationStatus,
    Finding,
    FindingKind,
    FindingSeverity,
    Recommendation,
    RecommendationAction,
    Uncertainty,
    UniversalAgentOutput,
)


class CortexRuntime:
    """Manages inference requests to the shared local llama.cpp runtime."""

    def __init__(
        self,
        endpoint_url: str = "http://localhost:8080/v1",
        model_id: str = "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        timeout_seconds: float = 30.0,
        mock_mode: Optional[bool] = None
    ) -> None:
        import os
        self.endpoint_url = os.getenv("LLAMA_CPP_ENDPOINT", endpoint_url)
        self.model_id = os.getenv("LLAMA_CPP_MODEL_ID", model_id)
        self.timeout_seconds = timeout_seconds
        if mock_mode is not None:
            self.mock_mode = mock_mode
        else:
            self.mock_mode = os.getenv("LLAMA_CPP_MOCK_MODE", "false").lower() in ("true", "1")
        self._inference_lock = threading.Lock()  # Strictly enforces concurrency=1

    def execute_specialist_task(
        self,
        role: SpecialistRoleCard,
        task_id: str,
        input_data: Dict[str, Any],
        input_event_ids: Optional[list[str]] = None
    ) -> UniversalAgentOutput:
        """Executes a specialist task through the shared runtime."""
        started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        input_ids = input_event_ids or []

        # Acquire single concurrency slot
        acquired = self._inference_lock.acquire(timeout=self.timeout_seconds)
        if not acquired:
            completed_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            return UniversalAgentOutput(
                agent_id=role.role_id,
                task_id=task_id,
                status=AgentStatus.FAILED,
                started_at_utc=started_utc,
                completed_at_utc=completed_utc,
                input_event_ids=input_ids,
                evidence_refs=[],
                findings=[],
                limitations=["Inference runtime concurrency queue timed out."],
                uncertainty=Uncertainty(
                    description="Execution failed due to queue congestion",
                    calibration_status=CalibrationStatus.NOT_APPLICABLE
                ),
                recommendation=Recommendation(
                    action=RecommendationAction.REQUEST_MORE_DATA,
                    rationale="Inference slot busy. Reschedule when queue clears."
                ),
                metrics={"latency_ms": int(self.timeout_seconds * 1000)},
                errors=["QUEUE_TIMEOUT"]
            )

        start_time = time.monotonic()
        try:
            if self.mock_mode:
                # Deterministic simulated response
                time.sleep(0.01)  # Minimal latency simulation
                completed_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                latency_ms = int((time.monotonic() - start_time) * 1000)

                return UniversalAgentOutput(
                    agent_id=role.role_id,
                    task_id=task_id,
                    status=AgentStatus.COMPLETED,
                    started_at_utc=started_utc,
                    completed_at_utc=completed_utc,
                    input_event_ids=input_ids,
                    evidence_refs=[f"ev-{task_id[:8]}"],
                    findings=[
                        Finding(
                            claim=f"Analyzed {role.primary_task} successfully within boundary: {role.hard_boundary}",
                            kind=FindingKind.CALCULATION if role.role_type == "DETERMINISTIC" else FindingKind.OBSERVATION,
                            support_refs=[f"ev-{task_id[:8]}"],
                            counterevidence_refs=[],
                            severity=FindingSeverity.INFO
                        )
                    ],
                    limitations=[role.hard_boundary],
                    uncertainty=Uncertainty(
                        description="Deterministic analysis with zero model hallucination" if role.role_type == "DETERMINISTIC" else "Advisory specialist output from shared llama.cpp weights",
                        calibration_status=CalibrationStatus.CALIBRATED if role.role_type == "DETERMINISTIC" else CalibrationStatus.NOT_CALIBRATED
                    ),
                    recommendation=Recommendation(
                        action=RecommendationAction.NONE,
                        rationale=f"{role.primary_task} completed within normal parameters."
                    ),
                    metrics={"latency_ms": latency_ms, "tokens_used": 128},
                    errors=[],
                    model_runtime_id="llama.cpp-local-1",
                    model_id=self.model_id
                )
            else:
                # Live HTTP call to llama.cpp OpenAI-compatible endpoint
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    resp = client.post(
                        f"{self.endpoint_url}/chat/completions",
                        json={
                            "model": self.model_id,
                            "messages": [
                                {"role": "system", "content": role.prompt},
                                {"role": "user", "content": json.dumps(input_data)}
                            ],
                            "max_tokens": 512,
                            "temperature": 0.2
                        }
                    )
                    resp.raise_for_status()
                    completed_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    latency_ms = int((time.monotonic() - start_time) * 1000)

                    return UniversalAgentOutput(
                        agent_id=role.role_id,
                        task_id=task_id,
                        status=AgentStatus.COMPLETED,
                        started_at_utc=started_utc,
                        completed_at_utc=completed_utc,
                        input_event_ids=input_ids,
                        evidence_refs=[],
                        findings=[
                            Finding(
                                claim=f"Evaluated {role.primary_task}",
                                kind=FindingKind.OBSERVATION,
                                support_refs=[],
                                counterevidence_refs=[],
                                severity=FindingSeverity.INFO
                            )
                        ],
                        limitations=[role.hard_boundary],
                        uncertainty=Uncertainty(
                            description="Live LLM inference",
                            calibration_status=CalibrationStatus.NOT_CALIBRATED
                        ),
                        recommendation=Recommendation(
                            action=RecommendationAction.NONE,
                            rationale="Completed"
                        ),
                        metrics={"latency_ms": latency_ms},
                        model_runtime_id="llama.cpp-live",
                        model_id=self.model_id
                    )
        finally:
            self._inference_lock.release()
