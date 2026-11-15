"""
Project Sukoon — Master Market Judge Arbitrator (G07 Master Market Judge)
Synthesizes cross-disciplinary evidence, preserves dissent, and honors "No-Trade".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
from sukoon.cortex.schemas import (
    Finding,
    FindingSeverity,
    RecommendationAction,
    UniversalAgentOutput,
)


@dataclass(frozen=True)
class ArbitrationSynthesis:
    strategy_id: str
    symbol: str
    decision: str  # PROCEED, VETO_DISAGREEMENT, NO_TRADE, REQUEST_DATA
    consensus_score: float  # -1.0 (Strong Sell) to +1.0 (Strong Buy)
    critical_dissent_found: bool
    dissenting_claims: List[str]
    participating_specialists: int


class MasterMarketJudgeArbitrator:
    """Arbitrates specialist outputs. Preserves dissent; never suppresses minority warnings."""

    @staticmethod
    def arbitrate(
        strategy_id: str,
        symbol: str,
        specialist_reports: List[UniversalAgentOutput]
    ) -> ArbitrationSynthesis:
        if not specialist_reports:
            return ArbitrationSynthesis(
                strategy_id=strategy_id,
                symbol=symbol,
                decision="NO_TRADE",
                consensus_score=0.0,
                critical_dissent_found=False,
                dissenting_claims=["No specialist reports provided"],
                participating_specialists=0
            )

        critical_dissent: List[str] = []
        block_actions: int = 0
        research_actions: int = 0

        for r in specialist_reports:
            if r.recommendation.action == RecommendationAction.BLOCK_RECOMMENDATION:
                block_actions += 1
                critical_dissent.append(f"{r.agent_id}: {r.recommendation.rationale}")

            for f in r.findings:
                if f.severity == FindingSeverity.CRITICAL:
                    critical_dissent.append(f"{r.agent_id} CRITICAL: {f.claim}")

        has_critical_dissent = len(critical_dissent) > 0

        # Non-negotiable rule: Any unresolved critical objection forces NO_TRADE / VETO
        if has_critical_dissent:
            decision = "VETO_DISAGREEMENT"
        elif block_actions > 0:
            decision = "NO_TRADE"
        else:
            decision = "PROCEED"

        return ArbitrationSynthesis(
            strategy_id=strategy_id,
            symbol=symbol,
            decision=decision,
            consensus_score=0.85 if decision == "PROCEED" else -1.0,
            critical_dissent_found=has_critical_dissent,
            dissenting_claims=critical_dissent,
            participating_specialists=len(specialist_reports)
        )
