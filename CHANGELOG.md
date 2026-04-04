# Changelog

All notable changes to the `openfisca-nsw-water` package are documented here.

This project follows [Semantic Versioning](https://semver.org/). Rule changes
that alter calculation outputs are **minor** version bumps. New variables or
entities are **minor**. Bug fixes are **patch**. Breaking API changes are
**major**.

---

## [Unreleased]

---

## [0.2.0] — 2025 Regulation update

### Changed

Metering compliance rules updated to reflect the **Water Management (General)
Regulation 2025** (commenced 1 September 2025), which replaced the 2018
Regulation and introduced a dual-axis compliance framework. Obligations are
now determined by **both** cumulative entitlement (ML) **and** pump/bore
diameter (mm), replacing the previous single-axis pump-size approach.

#### `variables/metering.py`

* **Removed** `pump_diameter_category` (Enum: small/medium/large) — replaced
  by continuous float inputs that match the actual legislative thresholds
* **Removed** `WaterRegion.murray_darling_regulated` and
  `WaterRegion.groundwater_mdb` enum values — region model simplified to
  `inland_regulated`, `inland_unregulated`, `coastal` reflecting the
  deadline structure in the 2025 Regulation
* **Removed** `MeterStatus.pattern_approved` — split into
  `pattern_approved_with_lid` and `pattern_approved_no_lid` to support the
  new `lid_required` compliance status
* **Added** `pump_diameter_mm` (float) — exact pump/bore diameter in mm
* **Added** `cumulative_entitlement_ml` (float) — total entitlement across
  all WALs nominated on the works approval
* **Added** `work_status` (Enum) — `active`, `inactive`, `unintended`;
  inactive and unintended works are now explicitly exempt under Schedule 7
* **Added** `is_trading_allocations` (bool) — trading overrides the ≤15ML
  low-volume exemption
* **Added** `is_single_work_on_property` (bool) — affects size-based
  exemption thresholds where multiple works exist on a property
* **Added** `is_size_exempt` (bool) — calculated; true where pump/bore is
  below the size threshold and the 500mm override does not apply
* **Added** `compliance_tier` (Enum) — central calculated variable:
  `not_applicable`, `exempt`, `tier_2_meter_only`,
  `tier_3_full_compliance`; all downstream variables derive from this
* **Added** `dqp_validation_required` (bool) — true for Tier 3 only
* **Added** `revalidation_period_years` (int) — 10 years initial (extended
  from 5 under 2018 Regulation), 5 years thereafter
* **Changed** `telemetry_required` — now decoupled from `metering_required`;
  mandatory for Tier 3 only, optional for Tier 2
* **Changed** `compliance_deadline_year` — now derived from `compliance_tier`
  and `water_region`; returns 0 for exempt/not-applicable works
* **Changed** `metering_compliance_status` — now returns six states instead
  of four: `not_applicable`, `exempt`, `compliant`, `lid_required`,
  `upgrade_required`, `action_required`

#### `tests/test_water_rules.yaml`

* All 6 metering tests replaced with 12 new tests covering the full
  decision space of the 2025 dual-axis framework (Tier 3 inland/coastal,
  Tier 2, exempt, trading override, groundwater, inactive works, no licence)
* CAA and harvestable rights tests unchanged

#### `Makefile`

* `example-metering` curl payload updated to use new input variables

#### `setup.py`

* Version bumped to `0.2.0`
* Repository URL corrected to `https://github.com/rshep85/openfisca-nsw-water`

### Legislation reference change

| Was | Now |
|---|---|
| Water Management (General) Regulation 2018, cl. 174–180 | Water Management (General) Regulation 2025, Part 5, cl. 66–116 |
| NSW Non-Urban Water Metering Policy 2019, Appendix A | Water Management (General) Regulation 2025, Schedule 7 |

---

## [0.1.0] — Initial release

### Added

* `entities.py` — Person, WaterLicence, LandHolding, ControlledActivityApplication
* `variables/metering.py` — Metering compliance rules
  + `licence_type`, `pump_diameter_category`, `water_region`, `current_meter_status` (inputs)
  + `metering_required`, `telemetry_required`, `compliance_deadline_year`, `metering_compliance_status` (outputs)
* `variables/controlled_activity.py` — CAA eligibility and exemptions
  + `activity_location`, `activity_type`, `special_circumstance`, `activity_purpose` (inputs)
  + `is_on_waterfront_land`, `emergency_exemption_applies`, `maintenance_exemption_applies`, `caa_exemption_applies`, `caa_required`, `caa_outcome_code` (outputs)
* `variables/harvestable_rights.py` — Farm dam capacity formula
  + `land_area_hectares`, `rainfall_zone`, `catchment_type`, `existing_dam_volume_ml` (inputs)
  + `harvestable_rights_factor`, `maximum_harvestable_dam_capacity_ml`, `remaining_dam_capacity_ml`, `regulated_river_restriction_applies` (outputs)
* `tests/test_water_rules.yaml` — 15 YAML tests covering all three modules
* `Makefile` — install, test, serve, lint, build, upload, bump-version targets
* `.github/workflows/test.yml` — CI on Python 3.7, 3.9, 3.11

### Legislation encoded

* Water Management Act 2000 (NSW) — s.52, s.91, s.91A, s.91I
* Water Management (General) Regulation 2018 — cl.43–48, cl.174–180, Schedule 3
* NSW Non-Urban Water Metering Policy 2019 — Appendix A (phased deadlines)

---

## How to record a rule change

When NSW legislation or policy changes, follow this process:

1. Update the relevant variable formula in `variables/`
2. Update any affected parameters (thresholds, dates, factors)
3. Add or update YAML tests to cover the new rule
4. Run `make test` to confirm all tests pass
5. Bump the version: `make bump-patch` (small fix) or `make bump-minor` (new rule)
6. Update this CHANGELOG under `[Unreleased]`
7. Commit with a message like: `feat: update metering deadline for coastal catchments (Reg 2025)`

---

*Computations powered by [OpenFisca](https://openfisca.org) — AGPL-3.0.*
