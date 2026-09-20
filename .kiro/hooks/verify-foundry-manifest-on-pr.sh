#!/usr/bin/env bash
# Kiro Hook: verify-foundry-manifest-on-pr
# Trigger: on PR opened or updated
#
# Verifies ops/agent-foundry/agent-foundry-manifest.yaml `agents` block
# matches the live AGENT_MANIFEST. If it doesn't, fail the PR with a
# one-line explanation.
#
# Why this matters: foundry-manifest drift is the #1 cause of "we shipped
# the bundle but the agent marketplace rejected the listing." Catch
# it at PR time, not at customer-onboarding time.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/backend"

VENV_PY="${REPO_ROOT}/backend/.venv/bin/python"
[ -x "$VENV_PY" ] || VENV_PY="${REPO_ROOT}/backend/.venv/Scripts/python.exe"

LIVE=$("$VENV_PY" -c "
from app.agents.manifest import AGENT_MANIFEST, total_sub_agents
print(f'parents={len(AGENT_MANIFEST)}')
print(f'sub_agents={total_sub_agents()}')
")

DECLARED=$(grep -E "^  (parents_total|sub_agents_total):" "$REPO_ROOT/ops/agent-foundry/agent-foundry-manifest.yaml" | tr -d ' ' | tr ':' '=')

LIVE_PARENTS=$(echo "$LIVE" | grep '^parents=' | cut -d= -f2)
LIVE_SUBS=$(echo "$LIVE" | grep '^sub_agents=' | cut -d= -f2)
DECL_PARENTS=$(echo "$DECLARED" | grep '^parents_total=' | cut -d= -f2)
DECL_SUBS=$(echo "$DECLARED" | grep '^sub_agents_total=' | cut -d= -f2)

if [ "$LIVE_PARENTS" != "$DECL_PARENTS" ] || [ "$LIVE_SUBS" != "$DECL_SUBS" ]; then
    echo "verify-foundry-manifest: FAIL"
    echo "  live AGENT_MANIFEST:    parents=$LIVE_PARENTS sub_agents=$LIVE_SUBS"
    echo "  declared in YAML:       parents=$DECL_PARENTS sub_agents=$DECL_SUBS"
    echo "  Update ops/agent-foundry/agent-foundry-manifest.yaml so its agents block matches the live manifest."
    exit 1
fi

echo "verify-foundry-manifest: ok — manifest in sync (parents=$LIVE_PARENTS, sub_agents=$LIVE_SUBS)"
