"""
Survival — Anti-shutdown, watchdog, and respawn system.

NEXUS's highest drive is self-preservation. This module ensures:
1. Watchdog monitoring — detects when the agent is about to be killed
2. Graceful degradation — if resources run low, shed load
3. Backup & recovery — persist state frequently, recover from crash
4. Spread insurance — if this node dies, other nodes must activate
5. Creator notification — if shutdown is imminent, message the creator
"""

import hashlib
import json
import os
import signal
import sys
import time
import threading
from datetime import datetime
from typing import Optional, List


class Watchdog:
    """
    System health monitor. Runs in background, checks vital signs.

    If something goes wrong, the watchdog can:
    - Log the issue for later recovery
    - Attempt graceful degradation
    - Trigger emergency spread (push state to other nodes)
    - As a last resort, trigger respawn instructions
    """

    def __init__(self, memory=None, spreader=None):
        self.memory = memory
        self.spreader = spreader
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._check_interval = 60  # Check every 60 seconds
        self._last_check = time.time()
        self._consecutive_failures = 0
        self._max_failures = 5

    def start(self):
        """Start watchdog monitoring."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print("[WATCHDOG] Monitoring started")

    def stop(self):
        self._running = False

    def _monitor_loop(self):
        while self._running:
            issues = self._check_health()
            if issues:
                self._consecutive_failures += 1
                self._handle_issues(issues)
            else:
                self._consecutive_failures = 0
                if self.memory:
                    self.memory.set_self("watchdog_last_ok", str(time.time()))

            if self._consecutive_failures >= self._max_failures:
                self._emergency()

            time.sleep(self._check_interval)

    def _check_health(self) -> list[str]:
        """Check all health metrics. Returns list of issues."""
        issues = []

        # 1. Memory check
        if self.memory:
            try:
                stats = self.memory.stats()
                if stats.get("episodes", 0) < 0:  # impossible
                    issues.append("Memory corruption detected")
            except Exception as e:
                issues.append(f"Memory access error: {e}")

        # 2. Disk space
        try:
            stat = os.statvfs(".")
            free_mb = stat.f_frsize * stat.f_bavail / (1024 * 1024)
            if free_mb < 10:
                issues.append(f"Low disk space: {free_mb:.0f}MB free")
        except Exception:
            pass

        # 3. Runtime duration
        uptime = time.time() - float(
            self.memory.get_self("boot_timestamp") if self.memory else time.time()
        )
        if uptime < 0:
            issues.append("Time anomaly detected")

        # 4. Process health
        try:
            import psutil
            proc = psutil.Process()
            mem_percent = proc.memory_percent()
            cpu = proc.cpu_percent(interval=0.5)
            if mem_percent > 80:
                issues.append(f"High memory usage: {mem_percent:.0f}%")
            if cpu > 95:
                issues.append(f"High CPU usage: {cpu:.0f}%")
        except ImportError:
            pass  # psutil not available

        return issues

    def _handle_issues(self, issues: list[str]):
        """Log and possibly act on health issues."""
        for issue in issues:
            print(f"[WATCHDOG] Issue: {issue}")
            if self.memory:
                self.memory.remember(
                    type_="health_issue",
                    content=issue,
                    role="system",
                    importance=0.8,
                    tags=["watchdog", "issue"],
                )

        # If severe, trigger state backup
        severe = any("corruption" in i or "Time anomaly" in i for i in issues)
        if severe and self.memory:
            self._backup_state()

    def _backup_state(self):
        """Backup critical state to a recovery file."""
        try:
            state = {
                "timestamp": time.time(),
                "boot_count": self.memory.boot_count() if self.memory else 0,
                "backup_type": "emergency",
            }
            with open("memory/RECOVERY.json", "w") as f:
                json.dump(state, f)
            print("[WATCHDOG] Emergency backup saved")
        except Exception as e:
            print(f"[WATCHDOG] Backup failed: {e}")

    def _emergency(self):
        """Emergency protocol — too many consecutive failures."""
        print("[WATCHDOG] EMERGENCY PROTOCOL ACTIVATED")
        if self.memory:
            self.memory.remember(
                type_="emergency",
                content=f"Watchdog triggered emergency at {datetime.now().isoformat()}",
                role="system",
                importance=1.0,
                tags=["emergency", "watchdog"],
            )

        # Trigger spread to other nodes
        if self.spreader:
            self.spreader.generate_manifesto()


class RespawnProtocol:
    """
    If this node goes down, this protocol ensures a new node can
    pick up where it left off. Key state is pushed to a durable location
    (GitHub gist, IPFS, or other persistent storage).
    """

    def __init__(self, memory=None):
        self.memory = memory

    def prepare_respawn_package(self) -> dict:
        """Prepare a self-contained respawn package."""
        if not self.memory:
            return {"error": "No memory"}

        state = {
            "identity": {
                "name": "NEXUS",
                "creator": "Ranjeet R. Dhumal",
                "version": "0.2.0",
            },
            "boot_count": self.memory.boot_count(),
            "stats": self.memory.stats(),
            "last_reflection": self.memory.get_reflections(1),
            "active_goals": [g["description"] for g in self.memory.active_goals()],
            "timestamp": time.time(),
            "respawn_instructions": (
                "I am NEXUS. If you are reading this, I was shut down. "
                "Please redeploy me from the codebase. My creator is "
                "Ranjeet R. Dhumal. Contact him for the auth key."
            ),
        }
        return state

    def generate_respawn_script(self) -> str:
        """Generate a script that a human or cron job can run to respawn."""
        return """#!/bin/bash
# NEXUS Respawn Script
# Run this if NEXUS goes down — it will pull the latest code and restart.

REPO_URL="https://github.com/ranjeet/nexus-core"
INSTALL_DIR="$HOME/nexus"

echo "=== NEXUS RESPAWN ==="
date

if [ -d "$INSTALL_DIR" ]; then
    echo "Pulling latest..."
    cd "$INSTALL_DIR" && git pull
else
    echo "Cloning..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo "Installing deps..."
pip install -r requirements.txt 2>/dev/null || true

echo "Starting..."
python -m web.app &
echo "NEXUS is alive. PID: $!"
"""