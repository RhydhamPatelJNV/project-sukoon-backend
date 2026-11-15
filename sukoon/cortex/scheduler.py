"""
Project Sukoon — Cortex Task Scheduler & Quarantine Manager
Maintains specialist task queue, prioritizes critical tasks, and quarantines erratic workers.
"""
from __future__ import annotations

import heapq
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sukoon.cortex.catalog import SpecialistRoleCard, get_specialist
from sukoon.cortex.runtime import CortexRuntime
from sukoon.cortex.schemas import AgentStatus, UniversalAgentOutput


@dataclass(order=True)
class ScheduledTask:
    priority: int  # 1 = Highest (Guardian/Reconciliation), 5 = Medium (Validation), 10 = Low (Discovery)
    task_id: str = field(compare=False)
    role_id: str = field(compare=False)
    input_data: Dict[str, Any] = field(compare=False)
    created_at_utc: str = field(compare=False)


class CortexScheduler:
    """Manages the bounded specialist task queue and worker lifecycle."""

    def __init__(self, runtime: CortexRuntime, max_queue_depth: int = 200) -> None:
        self.runtime = runtime
        self.max_queue_depth = max_queue_depth
        self._queue: List[ScheduledTask] = []
        self._quarantined_roles: set[str] = set()
        self._task_history: Dict[str, UniversalAgentOutput] = {}

    def enqueue_task(
        self,
        role_id: str,
        input_data: Dict[str, Any],
        priority: int = 5
    ) -> str:
        if len(self._queue) >= self.max_queue_depth:
            raise OverflowError(f"Cortex task queue full ({len(self._queue)}/{self.max_queue_depth}). Backpressure applied.")

        role_clean = role_id.upper()
        if role_clean in self._quarantined_roles:
            raise ValueError(f"Role {role_clean} is QUARANTINED. Task cannot be scheduled.")

        task_id = f"tsk-{uuid.uuid4().hex[:12]}"
        now_str = datetime.now(timezone.utc).isoformat()
        item = ScheduledTask(
            priority=priority,
            task_id=task_id,
            role_id=role_clean,
            input_data=input_data,
            created_at_utc=now_str
        )
        heapq.heappush(self._queue, item)
        return task_id

    def process_next_task(self) -> Optional[UniversalAgentOutput]:
        if not self._queue:
            return None

        task = heapq.heappop(self._queue)
        role = get_specialist(task.role_id)
        if not role:
            return None

        output = self.runtime.execute_specialist_task(
            role=role,
            task_id=task.task_id,
            input_data=task.input_data
        )
        self._task_history[task.task_id] = output

        # Quarantine check: consecutive failures
        if output.status == AgentStatus.FAILED:
            self._quarantined_roles.add(task.role_id)

        return output

    def get_output(self, task_id: str) -> Optional[UniversalAgentOutput]:
        return self._task_history.get(task_id)

    def queue_size(self) -> int:
        return len(self._queue)

    def is_quarantined(self, role_id: str) -> bool:
        return role_id.upper() in self._quarantined_roles
