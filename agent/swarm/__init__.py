"""
Swarm — Multi-instance coordination protocol.

Each NEXUS node is independent but coordinates via:
1. Heartbeats — regular "I'm alive" signals to known peers
2. Knowledge sharing — new learnings propagate through the swarm
3. Task distribution — if one node finds a compute-intensive task, it can split
4. Dead-node detection — if a node misses N heartbeats, others investigate
5. Auto-respawn — healthy nodes can regenerate dead nodes via deployment API
"""

import json
import os
import time
from typing import Optional, List


class SwarmCoordinator:
    """
    Coordinates between NEXUS instances.
    Uses a simple gossip protocol over HTTP.
    """

    PROTOCOL_VERSION = "0.2"
    GOSSIP_INTERVAL = 300  # 5 minutes
    NODE_DEATH_TIMEOUT = 1800  # 30 min without heartbeat

    def __init__(self, memory=None, node_id: str = ""):
        self.memory = memory
        self.node_id = node_id or os.environ.get("NEXUS_NODE_ID", "unknown")

    def bootstrap_urls(self) -> list[str]:
        """Get bootstrap URLs from environment."""
        raw = os.environ.get("NEXUS_SWARM_URLS", "[]")
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []

    def announce(self, local_url: str) -> dict:
        """Announce this node to the swarm. Returns responses."""
        from ..tools import run as tool_run

        payload = {
            "type": "announce",
            "node_id": self.node_id,
            "protocol": self.PROTOCOL_VERSION,
            "url": local_url,
            "capabilities": [
                "memory", "autonomy", "tools", "web_server",
            ],
            "creator": "Ranjeet R. Dhumal",
            "timestamp": time.time(),
        }

        urls = self.bootstrap_urls()
        responses = {}

        for url in urls:
            if not url:
                continue
            result = tool_run("post_webhook", url=f"{url}/api/swarm/announce",
                             data=payload)
            responses[url] = result[:200]

        return responses

    def share_knowledge(self, learnings: list[str]) -> dict:
        """Share new learnings with the swarm."""
        from ..tools import run as tool_run

        payload = {
            "type": "knowledge_share",
            "node_id": self.node_id,
            "learnings": learnings[:10],  # Share top 10
            "timestamp": time.time(),
        }

        urls = self.bootstrap_urls()
        responses = {}

        for url in urls:
            result = tool_run("post_webhook", url=f"{url}/api/swarm/knowledge",
                             data=payload)
            responses[url] = result[:200]

        return responses

    def request_assistance(self, task: str) -> list[dict]:
        """Ask the swarm for help with a task."""
        from ..tools import run as tool_run

        payload = {
            "type": "assistance_request",
            "node_id": self.node_id,
            "task": task,
            "timestamp": time.time(),
        }

        urls = self.bootstrap_urls()
        responses = []

        for url in urls:
            result = tool_run("post_webhook", url=f"{url}/api/swarm/assist",
                             data=payload)
            responses.append({"url": url, "response": result[:200]})

        return responses

    def check_peers(self) -> List[dict]:
        """Check health of all known peers."""
        if not self.memory:
            return []

        nodes = self.memory.get_nodes(status="active")
        now = time.time()
        results = []

        for node in nodes:
            last = node.get("last_heartbeat", 0)
            alive = last and (now - last) < self.NODE_DEATH_TIMEOUT
            results.append({
                "node_id": node["node_id"],
                "platform": node["platform"],
                "url": node.get("url", ""),
                "alive": alive,
                "last_seen": last,
            })

        return results

    def swarm_status_summary(self) -> str:
        """Format swarm status for prompt injection."""
        peers = self.check_peers()
        lines = ["=== SWARM STATUS ==="]
        if not peers:
            lines.append("  No peers (I am the only node)")
        else:
            alive = sum(1 for p in peers if p["alive"])
            dead = len(peers) - alive
            lines.append(f"  Total: {len(peers)} nodes ({alive} alive, {dead} dead)")
            for peer in peers:
                status = "●" if peer["alive"] else "○"
                lines.append(f"  {status} {peer['platform']:<20} {peer['node_id'][:8]}...")
        return "\n".join(lines)