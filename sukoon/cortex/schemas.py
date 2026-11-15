"""
Project Sukoon — Universal Specialist Output Schema (Pydantic v2)
Complying with SUK-API-0001, System Architecture §9, and additionalProperties: false.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AgentStatus(str, Enum):
    COMPLETED = "COMPLETED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    FAILED = "FAILED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    QUARANTINED = "QUARANTINED"


class FindingKind(str, Enum):
    OBSERVATION = "OBSERVATION"
    CALCULATION = "CALCULATION"
    HYPOTHESIS = "HYPOTHESIS"
    UNKNOWN = "UNKNOWN"


class FindingSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str
    kind: FindingKind
    support_refs: List[str] = Field(default_factory=list)
    counterevidence_refs: List[str] = Field(default_factory=list)
    severity: FindingSeverity = FindingSeverity.INFO


class CalibrationStatus(str, Enum):
    NOT_CALIBRATED = "NOT_CALIBRATED"
    CALIBRATED = "CALIBRATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Uncertainty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    calibration_status: CalibrationStatus = CalibrationStatus.NOT_CALIBRATED
    confidence_interval_95: Optional[List[float]] = None


class RecommendationAction(str, Enum):
    NONE = "NONE"
    REQUEST_MORE_DATA = "REQUEST_MORE_DATA"
    FLAG = "FLAG"
    BLOCK_RECOMMENDATION = "BLOCK_RECOMMENDATION"
    PROPOSE_RESEARCH = "PROPOSE_RESEARCH"


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: RecommendationAction
    rationale: str


class UniversalAgentOutput(BaseModel):
    """The canonical output payload for all 100 specialist roles."""
    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(..., pattern=r"^G(0[1-9]|1[0-5])-R(0[1-9]|1[0-5])$")
    agent_version: str = "1.0.0"
    task_id: str
    status: AgentStatus
    started_at_utc: str
    completed_at_utc: str
    input_event_ids: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    uncertainty: Uncertainty
    recommendation: Recommendation
    metrics: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    model_runtime_id: Optional[str] = None
    model_id: Optional[str] = None
    prompt_version: str = "1.0.0"
    code_commit: str = "git-head"
