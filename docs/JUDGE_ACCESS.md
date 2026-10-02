# Judge access - CLINI-CASE (One Health Interoperability Gateway)

Status as of 2026-10-02. Facts below were checked against the repository and the GitHub API. Items marked **verify** or listed under "Terms the owner must confirm" are not established. This document grants no license and does not expand `LICENSE`; see [LICENSE_REVIEW.md](LICENSE_REVIEW.md).

## 1. Repository visibility

- `https://github.com/victrvondoom/CLINI-CASE` is **public** (GitHub API 2026-10-02: `private: false`, `visibility: public`).
- GitHub reports the license as `other` / `NOASSERTION`, because the repository uses a proprietary license, not an open-source one.
- Public visibility alone grants no license to the code (`LICENSE`: "Access to or public availability of the Software does not grant any license or other right").

## 2. Inspection and evaluation by hackathon judges

- The repository is public so that hackathon judges can read the source and documentation, as the hackathon's public-repository requirement contemplates (rules cited in `HACKATHON_BUILD_SCOPE.md`).
- Judges may inspect and evaluate the submission **under the applicable terms**. The applicable terms are the proprietary `LICENSE` plus any written authorization the owner supplies (section 7). The LICENSE text does not itself mention judges or evaluation, so this document does not assert additional rights beyond those terms.
- The requester reported on 2026-10-01 that rights-holder authorization exists. No signed agreement or judge-specific grant has been inspected in this repository.

## 3. Execution conditions

Running the software is **use/deployment** under the LICENSE and therefore depends on the authorization in section 7. Where permitted, these conditions apply:

- **Synthetic data only.** The Track 7 journey uses synthetic data. Do not load real patient data or personally identifiable information.
- **No secrets in the repository.** Credentials come from the environment. The demo account password is set by `DEMO_USER_PASSWORD` (no default), and the Track 7 launcher generates a private reviewer account. Do not commit or publish credentials you create.
- **Local only.** Run on your own machine. Do not host, expose publicly or redistribute a running instance.
- **No cloud required.** AWS/Bedrock are optional adapters; the reliable demo path does not need them. Live LLM suggestions only run if you configure a provider; they are not needed.
- **Network note.** The frontend `index.html` loads web fonts from Google Fonts (`fonts.googleapis.com`) at page load. Dependency installation (pip/npm/container images) downloads third-party packages.

How to run:

1. Windows quick start (SQLite, no database server): `./start-track7.ps1 -SQLite`, then open `/journey`.
2. Containers/Kubernetes: Docker image build and a local kind cluster, see [KUBERNETES.md](KUBERNETES.md). Compose file: `docker-compose.track7.yml`.
3. Demo walk-through: [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md) and [track7/DEMO_SCRIPT.md](track7/DEMO_SCRIPT.md).

## 4. Third-party assets and licenses

Licenses below are **not verified by this review** unless the row says where the repository states it. Each dependency remains under its own license (LICENSE: "Nothing in this license expands or restricts rights granted by those third parties"). Exact versions are pinned in `backend/pyproject.toml` and `frontend/package.json` / lockfiles.

| Component | Where | License |
|---|---|---|
| FastAPI, uvicorn, pydantic, pydantic-settings, asyncpg, sse-starlette, structlog, httpx, python-dotenv, python-jose, passlib, bcrypt, python-multipart, redis | `backend/pyproject.toml` | verify |
| `fhir.resources` (FHIR R4 models), pgvector | `backend/pyproject.toml` | verify |
| anthropic, openai, boto3, langchain, langchain-anthropic, langgraph (optional/runtime AI and AWS adapters) | `backend/pyproject.toml` | verify |
| reportlab, Pillow, python-docx, pypdf, pypdfium2, pytesseract (needs a separately installed Tesseract binary) | `backend/pyproject.toml` | verify |
| numpy | `backend/pyproject.toml` | verify |
| Optional/dev: scikit-learn, pandas, scipy, openpyxl, sentence-transformers, pytest, hypothesis, ruff, mypy, PyYAML | `backend/pyproject.toml` extras | verify |
| React, react-dom, react-router-dom, three, @react-three/fiber, @react-three/drei, lucide-react, clsx, fflate | `frontend/package.json` | verify |
| Dev: vite, vitest, typescript, tailwindcss, postcss, autoprefixer, testing-library, jsdom | `frontend/package.json` | verify |
| Web fonts via Google Fonts: Geist Mono, Source Serif 4, Playfair Display, Outfit, Work Sans, Barlow Condensed, Cormorant, JetBrains Mono, IBM Plex Sans, Space Grotesk (loaded remotely, not bundled) | `frontend/index.html` | verify (each font family has its own license) |
| CardioTwin training data: UCI "Extension of Z-Alizadeh Sani Dataset" (id 411), committed unmodified at `backend/data/cardiotwin/z_alizadeh_sani_extension.csv`, with SHA-256 provenance check | `backend/data/cardiotwin/README.md` | **CC BY 4.0 as stated in that README** (attribution required; not independently re-checked) |
| Interop sample data (`backend/data/interop/*`), appeal sample PNGs (`ops/aws/sample_appeal_pages`), test fixture image, `clincase-mark.svg` logo | repository | Believed first-party/synthetic; verify provenance |
| Standards/references cited in docs (HL7 FHIR R4, WHO, CMS rules) | docs | Cited, not bundled; verify any quoted text |
| Container base images, Kubernetes/kind tooling | Dockerfiles, `k8s/` | verify |

## 5. Third-party data redistribution

No third-party data is redistributed beyond what is documented in [track7/DATA_SOURCES.md](track7/DATA_SOURCES.md) (verified present in this pass). The only third-party dataset this review found committed to the repository is the CardioTwin UCI CSV above, redistributed with attribution under the license its README states. Users must not extract and redistribute that or any other third-party data except as that data's own license allows.

## 6. AI assistance

Claude and Codex assisted development (commit author names in history include "Claude" and "OpenAI Codex"). Human authors are responsible for review, claims and submission. Runtime AI is separate from development assistance and optional in the reliable demo. See [HACKATHON_BUILD_SCOPE.md](HACKATHON_BUILD_SCOPE.md).

## 7. Terms the owner must confirm

None of the following can be determined from the repository. They are listed, not decided.

1. Does the proprietary `LICENSE` permit judges to **run** the software? As written it reserves use and deployment and requires a signed written agreement. Options: add an explicit evaluation permission, supply the signed authorization, relicense, or rely on organizer confirmation. See [LICENSE_REVIEW.md](LICENSE_REVIEW.md).
2. Scope, purpose, duration and signatories of the authorization the requester says exists, and whether it extends to judges and organizers.
3. Whether the hackathon rules require a specific license or run permission (the rules text checked on 2026-10-01 did not).
4. The official build-period dates and treatment of the Oct 4 submission extension (see HACKATHON_BUILD_SCOPE.md).
5. Verified licenses for every row marked "verify" in section 4, and that no third-party material is bundled beyond that table.
6. That all contributor identities in git history (vsrupeshkumar, victrvondoom, internationalhackerrebirth, Claude, OpenAI Codex) are covered by the owner's rights.
7. Preserve the organizers' written replies to the draft clarification questions: whether the extension also extends eligible development time; whether an existing platform may be reused with the Track 7 delta declared; whether a license or AI-assistance declaration is additionally required.
