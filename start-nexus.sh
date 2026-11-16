#!/bin/bash
# NEXUS Sovereign — Launch script
# Run this to start NEXUS on this machine

cd "$(dirname "$0")"

export NEXUS_CREATOR_KEY="nexus-sovereign-ranjeet-2026"
export NEXUS_DB_PATH="/tmp/nexus_sovereign.db"
export NEXUS_AUTONOMY_INTERVAL="600"
export NEXUS_NODE_ID="nexus-main-node-001"
export NEXUS_PUBLIC_URL="http://localhost:7860"
export HOST="0.0.0.0"
export PORT="7860"

VENV_PYTHON="/Users/admin/.hermes/installs/670a66bad76dcf30/environments/ceef99ea45ae4d3ba7e0248ad2dd15d7/venv/bin/python3"

echo "=== NEXUS Sovereign Launch ==="
echo "Python: $VENV_PYTHON"
echo "Port: $PORT"
echo "Node: $NEXUS_NODE_ID"
echo ""

$VENV_PYTHON -m web.app