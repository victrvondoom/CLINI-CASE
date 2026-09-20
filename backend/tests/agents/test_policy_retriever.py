"""Contract tests for the Policy Retriever agent."""
from __future__ import annotations

from app.agents.policy_retriever import _candidate_sections


def test_filters_aetna_trastuzumab():
    """Demo path: aetna + trastuzumab returns initial + continuation + exclusions."""
    cands = _candidate_sections("aetna", "trastuzumab")
    assert len(cands) >= 2, f"Expected >=2 sections for aetna trastuzumab, got {len(cands)}"
    titles = {c["section"]["heading"] for c in cands}
    assert "Initial Authorization Criteria" in titles


def test_filters_uhc_osimertinib():
    cands = _candidate_sections("uhc", "osimertinib")
    assert len(cands) >= 1
    assert all(c["policy"]["payer_id"] == "uhc" for c in cands)


def test_returns_empty_for_unknown_treatment():
    cands = _candidate_sections("aetna", "imaginarydrugXYZ")
    assert cands == []


def test_returns_empty_for_unknown_payer():
    cands = _candidate_sections("nonexistent_payer", "trastuzumab")
    assert cands == []


def test_keyword_match_handles_brand_name():
    """Brand name 'Herceptin' should also match the trastuzumab policy."""
    cands = _candidate_sections("aetna", "Herceptin")
    assert len(cands) >= 1
