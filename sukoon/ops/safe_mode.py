"""
Project Sukoon — Incident Classifier & Safe Mode Manager (SUK-OPS-0001)
Classifies P0/P1/P2 incidents and orchestrates automatic safe mode entry.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional
from sukoon.guardian.kill_switch import KillSwitchController
from sukoon.ops.telegram import TelegramAlertDispatcher


class IncidentClass(str, Enum):
    P0 = "P0"  # Critical: Unauthorized order, Guardian bypass, credential leak
    P1 = "P1"  # Serious: Stale feed, broker disconnect, DB disk > 90%
    P2 = "P2"  # Warning: Specialist worker failure, non-critical degraded feed


class SafeModeManager:
    """Orchestrates fail-safe protection across the platform."""

    def __init__(
        self,
        kill_switch: KillSwitchController,
        alert_dispatcher: TelegramAlertDispatcher
    ) -> None:
        self.kill_switch = kill_switch
        self.alert_dispatcher = alert_dispatcher
        self.active_incidents: List[Dict[str, str]] = []

    def handle_incident(self, incident_class: IncidentClass, title: str, details: str) -> None:
        record = {
            "severity": incident_class.value,
            "title": title,
            "details": details
        }
        self.active_incidents.append(record)

        # Trigger immediate protective actions
        if incident_class == IncidentClass.P0:
            self.kill_switch.engage(f"P0 Critical Incident: {title}", triggered_by="SAFE_MODE_MANAGER")
            self.alert_dispatcher.dispatch(
                severity="P0_CRITICAL",
                title=f"🚨 P0 EMERGENCY: {title}",
                body=f"Trading entries halted immediately. Details: {details}"
            )
        elif incident_class == IncidentClass.P1:
            self.kill_switch.engage(f"P1 Infrastructure Alert: {title}", triggered_by="SAFE_MODE_MANAGER")
            self.alert_dispatcher.dispatch(
                severity="P1_ERROR",
                title=f"⚠️ P1 SAFE MODE: {title}",
                body=f"Strategies suspended. Reconciliation required. Details: {details}"
            )
        else:
            self.alert_dispatcher.dispatch(
                severity="P2_WARNING",
                title=f"ℹ️ P2 Warning: {title}",
                body=details
            )
