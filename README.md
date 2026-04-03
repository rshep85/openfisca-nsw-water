# OpenFisca NSW Water

An [OpenFisca](https://openfisca.org) package encoding NSW water management rules as code.

Builds on the [`openfisca-nsw-base`](https://github.com/Openfisca-NSW/openfisca_nsw_base) package established by the NSW Government Rules-as-Code programme.

---

## Legislation Encoded

| Module | Legislation | Rules encoded |
|---|---|---|
| `metering.py` | Water Management Act 2000 s.91I; Water Management (General) Regulation 2018 cl.174–180; NSW Metering Policy 2019 | Is metering required? Is telemetry required? What is the compliance deadline? |
| `controlled_activity.py` | Water Management Act 2000 s.91; WM(G) Regulation 2018 Schedule 3 | Is the activity on waterfront land? Does an exemption apply? Is a CAA required? |
| `harvestable_rights.py` | Water Management Act 2000 s.52; WM(G) Regulation 2018 cl.43–48 | Maximum dam capacity (ML); Remaining capacity; Regulated river restrictions |

---

## Package Structure

```
openfisca_nsw_water/
├── __init__.py
├── entities.py                    # Person, LandHolding, WaterLicence, ControlledActivityApplication
└── variables/
    ├── metering.py                # Metering compliance rules
    ├── controlled_activity.py     # CAA eligibility and exemptions
    └── harvestable_rights.py      # Dam capacity formula

tests/
└── test_water_rules.yaml          # YAML tests for all three modules

setup.py
README.md
```

---

## Install

```bash
python -m venv water
source water/bin/activate
pip install -e .
```

## Run Tests

```bash
openfisca test tests/ --country-package openfisca_nsw_water
```

## Serve the API

```bash
openfisca serve --country-package openfisca_nsw_water --port 5000
```

Then call it:

```bash
curl -X POST http://localhost:5000/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "water_licences": {
      "my_licence": {
        "licence_type": { "ETERNITY": "surface_water" },
        "pump_diameter_category": { "ETERNITY": "large" },
        "water_region": { "ETERNITY": "murray_darling_regulated" },
        "current_meter_status": { "ETERNITY": "none" },
        "metering_required": { "2024": null },
        "compliance_deadline_year": { "2024": null },
        "telemetry_required": { "2024": null }
      }
    },
    "persons": {}
  }'
```

Expected response:
```json
{
  "water_licences": {
    "my_licence": {
      "metering_required": { "2024": true },
      "compliance_deadline_year": { "2024": 2024 },
      "telemetry_required": { "2024": true }
    }
  }
}
```

---

## Contributing

To add new rules (e.g. water restriction checks, entitlement calculators):

1. Add a new `.py` file under `variables/`
2. Define input variables (facts about the situation)
3. Define calculated variables with `formula()` methods that encode the legal logic
4. Add YAML tests to `tests/`
5. Run `openfisca test` to verify

---

## Credits

Computations powered by [OpenFisca](https://openfisca.org), the free and open-source social and fiscal computation engine. Source code available at [github.com/openfisca](https://github.com/openfisca). Licensed AGPL-3.0.

## Licence

AGPL-3.0 — as required by OpenFisca-Core.
