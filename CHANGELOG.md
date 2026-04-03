# Changelog

All notable changes to the `openfisca-nsw-water` package are documented here.

This project follows [Semantic Versioning](https://semver.org/). Rule changes
that alter calculation outputs are **minor** version bumps. New variables or
entities are **minor**. Bug fixes are **patch**. Breaking API changes are
**major**.

---

## [Unreleased]

---

## [0.1.0] — Initial release

### Added
- `entities.py` — Person, WaterLicence, LandHolding, ControlledActivityApplication
- `variables/metering.py` — Metering compliance rules
  - `licence_type`, `pump_diameter_category`, `water_region`, `current_meter_status` (inputs)
  - `metering_required`, `telemetry_required`, `compliance_deadline_year`, `metering_compliance_status` (outputs)
- `variables/controlled_activity.py` — CAA eligibility and exemptions
  - `activity_location`, `activity_type`, `special_circumstance`, `activity_purpose` (inputs)
  - `is_on_waterfront_land`, `emergency_exemption_applies`, `maintenance_exemption_applies`, `caa_exemption_applies`, `caa_required`, `caa_outcome_code` (outputs)
- `variables/harvestable_rights.py` — Farm dam capacity formula
  - `land_area_hectares`, `rainfall_zone`, `catchment_type`, `existing_dam_volume_ml` (inputs)
  - `harvestable_rights_factor`, `maximum_harvestable_dam_capacity_ml`, `remaining_dam_capacity_ml`, `regulated_river_restriction_applies` (outputs)
- `tests/test_water_rules.yaml` — 15 YAML tests covering all three modules
- `Makefile` — install, test, serve, lint, build, upload, bump-version targets
- `.github/workflows/test.yml` — CI on Python 3.7, 3.9, 3.11

### Legislation encoded
- Water Management Act 2000 (NSW) — s.52, s.91, s.91A, s.91I
- Water Management (General) Regulation 2018 — cl.43–48, cl.174–180, Schedule 3
- NSW Non-Urban Water Metering Policy 2019 — Appendix A (phased deadlines)

---

## How to record a rule change

When NSW legislation or policy changes, follow this process:

1. Update the relevant variable formula in `variables/`
2. Update any affected parameters (thresholds, dates, factors)
3. Add or update YAML tests to cover the new rule
4. Run `make test` to confirm all tests pass
5. Bump the version: `make bump-patch` (small fix) or `make bump-minor` (new rule)
6. Update this CHANGELOG under `[Unreleased]`
7. Commit with a message like: `feat: update metering deadline for coastal catchments (Policy 2025 revision)`

---

*Computations powered by [OpenFisca](https://openfisca.org) — AGPL-3.0.*
