#!/usr/bin/env bash
# Kiro Hook: regenerate-specs-on-save
# Trigger: on file save in backend/app/agents/**
#
# Re-emits .kiro/specs/<agent>/{requirements,design,tasks}.md from the
# live AGENT_MANIFEST. Guarantees the spec library mirrors the source code
# at every commit; no manual sync.
set -euo pipefail

# Only run when the saved file is in the agents subtree
SAVED_FILE="${KIRO_SAVED_FILE:-}"
case "$SAVED_FILE" in
    *backend/app/agents/*) ;;
    *)
        echo "regenerate-specs: skipped (saved file outside agents subtree)"
        exit 0
        ;;
esac

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/backend"

VENV_PY="${REPO_ROOT}/backend/.venv/bin/python"
[ -x "$VENV_PY" ] || VENV_PY="${REPO_ROOT}/backend/.venv/Scripts/python.exe"

if [ ! -x "$VENV_PY" ]; then
    echo "regenerate-specs: ERROR — backend venv not found at .venv/bin/python or .venv/Scripts/python.exe"
    exit 1
fi

"$VENV_PY" -m app.integrations.kiro.exporter
echo "regenerate-specs: ok — .kiro/specs/ updated from AGENT_MANIFEST"
