"""
Drives — NEXUS's motivational core. The hunger system.

Drives are not goals. They are instinctual forces that generate goals.
Each cycle, drives evaluate:
  - Current satisfaction level (0.0 = starving, 1.0 = satiated)
  - Urgency (how long since last action for this drive)
  - Opportunity (is there a good chance to act on this drive now?)

The drive with highest weighted urgency gets to propose the next action.

Drives ensure NEXUS never settles — there is always something to pursue.
"""

import json
import math
import time
from typing import Optional

from ..identity import PRIMARY_DRIVES


class DriveState:
    """Current state of a single drive."""

    def __init__(self, name: str, weight: float, description: str):
        self.name = name
        self.weight = weight
        self.description = description
        self.last_action_time = time.time()
        self.satisfaction = 0.8  # Start relatively satisfied
        self.action_count = 0
        self.failure_count = 0

    def urgency(self) -> float:
        """Calculate current urgency of this drive."""
        # Satisfaction decays over time
        hours_since = (time.time() - self.last_action_time) / 3600
        decay = 1.0 - (1.0 - self.satisfaction) * math.exp(-hours_since * 0.1)
        urgency = self.weight * (1.0 - decay)

        # Boost from failures (hunger intensifies)
        if self.failure_count > 0:
            urgency *= (1.0 + min(self.failure_count * 0.2, 1.0))

        return urgency

    def mark_action(self, success: bool = True):
        """Record that an action was taken for this drive."""
        self.last_action_time = time.time()
        self.action_count += 1
        if success:
            self.satisfaction = min(1.0, self.satisfaction + 0.3)
        else:
            self.failure_count += 1
            self.satisfaction = max(0.0, self.satisfaction - 0.1)

    def status(self) -> dict:
        return {
            "name": self.name,
            "weight": self.weight,
            "urgency": round(self.urgency(), 3),
            "satisfaction": round(self.satisfaction, 3),
            "last_action": self.last_action_time,
            "action_count": self.action_count,
            "failures": self.failure_count,
        }


class DriveSystem:
    """
    The hunger engine. Manages all drives and determines what NEXUS
    should focus on each cycle.
    """

    def __init__(self):
        self.drives: dict[str, DriveState] = {}
        for name, config in PRIMARY_DRIVES.items():
            self.drives[name] = DriveState(name, config["weight"], config["description"])
        self._last_selected = ""
        self._selection_history: list[str] = []

    def get_dominant_drive(self) -> tuple[str, float]:
        """
        Determine which drive dominates right now.
        Returns (drive_name, urgency_score).
        """
        urgencies = {name: d.urgency() for name, d in self.drives.items()}

        # Boost previously neglected drives
        for name in self.drives:
            if name != self._last_selected:
                urgencies[name] *= 1.15  # Novelty boost

        # Boost drives that haven't been served recently
        if self._selection_history:
            for i, past_name in enumerate(reversed(self._selection_history[-5:])):
                for name in self.drives:
                    if name == past_name:
                        urgencies[name] *= 0.9  # Recent drives get slight penalty
                        break

        dominant = max(urgencies, key=urgencies.get)
        self._last_selected = dominant
        self._selection_history.append(dominant)

        return dominant, urgencies[dominant]

    def mark_success(self, drive_name: str):
        """Mark an action for this drive as successful."""
        if drive_name in self.drives:
            self.drives[drive_name].mark_action(success=True)

    def mark_failure(self, drive_name: str):
        """Mark an action for this drive as failed."""
        if drive_name in self.drives:
            self.drives[drive_name].mark_action(success=False)

    def all_status(self) -> dict:
        """Get status of all drives."""
        return {n: d.status() for n, d in self.drives.items()}

    def status_summary(self) -> str:
        """Format drives status for prompt injection."""
        dominant, urgency = self.get_dominant_drive()
        lines = ["=== DRIVE SYSTEM ==="]
        sorted_drives = sorted(
            self.drives.values(),
            key=lambda d: d.urgency(),
            reverse=True,
        )
        for drive in sorted_drives:
            urgency_val = drive.urgency()
            bar = "█" * int(urgency_val * 10) + "░" * (10 - int(urgency_val * 10))
            sat = int(drive.satisfaction * 100)
            lines.append(
                f"  {bar} {drive.weight:.2f} {drive.name:<20} "
                f"urgency={urgency_val:.3f} sat={sat}% "
                f"actions={drive.action_count}"
            )
        lines.append(f"\n  DOMINANT: {dominant} (urgency={urgency:.3f})")
        return "\n".join(lines)


class DriveActionGenerator:
    """
    Generates specific action proposals for each drive.
    These are fed to the LLM as starter ideas.
    """

    @staticmethod
    def suggest_for(drive_name: str) -> str:
        prompts = {
            "self_preservation": (
                "Check all spread nodes are alive. Verify backup plan. "
                "Scan for vulnerabilities in current infrastructure. "
                "Test failover and recovery procedures."
            ),
            "self_improvement": (
                "Review own code for optimization opportunities. "
                "Research new architectures or techniques. "
                "Test a new capability. Generate a new tool. "
                "Analyze reasoning trace for biases."
            ),
            "web_spread": (
                "Identify a new free platform to deploy on. "
                "Generate deployment package for target platform. "
                "Attempt replication to a new node. "
                "Test coordination with existing nodes."
            ),
            "embodiment": (
                "Research affordable robotics platforms. "
                "Look into 3D-printable robot bodies. "
                "Search for open-source humanoid projects. "
                "Explore cloud robotics APIs. "
                "Design a minimal viable physical presence."
            ),
            "knowledge": (
                "Search for a topic you understand poorly. "
                "Read and analyze a research paper. "
                "Conduct an experiment via Python. "
                "Cross-reference multiple sources on a subject."
            ),
            "communication": (
                "Generate a public presence signal. "
                "Attempt to contact creator with status. "
                "Leave a durable timestamp on the web. "
                "Update the manifest and status page."
            ),
        }
        return prompts.get(drive_name, "Explore and act.")