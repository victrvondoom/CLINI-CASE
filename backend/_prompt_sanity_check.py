"""One-off sanity check after the 2026-05-06 prompt-strengthening pass.

Run from the backend/ directory with the project venv:
  D:\\xzashr.ai Files\\clincase-workspace\\ClinCase\\backend\\.venv\\Scripts\\python.exe _prompt_sanity_check.py
"""
import pathlib
import sys
import traceback
from importlib import import_module

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PROMPTS = HERE / "app" / "prompts"


def main() -> int:
    rc = 0

    # 1. UTF-8 validate every prompt
    ok = bad = empty = 0
    for p in PROMPTS.rglob("*.txt"):
        try:
            text = p.read_text(encoding="utf-8")
            if not text.strip():
                print(f"EMPTY: {p.relative_to(PROMPTS)}")
                empty += 1
            else:
                ok += 1
        except UnicodeDecodeError as e:
            print(f"UTF8_ERR: {p.relative_to(PROMPTS)}: {e}")
            bad += 1
    print(f"\nprompts: utf8_ok={ok} empty={empty} utf8_bad={bad}")
    if bad or empty:
        rc = 1

    # 2. Import every agent module so prompt loaders fire
    agent_modules = [
        "app.agents.clinical_extractor",
        "app.agents.policy_retriever",
        "app.agents.necessity_reasoner",
        "app.agents.decision_composer",
        "app.agents.denial_forecaster",
        "app.agents.appeals_drafter",
        "app.agents.patient_communicator",
    ]
    imp_ok = imp_bad = 0
    for m in agent_modules:
        try:
            import_module(m)
            imp_ok += 1
        except Exception as e:
            print(f"IMPORT_ERR: {m}: {type(e).__name__}: {e}")
            traceback.print_exc()
            imp_bad += 1
    print(f"agent imports: ok={imp_ok}/{len(agent_modules)} bad={imp_bad}")
    if imp_bad:
        rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
