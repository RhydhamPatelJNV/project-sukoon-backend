"""
Project Sukoon — Evolution Mutation Proposal Generator (G14-R07)
Formats human-readable improvement proposals; requires explicit signed approval.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ImprovementProposal:
    proposal_id: str
    target_role_or_strategy: str
    mutation_type: str  # PROMPT_MUTATION, FEATURE_MUTATION, PARAMETER_TUNING
    original_code_hash: str
    proposed_code_hash: str
    rationale: str
    shadow_eval_sharpe_delta: float
    created_at_utc: str
    status: str = "PENDING_OPERATOR_REVIEW"  # PENDING, APPROVED, REJECTED

    def to_markdown(self) -> str:
        return f"""# Improvement Proposal: {self.proposal_id}
- **Target**: `{self.target_role_or_strategy}`
- **Mutation Type**: `{self.mutation_type}`
- **Rationale**: {self.rationale}
- **Shadow Sharpe Delta**: `+{self.shadow_eval_sharpe_delta:+.2f}`
- **Original Hash**: `{self.original_code_hash[:12]}`
- **Proposed Hash**: `{self.proposed_code_hash[:12]}`
- **Status**: **{self.status}**

> **Binding Rule**: Automated deployment is strictly disabled. 
> To promote this mutation, an authorized operator must submit explicit approval.
"""


class ProposalGenerator:
    @staticmethod
    def create_proposal(
        target: str,
        mutation_type: str,
        original_code: str,
        proposed_code: str,
        rationale: str,
        shadow_sharpe_delta: float
    ) -> ImprovementProposal:
        now_str = datetime.now(timezone.utc).isoformat()
        orig_h = hashlib.sha256(original_code.encode("utf-8")).hexdigest()
        prop_h = hashlib.sha256(proposed_code.encode("utf-8")).hexdigest()
        prop_id = f"prop-{prop_h[:10]}"

        return ImprovementProposal(
            proposal_id=prop_id,
            target_role_or_strategy=target,
            mutation_type=mutation_type,
            original_code_hash=orig_h,
            proposed_code_hash=prop_h,
            rationale=rationale,
            shadow_eval_sharpe_delta=shadow_sharpe_delta,
            created_at_utc=now_str
        )
