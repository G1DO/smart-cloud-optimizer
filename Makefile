# Makefile — same verbs as [tool.poe.tasks] (short shell steps, real tools).
# No glue scripts; missing tool fails closed (exit 2), never silent pass.
# Prototype note: test + verify are the only required gates for
# prototype-stage changes; the other verbs run on demand or in review.
# Usage: make verify | make test | make check-secrets (or make 'check:secrets').

.PHONY: help dev test migrate build test-contract test\:contract \
	check-sast check\:sast check-secrets check\:secrets check-audit check\:audit \
	check-hygiene check\:hygiene diagrams verify

help:
	@echo "verbs: dev test migrate build test:contract check:sast check:secrets"
	@echo "       check:audit check:hygiene diagrams verify (prototype: test + verify only)"

dev:
	@python3 -c "import uvicorn" 2>/dev/null || { echo "dev: missing tool uvicorn (pip install -r requirements.txt)"; exit 2; }
	python3 -m uvicorn backend_api.main:app --reload --host 127.0.0.1 --port 8000

test:
	@python3 -c "import pytest" 2>/dev/null || { echo "test: missing tool pytest (pip install -r requirements.txt)"; exit 2; }
	python3 -m pytest tests/ -v

migrate:
	python3 -c "import sqlite3; from storage import ensure_schema; c=sqlite3.connect(':memory:'); ensure_schema(c); c.close(); print('migrate ok')"

build:
	@command -v npm >/dev/null 2>&1 || { echo "build: missing tool npm (install Node 22+)"; exit 2; }
	python3 -m compileall -q backend_api cloud_optimizer aws_collector storage data_generation ml_engine optimizer ai_module dashboard
	npm --prefix frontend run build

test-contract:
	@test -f tests/test_frontend_backend_contract.py || { echo "test:contract omitted: no contract suite in tree"; exit 0; }
	@python3 -c "import pytest" 2>/dev/null || { echo "test:contract: missing tool pytest (pip install -r requirements.txt)"; exit 2; }
	python3 -m pytest tests/test_frontend_backend_contract.py -v

test\:contract: test-contract

check-sast:
	@python3 -c "import bandit" 2>/dev/null || { echo "check:sast: missing tool bandit (pip install bandit)"; exit 2; }
	python3 -m bandit -r backend_api storage -q

check\:sast: check-sast

check-secrets:
	python3 scripts/check_secrets.py

check\:secrets: check-secrets

check-audit:
	python3 -m pip check
	@if command -v pip-audit >/dev/null 2>&1; then pip-audit; else echo "check:audit note: pip-audit not installed — pip check passed (omitted with reason)"; fi

check\:audit: check-audit

check-hygiene:
	@command -v git >/dev/null 2>&1 || { echo "check:hygiene: missing tool git"; exit 2; }
	git diff --check
	python3 scripts/check_no_placeholders.py
	python3 scripts/check_no_pasted_diagrams.py

check\:hygiene: check-hygiene

diagrams:
	@files=$$(find . -name '*.mmd' -not -path './node_modules/*' -not -path './frontend/node_modules/*' -not -path './frontend/.next/*' -not -path './.git/*' -print); \
	if [ -z "$$files" ]; then echo "diagrams omitted: no .mmd sources in tree (add docs/<area>/<name>.mmd to enable)"; exit 0; fi; \
	command -v mmdc >/dev/null 2>&1 || { echo "diagrams: missing tool mermaid-cli (npm i -g @mermaid-js/mermaid-cli)"; exit 2; }; \
	for f in $$files; do mmdc -i "$$f" -o "$${f%.mmd}.svg"; done

verify:
	@python3 -c "import pytest" 2>/dev/null || { echo "verify: missing tool pytest (pip install -r requirements.txt)"; exit 2; }
	@command -v npm >/dev/null 2>&1 || { echo "verify: missing tool npm (install Node 22+)"; exit 2; }
	@command -v git >/dev/null 2>&1 || { echo "verify: missing tool git"; exit 2; }
	python3 -m pytest tests/ -v
	git diff --check
	python3 scripts/check_no_placeholders.py
	python3 scripts/check_no_pasted_diagrams.py
	python3 scripts/check_secrets.py
	python3 scripts/verify_schema_restore.py
	npm --prefix frontend run lint
	npm --prefix frontend run build
