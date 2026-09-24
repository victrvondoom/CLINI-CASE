"""Contract tests for keyword_filter DeterministicSubAgent."""
from __future__ import annotations

from app.agents.policy_retriever.schemas import KeywordFilterInput
from app.agents.policy_retriever.sub_agents.keyword_filter import keyword_filter


def test_finds_aetna_trastuzumab():
    out = keyword_filter._execute(  # noqa: SLF001
        KeywordFilterInput(payer_id="aetna", treatment_name="trastuzumab")
    )
    assert len(out.candidates) > 0
    assert all(c.payer_id == "aetna" for c in out.candidates)
    assert any("trastuzumab" in c.policy_title.lower() for c in out.candidates)


def test_cross_payer_pembrolizumab_all_4_payers():
    """All 4 payers should have pembrolizumab coverage in our 22-policy corpus."""
    found_payers = set()
    for payer in ["aetna", "uhc", "bcbs", "anthem"]:
        out = keyword_filter._execute(  # noqa: SLF001
            KeywordFilterInput(payer_id=payer, treatment_name="pembrolizumab")
        )
        if out.candidates:
            found_payers.add(payer)
    assert found_payers == {"aetna", "uhc", "bcbs", "anthem"}


def test_returns_empty_for_unknown_treatment():
    out = keyword_filter._execute(  # noqa: SLF001
        KeywordFilterInput(payer_id="aetna", treatment_name="some-fictional-drug-xyz999")
    )
    assert out.candidates == []


def test_candidates_have_full_metadata():
    out = keyword_filter._execute(  # noqa: SLF001
        KeywordFilterInput(payer_id="aetna", treatment_name="trastuzumab")
    )
    c = out.candidates[0]
    assert c.policy_id
    assert c.payer_id == "aetna"
    assert c.policy_title
    assert c.section_heading
    assert c.section_text
