# NSW Water · Rules as Code — Complete Package

This repository contains everything produced as part of the NSW Water Rules as Code initiative:
a working OpenFisca rules model, two interactive demo applications, and the supporting strategic documents.

---

## What's in here

```
openfisca_nsw_water/        ← Phase 1: OpenFisca rules engine (Python package)
demo_apps/                  ← Interactive HTML demos (open in any browser)
documents/                  ← Strategic brief and personal note (Word docs)
```

---

## Phase 1 — OpenFisca NSW Water Rules Engine

A Python package that encodes NSW water management legislation as executable rules.

**Legislation encoded:**
- Water Management Act 2000 (s.52, s.91, s.91A, s.91I)
- Water Management (General) Regulation 2018 (cl.43–48, cl.174–180, Schedule 3)
- NSW Non-Urban Water Metering Policy 2019 (Appendix A — phased deadlines)

**Three rule modules:**

| Module | What it calculates |
|---|---|
| `metering.py` | Is a meter required? Telemetry? What deadline? |
| `controlled_activity.py` | Is a CAA required? Does an exemption apply? |
| `harvestable_rights.py` | Maximum dam capacity (ML) under harvestable rights |

**Quick start:**
```bash
cd openfisca_nsw_water
python3 -m venv .venv && source .venv/bin/activate
make install
make test
make serve          # API live at http://localhost:5000
make example-metering   # test a real API call
```

**Builds on:** [openfisca-nsw-base](https://github.com/Openfisca-NSW/openfisca_nsw_base) — the NSW Government's existing OpenFisca base package (shared entities, available on PyPI).

---

## Phase 2 — Demo Applications

Open either HTML file directly in a browser — no server required.

### `01_phase1_rac_executive_demo.html`
Three-lens executive demonstration of the Rules as Code platform:
- **Water User lens** — four guided compliance tools (metering, CAA, dam calculator, navigator)
- **NRAR Regulator lens** — automated monitoring dashboard, breach flagging, regional compliance
- **Policy Simulation lens** — adjust rule parameters and see population-wide impact

### `02_phase2_compliance_register_tiered_attestation.html`
Compliance Obligation Register with honest tiered attestation:
- Obligations register with Tier 1/2/3 integrity classification per obligation
- Live compliance calendar
- Upload and extract obligations from licence documents (simulated)
- Change detection — what changed when a licence is amended
- NRAR regulator dashboard showing entity integrity scores
- Entity switcher: water/floodplain harvesting/supplementary licence types

**The handoff between Phase 1 and Phase 2** is demonstrated — a metering compliance result from the RaC tool appears pre-populated in the obligation register.

---

## Documents

| File | Purpose |
|---|---|
| `NRAR_RaC_Strategic_Brief.docx` | Strategic initiative brief for the Chief Regulatory Officer |
| `NRAR_CRO_Personal_Note.docx` | Personal follow-up note re: EO14/15 role, tenure, review point |

---

## GitHub setup (your own repo)

This package is designed to live in your own GitHub account — not the NSW Government Openfisca-NSW org.

```bash
# 1. Create a new repo on github.com
#    Suggested name: openfisca-nsw-water
#    Visibility: Public (required for AGPL-3.0 compliance if you serve the API)
#    Licence: AGPL-3.0 (select when creating)

# 2. Clone it locally
git clone https://github.com/YOUR-USERNAME/openfisca-nsw-water.git
cd openfisca-nsw-water

# 3. Copy the openfisca_nsw_water/ folder contents in
#    (everything inside openfisca_nsw_water/ goes to the repo root)

# 4. Update setup.py — change the url field:
#    url="https://github.com/YOUR-USERNAME/openfisca-nsw-water"

# 5. Push
git add .
git commit -m "Initial NSW water rules package — metering, CAA, harvestable rights"
git push
```

The demo apps and documents are separate from the GitHub package — keep them locally or in a private repo.

---

## Licence

AGPL-3.0 — as required by OpenFisca-Core. If you serve the API publicly, the source code must be publicly accessible. This is already satisfied by having the repo public on GitHub.

> Computations powered by [OpenFisca](https://openfisca.org) — the free and open-source rules as code engine.
