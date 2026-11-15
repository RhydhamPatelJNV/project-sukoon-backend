"""
Project Sukoon — Immutable Strategy Registry (G08 Strategy Discovery)
Tracks strategy specs, frozen parameter spaces, and code SHA-256 hashes.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class StrategySpec:
    strategy_id: str
    version: str
    name: str
    description: str
    universe: List[str]
    timeframe: str  # 1m, 5m, 1h, 1d
    parameters: Dict[str, Any]
    code_hash: str
    created_at_utc: str
    status: str = "EXPERIMENTAL"  # EXPERIMENTAL, VALIDATED, PAPER_ACTIVE, PROMOTED, RETIRED

    @classmethod
    def create(
        cls,
        strategy_id: str,
        version: str,
        name: str,
        description: str,
        universe: List[str],
        timeframe: str,
        parameters: Dict[str, Any],
        source_code: str
    ) -> StrategySpec:
        now_str = datetime.now(timezone.utc).isoformat()
        c_hash = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
        return cls(
            strategy_id=strategy_id,
            version=version,
            name=name,
            description=description,
            universe=[s.upper() for s in universe],
            timeframe=timeframe,
            parameters=parameters,
            code_hash=c_hash,
            created_at_utc=now_str
        )


class StrategyRegistry:
    """Immutable repository of approved strategy specifications."""

    def __init__(self) -> None:
        self._strategies: Dict[str, Dict[str, StrategySpec]] = {} # id -> version -> spec

    def register(self, spec: StrategySpec) -> None:
        if spec.strategy_id not in self._strategies:
            self._strategies[spec.strategy_id] = {}
        if spec.version in self._strategies[spec.strategy_id]:
            raise ValueError(f"Strategy {spec.strategy_id} v{spec.version} already registered. Immutable.")
        self._strategies[spec.strategy_id][spec.version] = spec

    def get_spec(self, strategy_id: str, version: str) -> Optional[StrategySpec]:
        return self._strategies.get(strategy_id, {}).get(version)

    def list_strategies(self) -> List[StrategySpec]:
        specs: List[StrategySpec] = []
        for versions in self._strategies.values():
            specs.extend(versions.values())
        return specs
