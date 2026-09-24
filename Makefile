.PHONY: help backend.install backend.dev backend.test backend.lint \
        frontend.install frontend.dev frontend.build frontend.typecheck \
        db.init db.reset db.psql \
        ingest.policies seed.demo \
        smoke deck preflight tf.fmt tf.validate kiro.export \
        migrate sbom sign supply-chain \
        twin.test twin.demo twin.stress twin.train twin.reference twin.benchmark \
        test lint clean

help:
	@echo "ClinCase Makefile targets"
	@echo "  backend.install   - install Python dependencies"
	@echo "  backend.dev       - run uvicorn with reload"
	@echo "  backend.test      - run pytest"
	@echo "  backend.lint      - ruff + mypy"
	@echo "  frontend.install  - install node modules"
	@echo "  frontend.dev      - run vite dev server"
	@echo "  frontend.build    - build production bundle"
	@echo "  db.init           - apply schema.sql to local postgres"
	@echo "  db.reset          - drop volume and reinit"
	@echo "  db.psql           - open psql shell on local postgres"
	@echo "  ingest.policies   - ingest payer PDFs into pgvector"
	@echo "  seed.demo         - seed the 10 demo cases"
	@echo "  twin.test         - OncoTwin tests"
	@echo "  twin.demo         - OncoTwin flagship journey (one command, synthetic)"
	@echo "  twin.stress       - OncoTwin red-team stress test"
	@echo "  twin.train        - retrain OncoTwin models"
	@echo "  twin.reference    - rebuild the drift reference profile"
	@echo "  twin.benchmark    - OncoTwin Research Lab benchmark"
	@echo "  test              - run all tests"
	@echo "  lint              - run all linters"

# --- backend ---------------------------------------------------------------
backend.install:
	cd backend && python -m pip install -e ".[dev]"

backend.dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend.test:
	cd backend && pytest -q

backend.lint:
	cd backend && ruff check app tests && ruff format --check app tests
	cd backend && mypy app/models app/graph

# --- frontend --------------------------------------------------------------
frontend.install:
	cd frontend && npm install

frontend.dev:
	cd frontend && npm run dev

frontend.build:
	cd frontend && npm run build

# --- OncoTwin (digital twin) -------------------------------------------------
# No database or LLM key needed. All data is synthetic.
twin.test:
	cd backend && pytest tests/oncotwin -q

twin.demo:            ## flagship OT-005 closed-loop journey end to end; writes JSON + Markdown report
	cd backend && python -m app.oncotwin.demo

twin.stress:          ## red-team Twin Stress Test; non-zero exit if any scenario fails unsafe
	cd backend && python -m app.oncotwin.stress

twin.train:           ## retrain the OT-ACUTE-7 model and the multi-horizon survival model (deterministic)
	cd backend && python -m app.oncotwin.ml.train --n 1000 && python -m app.oncotwin.ml.horizon --n 1000

twin.reference:       ## rebuild the drift-monitor reference profile from the training cohort
	cd backend && python -m app.oncotwin.mlops.drift --build-reference

twin.benchmark:       ## Research Lab benchmark (modality, ablation, horizons, change points, lead time)
	cd backend && python -m app.oncotwin.research.benchmark --n 1000

# --- database --------------------------------------------------------------
db.init:
	docker exec -i clincase-postgres psql -U clincase -d clincase < backend/db/schema.sql

db.reset:
	docker compose down -v
	docker compose up -d postgres
	@echo "waiting for postgres..." && sleep 5
	$(MAKE) db.init

db.psql:
	docker exec -it clincase-postgres psql -U clincase -d clincase

# --- demo data -------------------------------------------------------------
ingest.policies:
	cd backend && python -m app.ingestion.ingest_policies

seed.demo:
	cd backend && python -m app.synthea.seed

# --- top-level -------------------------------------------------------------
test: backend.test

lint: backend.lint

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true

# --- demo checks ---------------------------------------------------------
smoke:
	cd backend && .venv/Scripts/python.exe -m scripts.smoke_test

frontend.typecheck:
	cd frontend && npx tsc --noEmit

# Full pre-demo gate: backend smoke + frontend typecheck
preflight: smoke frontend.typecheck
	@echo "preflight passed: backend smoke OK, frontend typecheck OK"

kiro.export:
	cd backend && .venv/Scripts/python.exe -m app.integrations.kiro.exporter

# --- terraform ------------------------------------------------------------
tf.fmt:
	cd ops/terraform && terraform fmt -recursive

tf.validate:
	@for d in multi-region provisioned-throughput bedrock-vpc-endpoint s3-vectors waf cdc-stream fis audit-export secrets-rotation; do \
		echo "--- validating $$d ---"; \
		if [ -d "ops/terraform/$$d" ]; then \
			cd ops/terraform/$$d && terraform init -backend=false > /dev/null && terraform validate && cd ../../..; \
		else \
			echo "  (not present yet — skipping)"; \
		fi; \
	done

# --- alembic schema migrations (round 11) ---------------------------------
# In production, this Makefile target runs as a Kubernetes Job before each
# rollout. Exit code 0 → deploy proceeds. Non-zero → deploy aborts.
migrate:
	cd backend && DATABASE_URL=$${DATABASE_URL:-postgresql://clincase:clincase@localhost:5432/clincase} \
		.venv/Scripts/python.exe -m alembic upgrade head

# --- supply chain security (round 11) ------------------------------------
# Generates a CycloneDX SBOM for the backend image + signs the image with
# Sigstore cosign (keyless OIDC). Required for FedRAMP and increasingly for
# HHS attestation.
#
# Pre-reqs:
#   - syft   (https://github.com/anchore/syft)   — SBOM generator
#   - cosign (https://github.com/sigstore/cosign) — keyless image signer
#   - The image must already be built + pushed
#
# CI pipeline runs `make supply-chain` after `docker push`; the resulting
# SBOM is attached to the GitHub Release; the cosign signature is verified
# at deploy time via Argo CD's image verifier.

sbom:
	@echo "→ generating CycloneDX SBOM for backend image..."
	syft clincase-backend:latest -o cyclonedx-json > sbom-backend.cdx.json
	@echo "→ generating CycloneDX SBOM for worker image..."
	syft clincase-worker:latest -o cyclonedx-json > sbom-worker.cdx.json
	@echo "OK: sbom-backend.cdx.json + sbom-worker.cdx.json"

sign:
	@echo "→ signing backend image with Sigstore cosign (keyless via OIDC)..."
	COSIGN_EXPERIMENTAL=1 cosign sign clincase-backend:latest
	@echo "→ signing worker image..."
	COSIGN_EXPERIMENTAL=1 cosign sign clincase-worker:latest
	@echo "OK: images signed; signatures pushed to the registry alongside images"

supply-chain: sbom sign
	@echo "supply-chain bundle ready: SBOM + Sigstore signatures"
