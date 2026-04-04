# NSW Water · Rules as Code

OpenFisca package encoding NSW water management legislation as executable rules —
metering compliance, controlled activity approvals, and harvestable rights.

---

## What's in here

```
openfisca_nsw_water/        ← OpenFisca rules engine (Python package)
  variables/
    metering.py             ← Metering compliance — dual-axis tier framework
    controlled_activity.py  ← Controlled activity approvals and exemptions
    harvestable_rights.py   ← Farm dam capacity under harvestable rights
  entities.py               ← WaterLicence, LandHolding, ControlledActivityApplication
tests/
  test_water_rules.yaml     ← 21 YAML tests across all three modules
```

---

## Legislation encoded

| Module | Legislation |
|---|---|
| `metering.py` | Water Management Act 2000, s.101A; Water Management (General) Regulation 2025, Part 5 (cl. 66–116), Schedule 7 |
| `controlled_activity.py` | Water Management Act 2000, s.91; Water Management (General) Regulation 2025, Schedule 3 |
| `harvestable_rights.py` | Water Management Act 2000, s.52; Water Management (General) Regulation 2018, cl. 43–48 |

### Metering — dual-axis compliance framework (2025 Regulation)

The 2025 Regulation (commenced 1 September 2025) replaced the 2018 Regulation
and introduced a dual-axis framework. Obligations are determined by **both**
cumulative entitlement (ML) **and** pump/bore diameter (mm):

| Tier | Trigger | Requires |
|---|---|---|
| **Exempt** | Single pump <100mm AND entitlement ≤15ML | Nothing (recording still required) |
| **Tier 2** | Entitlement >15ML and <100ML | Pattern-approved AS4747 meter |
| **Tier 3** | Pump ≥500mm anywhere, OR entitlement ≥100ML | AS4747 meter + DQP validation + LID + telemetry |

---

## Quick start

```bash
git clone https://github.com/rshep85/openfisca-nsw-water.git
cd openfisca-nsw-water
python3 -m venv .venv && source .venv/bin/activate
make install
make test
make serve          # API live at http://localhost:5000
make example-metering   # test a live API call
make example-dam        # test harvestable rights
make example-caa        # test controlled activity approval
```

**Builds on:** [openfisca-nsw-base](https://github.com/Openfisca-NSW/openfisca_nsw_base) — the NSW Government's existing OpenFisca base package (available on PyPI).

---

## Example API call — metering compliance

With `make serve` running:

```bash
curl -s -X POST http://localhost:5000/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "water_licences": {
      "my_licence": {
        "licence_type":                { "ETERNITY": "surface_water" },
        "pump_diameter_mm":            { "ETERNITY": 300.0 },
        "cumulative_entitlement_ml":   { "ETERNITY": 150.0 },
        "water_region":                { "ETERNITY": "inland_regulated" },
        "current_meter_status":        { "ETERNITY": "none" },
        "work_status":                 { "ETERNITY": "active" },
        "is_single_work_on_property":  { "ETERNITY": true },
        "is_trading_allocations":      { "2025": false },
        "compliance_tier":             { "2025": null },
        "metering_required":           { "2025": null },
        "telemetry_required":          { "2025": null },
        "dqp_validation_required":     { "2025": null },
        "compliance_deadline_year":    { "2025": null },
        "metering_compliance_status":  { "2025": null }
      }
    },
    "persons": {}
  }' | python3 -m json.tool
```

Expected response: Tier 3, meter + DQP + telemetry required, deadline 2024 (inland — overdue), status `action_required`.

---

## Running tests

```bash
make test          # all 21 YAML tests
make test-v        # verbose output
```

Tests cover:
- Tier 3 inland and coastal (compliant, action required, upgrade required, LID missing)
- Tier 3 high-risk pump (≥500mm regardless of entitlement)
- Tier 2 (meter only, DQP/telemetry optional)
- Exempt (small pump + low volume)
- Trading allocation override of low-volume exemption
- Groundwater bore size exemption
- Inactive and unintended works
- No licence held
- Controlled activity approvals (6 scenarios)
- Harvestable rights dam capacity (5 scenarios)

---

## Licence

AGPL-3.0 — as required by OpenFisca-Core. If you serve the API publicly,
the source code must be publicly accessible. This is satisfied by the repo
being public on GitHub.

> Computations powered by [OpenFisca](https://openfisca.org) — the free and open-source rules as code engine.
