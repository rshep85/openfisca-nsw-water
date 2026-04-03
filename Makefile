# =============================================================================
# OpenFisca NSW Water — Makefile
#
# Usage:
#   make install       Install package and dependencies
#   make test          Run all YAML tests
#   make serve         Serve the OpenFisca Web API locally (port 5000)
#   make build         Build distribution package
#   make upload        Upload to PyPI
#   make lint          Lint Python files
#   make clean         Remove build artifacts
#
# Prerequisites: Python 3.7+, pip, virtualenv
# =============================================================================

PACKAGE     = openfisca_nsw_water
PORT        = 5000
PYTHON      = python3
PIP         = pip
VENV        = .venv
VENV_BIN    = $(VENV)/bin

# ── Colours for output ──────────────────────────────────────────────────────
RESET  = \033[0m
BOLD   = \033[1m
GREEN  = \033[32m
YELLOW = \033[33m
CYAN   = \033[36m

.DEFAULT_GOAL := help

# ── Help ────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "$(BOLD)OpenFisca NSW Water$(RESET)"
	@echo "Encodes NSW water management rules as code."
	@echo ""
	@echo "$(CYAN)Available commands:$(RESET)"
	@echo "  $(GREEN)make install$(RESET)      Install package and all dependencies"
	@echo "  $(GREEN)make test$(RESET)         Run all YAML rule tests"
	@echo "  $(GREEN)make serve$(RESET)        Serve the Web API on http://localhost:$(PORT)"
	@echo "  $(GREEN)make lint$(RESET)         Lint Python source files"
	@echo "  $(GREEN)make build$(RESET)        Build distribution packages (sdist + wheel)"
	@echo "  $(GREEN)make upload$(RESET)       Upload to PyPI (requires credentials)"
	@echo "  $(GREEN)make clean$(RESET)        Remove build artifacts and cache"
	@echo "  $(GREEN)make venv$(RESET)         Create a fresh virtualenv"
	@echo ""
	@echo "$(CYAN)Quick start:$(RESET)"
	@echo "  make venv && source $(VENV)/bin/activate && make install && make test"
	@echo ""

# ── Virtual environment ──────────────────────────────────────────────────────
.PHONY: venv
venv:
	@echo "$(CYAN)→ Creating virtualenv in $(VENV)/$(RESET)"
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip
	@echo "$(GREEN)✓ Virtualenv ready. Activate with: source $(VENV)/bin/activate$(RESET)"

# ── Install ──────────────────────────────────────────────────────────────────
.PHONY: install
install:
	@echo "$(CYAN)→ Installing $(PACKAGE) and dependencies...$(RESET)"
	$(PIP) install --upgrade pip
	$(PIP) install --editable ".[dev]"
	@echo "$(GREEN)✓ Installation complete$(RESET)"
	@echo ""
	@echo "  Run tests:  make test"
	@echo "  Serve API:  make serve"

# ── Test ─────────────────────────────────────────────────────────────────────
.PHONY: test
test:
	@echo "$(CYAN)→ Running YAML tests against $(PACKAGE)...$(RESET)"
	openfisca test tests/ --country-package $(PACKAGE)
	@echo "$(GREEN)✓ All tests passed$(RESET)"

# Test with verbose output
.PHONY: test-v
test-v:
	@echo "$(CYAN)→ Running YAML tests (verbose)...$(RESET)"
	openfisca test tests/ --country-package $(PACKAGE) --verbose

# Test a specific file
.PHONY: test-file
test-file:
	@echo "$(CYAN)→ Running tests in $(FILE)...$(RESET)"
	openfisca test $(FILE) --country-package $(PACKAGE)

# ── Serve ─────────────────────────────────────────────────────────────────────
.PHONY: serve
serve:
	@echo "$(CYAN)→ Serving OpenFisca Web API on http://localhost:$(PORT)$(RESET)"
	@echo "$(YELLOW)  Swagger docs: http://localhost:$(PORT)/spec$(RESET)"
	@echo "$(YELLOW)  Calculate:    POST http://localhost:$(PORT)/calculate$(RESET)"
	@echo "$(YELLOW)  Variables:    GET  http://localhost:$(PORT)/variables$(RESET)"
	@echo ""
	openfisca serve \
		--country-package $(PACKAGE) \
		--port $(PORT) \
		--bind 0.0.0.0

# Serve with auto-reload on file changes (development)
.PHONY: serve-dev
serve-dev:
	@echo "$(CYAN)→ Serving in dev mode (auto-reload)...$(RESET)"
	openfisca serve \
		--country-package $(PACKAGE) \
		--port $(PORT) \
		--bind 0.0.0.0 \
		--reload

# ── Example API calls ─────────────────────────────────────────────────────────
# Run these after `make serve` in another terminal.

.PHONY: example-metering
example-metering:
	@echo "$(CYAN)→ Example: metering_required calculation$(RESET)"
	curl -s -X POST http://localhost:$(PORT)/calculate \
	  -H "Content-Type: application/json" \
	  -d '{ \
	    "water_licences": { \
	      "my_licence": { \
	        "licence_type":           { "ETERNITY": "surface_water" }, \
	        "pump_diameter_category": { "ETERNITY": "large" }, \
	        "water_region":           { "ETERNITY": "murray_darling_regulated" }, \
	        "current_meter_status":   { "ETERNITY": "none" }, \
	        "metering_required":         { "2025": null }, \
	        "telemetry_required":         { "2025": null }, \
	        "compliance_deadline_year":  { "2025": null }, \
	        "metering_compliance_status":{ "2025": null } \
	      } \
	    }, \
	    "persons": {} \
	  }' | python3 -m json.tool

.PHONY: example-dam
example-dam:
	@echo "$(CYAN)→ Example: harvestable rights dam capacity$(RESET)"
	curl -s -X POST http://localhost:$(PORT)/calculate \
	  -H "Content-Type: application/json" \
	  -d '{ \
	    "land_holdings": { \
	      "my_property": { \
	        "land_area_hectares":  { "ETERNITY": 150 }, \
	        "rainfall_zone":       { "ETERNITY": "medium" }, \
	        "catchment_type":      { "ETERNITY": "unregulated" }, \
	        "existing_dam_volume_ml": { "ETERNITY": 0 }, \
	        "maximum_harvestable_dam_capacity_ml": { "2025": null }, \
	        "remaining_dam_capacity_ml":           { "2025": null }, \
	        "harvestable_rights_factor":           { "2025": null } \
	      } \
	    }, \
	    "persons": {} \
	  }' | python3 -m json.tool

.PHONY: example-caa
example-caa:
	@echo "$(CYAN)→ Example: controlled activity approval check$(RESET)"
	curl -s -X POST http://localhost:$(PORT)/calculate \
	  -H "Content-Type: application/json" \
	  -d '{ \
	    "controlled_activity_applications": { \
	      "my_application": { \
	        "activity_location":  { "ETERNITY": "within_40m_river" }, \
	        "activity_type":      { "ETERNITY": "erect_structure" }, \
	        "special_circumstance": { "ETERNITY": "none" }, \
	        "activity_purpose":   { "ETERNITY": "agricultural" }, \
	        "caa_required":       { "2025": null }, \
	        "caa_outcome_code":   { "2025": null }, \
	        "caa_exemption_applies": { "2025": null } \
	      } \
	    }, \
	    "persons": {} \
	  }' | python3 -m json.tool

# ── Lint ──────────────────────────────────────────────────────────────────────
.PHONY: lint
lint:
	@echo "$(CYAN)→ Linting Python source files...$(RESET)"
	$(PIP) install flake8 --quiet
	flake8 $(PACKAGE)/ \
		--max-line-length=120 \
		--extend-ignore=E501,W503 \
		--exclude=__pycache__,.venv
	@echo "$(GREEN)✓ Lint passed$(RESET)"

# ── Build ─────────────────────────────────────────────────────────────────────
.PHONY: build
build: clean
	@echo "$(CYAN)→ Building distribution packages...$(RESET)"
	$(PIP) install build --quiet
	$(PYTHON) -m build
	@echo "$(GREEN)✓ Build complete — packages in dist/$(RESET)"
	@ls -lh dist/

# ── Upload to PyPI ────────────────────────────────────────────────────────────
.PHONY: upload
upload: build
	@echo "$(CYAN)→ Uploading to PyPI...$(RESET)"
	@echo "$(YELLOW)  Ensure you have configured ~/.pypirc or set TWINE_USERNAME / TWINE_PASSWORD$(RESET)"
	$(PIP) install twine --quiet
	twine upload dist/*
	@echo "$(GREEN)✓ Upload complete$(RESET)"

# Upload to TestPyPI first (recommended before a real release)
.PHONY: upload-test
upload-test: build
	@echo "$(CYAN)→ Uploading to TestPyPI...$(RESET)"
	twine upload --repository testpypi dist/*

# ── Clean ─────────────────────────────────────────────────────────────────────
.PHONY: clean
clean:
	@echo "$(CYAN)→ Cleaning build artifacts...$(RESET)"
	rm -rf dist/ build/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Clean$(RESET)"

# ── Version bump helpers ──────────────────────────────────────────────────────
# Usage: make bump-patch  (0.1.0 → 0.1.1)
#        make bump-minor  (0.1.0 → 0.2.0)
#        make bump-major  (0.1.0 → 1.0.0)

.PHONY: bump-patch bump-minor bump-major
bump-patch:
	@echo "$(CYAN)→ Bumping patch version...$(RESET)"
	$(PIP) install bump2version --quiet
	bump2version patch
	@echo "$(GREEN)✓ Version bumped$(RESET)"

bump-minor:
	$(PIP) install bump2version --quiet
	bump2version minor

bump-major:
	$(PIP) install bump2version --quiet
	bump2version major

# ── CI shortcut ───────────────────────────────────────────────────────────────
# Used by GitHub Actions (see .github/workflows/test.yml)
.PHONY: ci
ci: install lint test
	@echo "$(GREEN)✓ CI checks passed$(RESET)"
