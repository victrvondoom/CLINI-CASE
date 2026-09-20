#!/usr/bin/env bash
# Kiro Hook: architecture-boundary-check
# Trigger: on file save in backend/app/**.py
#
# Enforces the 5-layer module boundaries from ops/architecture/TARGET_ARCHITECTURE.md:
#   1. app/api/* MUST NOT import from app/llm/* directly (must go via Gateway).
#   2. app/agents/* MUST NOT import from app/api/* (no circular orchestration).
#   3. Only app/llm/gateway.py + app/llm/factory.py may call BedrockClient directly.
#   4. app/integrations/trizetto/** MUST NOT import from app/agents/**.
#
# Surfaces violations in Kiro's diagnostics panel BEFORE the file is committed.
set -euo pipefail

SAVED_FILE="${KIRO_SAVED_FILE:-}"
case "$SAVED_FILE" in
    *backend/app/*.py) ;;
    *)
        exit 0
        ;;
esac

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

violations=()

# Rule 1: api → llm.* must go through factory's get_llm_client (which returns Gateway-wrapped)
if grep -rEn "from app\.llm\.(bedrock_client|anthropic_client|openrouter_client) import" backend/app/api/ 2>/dev/null; then
    violations+=("api → direct llm provider import (must use get_llm_client() / Gateway)")
fi

# Rule 2: agents must not import api
if grep -rEn "from app\.api" backend/app/agents/ 2>/dev/null; then
    violations+=("agents → app.api import (would create circular orchestration)")
fi

# Rule 3: Only gateway.py + factory.py may import the raw BedrockClient
forbidden=$(grep -rEln "from app\.llm\.bedrock_client" backend/app/ 2>/dev/null \
            | grep -vE "(app/llm/gateway\.py|app/llm/factory\.py|app/llm/__init__\.py)$" || true)
if [ -n "$forbidden" ]; then
    violations+=("BedrockClient imported outside gateway.py / factory.py: $forbidden")
fi

# Rule 4: trizetto integrations must not import from agents
if grep -rEn "from app\.agents" backend/app/integrations/trizetto/ 2>/dev/null; then
    violations+=("integrations/trizetto → app.agents import (couples integration to agent internals)")
fi

if [ ${#violations[@]} -gt 0 ]; then
    echo "architecture-boundary-check: FAIL"
    for v in "${violations[@]}"; do
        echo "  - $v"
    done
    exit 1
fi

echo "architecture-boundary-check: ok"
