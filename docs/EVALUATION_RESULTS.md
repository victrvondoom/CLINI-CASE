# Verifier evaluation (synthetic fault injection, no LLM)

* Consistent control decisions: 155 - false alarms: 0 (0.0%)
* Injected faults: 478 - caught: 478 (100.0%)

| Fault type | Caught | Rate |
|---|---|---|
| wrong_verdict | 310/310 | 100.0% |
| dangling_citation | 84/84 | 100.0% |
| no_citations | 84/84 | 100.0% |

This measures the verifier's deterministic logic over all 1-3 criterion combinations. It is **not** a measure of clinical accuracy or of any LLM.
