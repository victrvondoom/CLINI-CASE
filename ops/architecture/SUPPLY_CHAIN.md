# ClinCase — Software Supply Chain Security

**Status:** Accepted (round-11)
**Audience:** Customer security team · FedRAMP authorizing official · HHS attestation auditor

## Why this matters

Modern enterprise + government procurement requires **provenance** for every binary you ship:

- **FedRAMP** — SP 800-218 SSDF (Secure Software Development Framework) is mandatory for agency authorizations
- **HHS attestation** — increasingly references SLSA / Sigstore / SBOM in vendor scoring rubrics
- **EO 14028** — *Improving the Nation's Cybersecurity* — requires SBOMs from federal contractors
- **CMS** — moving toward SBOM requirements for healthcare IT vendors per the [SBOM playbook](https://www.cisa.gov/sbom)

Round-9 build had: `docker build`, `docker push`, deploy. No provenance. **An attacker who compromises GitHub Actions could ship a backdoored image and we'd have no way to detect it.**

## Decision

Three layers of supply-chain security, all wired into CI:

| Layer | Tool | Output |
|---|---|---|
| **SBOM** | [Syft](https://github.com/anchore/syft) | `sbom-backend.cdx.json` (CycloneDX 1.6) + SPDX 2.3 |
| **Image signing** | [Sigstore cosign](https://www.sigstore.dev/) | OCI signature stored alongside image, keyless OIDC |
| **In-toto SBOM attestation** | cosign attest | SBOM cryptographically bound to the image digest |

## What this proves

A customer's deploy-time policy can require:
1. The image must have a Sigstore signature signed by GitHub Actions OIDC for `victrvondoom/CLINI-CASE` repo
2. The image must have an attached CycloneDX SBOM
3. The SBOM must not contain any package with a CVE > 7.0

If any of these fail, deploy is rejected. Argo CD + Kyverno or [policy-controller](https://docs.sigstore.dev/policy-controller/overview/) enforce this.

## Wire path

```
git push → GitHub Actions → docker build → docker push → ghcr.io
                                       │
                                       ├──► syft → SBOM (CycloneDX)
                                       │
                                       ├──► cosign sign --keyless (GitHub OIDC)
                                       │      → OCI registry
                                       │
                                       └──► cosign attest --predicate SBOM
                                              → in-toto attestation in registry

cluster: kyverno policy verifies cosign signature + SBOM presence before pod admission
```

## Files

| Where | What |
|---|---|
| `Makefile` (round 11) | `make sbom`, `make sign`, `make supply-chain` targets |
| `.github/workflows/supply-chain.yml` | CI workflow: build → SBOM → sign → attest → release |
| (post-pilot) `ops/k8s/policies/cosign-policy.yaml` | Kyverno policy enforcing signature presence at admission |

## SLSA level achieved (with this work)

- **SLSA 2** — provenance generated automatically (✅ achieved by GitHub Actions OIDC)
- **SLSA 3** — built on a hardened build platform with signed provenance (✅ — GitHub OIDC + Sigstore)
- **SLSA 4** — requires hermetic, reproducible builds (⏳ deferred — ClinCase Python deps don't currently lock-pin transitive deps)

## What's deferred to post-pilot

- ⏳ **Reproducible builds** — would require pinning every transitive dep + locking the build environment.
- ⏳ **Vulnerability scanning gate in CI** — Trivy / Snyk integration (1-day work)
- ⏳ **Kyverno admission policy** — drops in once `cosign-policy.yaml` is in the customer's cluster
- ⏳ **GUAC integration** — for fleet-wide SBOM querying (post-multi-customer pilot)

Each is a stated trigger.

## Sources

- SLSA — https://slsa.dev/
- Sigstore docs — https://docs.sigstore.dev/
- CycloneDX — https://cyclonedx.org/
- Syft — https://github.com/anchore/syft
- CISA SBOM — https://www.cisa.gov/sbom
- EO 14028 — https://www.whitehouse.gov/briefing-room/presidential-actions/2021/05/12/executive-order-on-improving-the-nations-cybersecurity/
