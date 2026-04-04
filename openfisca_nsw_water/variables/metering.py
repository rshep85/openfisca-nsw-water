"""
Metering compliance variables for NSW water licences.

Encodes the NSW metering rules under:
  - Water Management Act 2000, Part 2, Division 3 (s.91I, s.101A)
  - Water Management (General) Regulation 2025, Part 5 (cl. 66-116)
  - Water Management (General) Regulation 2025, Schedule 5 (metering standards)
  - Water Management (General) Regulation 2025, Schedule 7 (exemptions)

Updated from the 2018 Regulation to reflect the 2025 Regulation which
commenced 1 September 2025 and introduced a dual-axis compliance framework:
obligations are now determined by BOTH cumulative entitlement (ML) AND
pump/bore diameter (mm), replacing the previous single-axis pump-size approach.

Key structural changes from 2018 → 2025 Regulation:
  - New low-volume exemption: ≤15ML entitlement exempt from metering
  - New middle tier: >15ML and <100ML requires meter but DQP/telemetry optional
  - Telemetry decoupled from metering for sub-100ML works
  - Compliance deadlines revised, coastal deadline extended to 1 Dec 2026/2027
  - Revalidation period extended: 10 years initial, 5 years thereafter
  - work_status (active/inactive/unintended) now affects obligations

Variables are defined on the WaterLicence entity.
"""

import numpy as np
from openfisca_core.periods import ETERNITY, MONTH, YEAR
from openfisca_core.variables import Variable
from openfisca_core.indexed_enums import Enum

from openfisca_nsw_water.entities import WaterLicence


# ── Enumerations ─────────────────────────────────────────────────────────────

class LicenceType(Enum):
    """
    Type of NSW water access licence.
    Reference: Water Management Act 2000, s.55
    """
    surface_water = "Surface water access licence"
    groundwater = "Groundwater access licence"
    floodplain_harvesting = "Floodplain harvesting access licence"
    interim = "Interim water access licence"
    none = "No water access licence"


class WaterRegion(Enum):
    """
    Geographic region of the extraction works.
    Determines compliance deadline under the 2025 Regulation.
    Inland = MDB and inland unregulated systems.
    Coastal = coastal catchments.
    Reference: Water Management (General) Regulation 2025, cl. 66 + Schedule 7
    """
    inland_regulated = "Inland regulated rivers (incl. Murray-Darling Basin)"
    inland_unregulated = "Inland unregulated rivers and groundwater"
    coastal = "Coastal catchments"


class MeterStatus(Enum):
    """
    Current installation status of metering equipment at the works.
    Reference: Water Management (General) Regulation 2025, cl. 68-70
    """
    pattern_approved_with_lid = "Pattern-approved AS4747 meter with LID/telemetry installed"
    pattern_approved_no_lid = "Pattern-approved AS4747 meter installed, no LID"
    non_approved = "Older non-approved meter installed"
    none = "No meter installed"


class WorkStatus(Enum):
    """
    Operational status of the water supply work (pump or bore).
    Inactive and unintended works are exempt from metering obligations.
    Reference: Water Management (General) Regulation 2025, Schedule 7
    """
    active = "Active — currently used to take licensed water"
    inactive = "Inactive — not currently used, may be reactivated"
    unintended = "Unintended — listed on approval but not taking licensed water"


class ComplianceTier(Enum):
    """
    Metering compliance tier under the 2025 dual-axis framework.
    Tier is determined by cumulative entitlement AND pump/bore diameter.
    Reference: Water Management (General) Regulation 2025, Part 5, Division 2
    """
    exempt = "Exempt — below size and volume thresholds"
    tier_2_meter_only = "Tier 2 — pattern-approved meter required, DQP/telemetry optional"
    tier_3_full_compliance = "Tier 3 — full compliance: AS4747 meter + DQP + LID + telemetry"
    not_applicable = "Not applicable — no licence or inactive/unintended works"


# ── Input Variables ───────────────────────────────────────────────────────────

class licence_type(Variable):
    """
    The category of NSW water access licence held.
    Reference: Water Management Act 2000, s.55
    """
    value_type = Enum
    possible_values = LicenceType
    default_value = LicenceType.surface_water
    entity = WaterLicence
    definition_period = ETERNITY
    label = "Type of water access licence"
    reference = "Water Management Act 2000, s.55"


class water_region(Variable):
    """
    Geographic region of the extraction works.
    Determines compliance deadline phase under the 2025 Regulation.
    Inland deadline for large works: now (overdue).
    Coastal deadline for large works: 1 December 2026.
    All works >15ML and <100ML: 1 December 2027 or works renewal, whichever first.
    Reference: Water Management (General) Regulation 2025, cl. 66; Schedule 7
    """
    value_type = Enum
    possible_values = WaterRegion
    default_value = WaterRegion.inland_regulated
    entity = WaterLicence
    definition_period = ETERNITY
    label = "Geographic region of extraction works"
    reference = "Water Management (General) Regulation 2025, cl. 66"


class pump_diameter_mm(Variable):
    """
    Diameter of the authorised water supply work (pump or bore) in millimetres.
    This is one of two axes that determine metering obligations.

    Key thresholds under the 2025 Regulation:
      Surface water pumps:
        <100mm  → size-based exemption (single pump on property)
        100–499mm → standard works, obligations set by entitlement tier
        ≥500mm  → high-risk works, full Tier 3 compliance regardless of entitlement

      Groundwater bores:
        <200mm  → size-based exemption (single bore on property)
        ≥200mm  → standard bore, obligations set by entitlement tier

    Note: Where there is more than one pump or bore on a property, different
    size-based exemption thresholds apply — see Schedule 7, Part 2.

    Reference: Water Management (General) Regulation 2025, cl. 73; Schedule 7
    """
    value_type = float
    entity = WaterLicence
    definition_period = ETERNITY
    label = "Diameter of extraction works in millimetres"
    reference = "Water Management (General) Regulation 2025, cl. 73; Schedule 7"


class cumulative_entitlement_ml(Variable):
    """
    Total cumulative share component (entitlement) across ALL water access
    licences nominated on the works approval, expressed in megalitres (ML).

    This is the second axis determining metering obligations.
    Where a work is nominated on multiple WALs, the entitlements are summed.
    1 unit share = 1 ML under the 2025 Regulation dictionary.

    Key thresholds:
      ≤15ML   → exempt from mandatory metering (unless trading allocations)
      >15ML and <100ML → Tier 2: meter required, DQP/LID/telemetry optional
      ≥100ML  → Tier 3: full compliance required (AS4747 + DQP + LID + telemetry)

    Reference: Water Management (General) Regulation 2025, cl. 73-75; Schedule 7
    """
    value_type = float
    entity = WaterLicence
    definition_period = ETERNITY
    label = "Cumulative licensed entitlement across all WALs on the works (ML)"
    reference = "Water Management (General) Regulation 2025, cl. 73; Schedule 7, Part 2"


class current_meter_status(Variable):
    """
    Current installation status of metering equipment at the works.
    Reference: Water Management (General) Regulation 2025, cl. 68-70
    """
    value_type = Enum
    possible_values = MeterStatus
    default_value = MeterStatus.none
    entity = WaterLicence
    definition_period = ETERNITY
    label = "Current meter installation status"
    reference = "Water Management (General) Regulation 2025, cl. 68"


class work_status(Variable):
    """
    Operational status of the water supply work.
    Inactive and unintended works are exempt from metering obligations.

    Inactive: works not currently used but may be reactivated.
    Unintended: works listed on an approval but not taking licensed water
    (decommissioned, not constructed, or not drawing from a water source).
    A licence condition prohibits using unintended works to take licensed water.

    Reference: Water Management (General) Regulation 2025, Schedule 7, Part 3
    """
    value_type = Enum
    possible_values = WorkStatus
    default_value = WorkStatus.active
    entity = WaterLicence
    definition_period = ETERNITY
    label = "Operational status of the water supply work"
    reference = "Water Management (General) Regulation 2025, Schedule 7, Part 3"


class is_trading_allocations(Variable):
    """
    Whether the licence holder is trading water allocations.
    Trading triggers mandatory metering even where the ≤15ML exemption
    would otherwise apply.
    Reference: Water Management (General) Regulation 2025, Schedule 7, Part 2
    """
    value_type = bool
    entity = WaterLicence
    definition_period = YEAR
    label = "Is the licence holder trading water allocations?"
    reference = "Water Management (General) Regulation 2025, Schedule 7, Part 2"


class is_single_work_on_property(Variable):
    """
    Whether this is the only bore or pump on the property.
    Affects size-based exemption thresholds:
      Single pump on property → exempt if <100mm (surface water)
      Single bore on property → exempt if <200mm (groundwater)
    Where multiple works exist on a property, different thresholds apply
    (see Schedule 7, Part 2 of the 2025 Regulation).
    Reference: Water Management (General) Regulation 2025, Schedule 7, Part 2
    """
    value_type = bool
    entity = WaterLicence
    definition_period = ETERNITY
    default_value = True
    label = "Is this the only pump or bore on the property?"
    reference = "Water Management (General) Regulation 2025, Schedule 7, Part 2"


# ── Calculated Variables ──────────────────────────────────────────────────────

class is_size_exempt(Variable):
    """
    Whether the works are exempt from metering due to size alone,
    irrespective of entitlement.

    Single surface water pump <100mm → exempt.
    Single groundwater bore <200mm → exempt.
    500mm or greater surface water pumps are NEVER size-exempt regardless
    of any other factor (cl. 75(2) of the 2025 Regulation).

    Note: Where there is more than one pump or bore on a property, different
    thresholds apply. This variable assumes single-work-on-property = True
    unless overridden. For multi-work properties, this variable should be
    reviewed manually against Schedule 7, Part 2.

    Reference: Water Management (General) Regulation 2025, cl. 73-75; Schedule 7
    """
    value_type = bool
    entity = WaterLicence
    definition_period = ETERNITY
    label = "Is the work exempt from metering due to size threshold?"
    reference = "Water Management (General) Regulation 2025, cl. 73-75; Schedule 7"

    def formula(water_licence, period, parameters):
        diameter = water_licence("pump_diameter_mm", period)
        licence = water_licence("licence_type", period)
        single_work = water_licence("is_single_work_on_property", period)

        is_groundwater = (licence == LicenceType.groundwater)
        is_surface = (
            (licence == LicenceType.surface_water) +
            (licence == LicenceType.interim)
        )

        # 500mm+ pumps are never exempt regardless of any other factor
        # (cl. 75(2): subsection (1) does not apply to pump ≥500mm)
        high_risk_pump = (diameter >= 500)

        # Single-work size exemptions
        surface_size_exempt = is_surface * single_work * (diameter < 100)
        groundwater_size_exempt = is_groundwater * single_work * (diameter < 200)

        size_exempt = (surface_size_exempt + groundwater_size_exempt) > 0

        # High-risk pumps override any size exemption
        return size_exempt * np.logical_not(high_risk_pump)


class compliance_tier(Variable):
    """
    Metering compliance tier under the 2025 dual-axis framework.

    Tier is determined by BOTH cumulative entitlement AND pump/bore diameter:

      not_applicable:
        - No water access licence, OR
        - Work is inactive or unintended

      exempt:
        - Work is size-exempt (single pump <100mm or single bore <200mm), AND
        - Cumulative entitlement ≤15ML, AND
        - Not trading water allocations

      tier_2_meter_only:
        - Not size-exempt or high-risk, AND
        - Cumulative entitlement >15ML and <100ML
        - Requires: pattern-approved AS4747 meter
        - Optional: DQP validation, LID, telemetry

      tier_3_full_compliance:
        - Pump diameter ≥500mm (high-risk works), OR
        - Cumulative entitlement ≥100ML
        - Requires: AS4747 meter + DQP validation + LID + telemetry

    Reference: Water Management (General) Regulation 2025, Part 5, Division 2;
               cl. 73-75; Schedule 7
    """
    value_type = Enum
    possible_values = ComplianceTier
    default_value = ComplianceTier.not_applicable
    entity = WaterLicence
    definition_period = YEAR
    label = "Metering compliance tier under the 2025 dual-axis framework"
    reference = "Water Management (General) Regulation 2025, Part 5, Division 2"

    def formula(water_licence, period, parameters):
        licence = water_licence("licence_type", period)
        diameter = water_licence("pump_diameter_mm", period)
        entitlement = water_licence("cumulative_entitlement_ml", period)
        status = water_licence("work_status", period)
        trading = water_licence("is_trading_allocations", period)
        size_exempt = water_licence("is_size_exempt", period)

        has_licence = (
            (licence == LicenceType.surface_water) +
            (licence == LicenceType.groundwater) +
            (licence == LicenceType.floodplain_harvesting) +
            (licence == LicenceType.interim)
        ) > 0

        work_is_active = (status == WorkStatus.active)

        # High-risk pump: ≥500mm, full Tier 3 regardless of entitlement
        high_risk_pump = (diameter >= 500)

        # Entitlement thresholds
        large_entitlement = (entitlement >= 100)       # ≥100ML → Tier 3
        mid_entitlement = (entitlement > 15) * (entitlement < 100)  # >15 and <100ML → Tier 2
        low_entitlement = (entitlement <= 15)          # ≤15ML → exempt (unless trading)

        # Low-volume exemption is overridden by trading
        low_volume_exempt = low_entitlement * np.logical_not(trading)

        # Tier 3: high-risk pump OR large entitlement
        is_tier_3 = has_licence * work_is_active * (high_risk_pump + large_entitlement)

        # Tier 2: not high-risk, mid entitlement
        is_tier_2 = (
            has_licence * work_is_active *
            np.logical_not(high_risk_pump) *
            mid_entitlement
        )

        # Exempt: size-exempt AND low volume AND not trading
        is_exempt = (
            has_licence * work_is_active *
            np.logical_not(high_risk_pump) *
            size_exempt *
            low_volume_exempt
        )

        # Not applicable: no licence OR inactive/unintended works
        is_not_applicable = np.logical_not(has_licence) + np.logical_not(work_is_active)

        return np.select(
            [
                is_not_applicable > 0,
                is_tier_3 > 0,
                is_tier_2 > 0,
                is_exempt > 0,
            ],
            [
                ComplianceTier.not_applicable,
                ComplianceTier.tier_3_full_compliance,
                ComplianceTier.tier_2_meter_only,
                ComplianceTier.exempt,
            ],
            default=ComplianceTier.exempt,
        )


class metering_required(Variable):
    """
    Whether a pattern-approved AS4747 meter is required for this licence.

    True for Tier 2 and Tier 3 works.
    False for exempt works and not-applicable works.

    Note: Even where metering_required is False, recording and reporting
    of water take remains mandatory under cl. 109 of the 2025 Regulation
    (records when using unmetered works).

    Reference: Water Management (General) Regulation 2025, cl. 68; Part 5, Division 2
    """
    value_type = bool
    entity = WaterLicence
    definition_period = YEAR
    label = "Is a pattern-approved AS4747 meter required?"
    reference = [
        "Water Management Act 2000, s.101A",
        "Water Management (General) Regulation 2025, cl. 68",
    ]

    def formula(water_licence, period, parameters):
        tier = water_licence("compliance_tier", period)
        return (
            (tier == ComplianceTier.tier_2_meter_only) +
            (tier == ComplianceTier.tier_3_full_compliance)
        ) > 0


class dqp_validation_required(Variable):
    """
    Whether installation must be validated by a Duly Qualified Person (DQP).

    Required for Tier 3 works only (≥100ML or ≥500mm pump).
    Optional for Tier 2 works (>15ML and <100ML).

    A DQP is an accredited meter installer under s.115B of the
    Water Management Act 2000 and cl. 93-96 of the 2025 Regulation.

    Reference: Water Management (General) Regulation 2025, cl. 93-96; Schedule 5
    """
    value_type = bool
    entity = WaterLicence
    definition_period = YEAR
    label = "Is DQP validation of meter installation required?"
    reference = [
        "Water Management Act 2000, s.115B",
        "Water Management (General) Regulation 2025, cl. 93-96; Schedule 5",
    ]

    def formula(water_licence, period, parameters):
        tier = water_licence("compliance_tier", period)
        return (tier == ComplianceTier.tier_3_full_compliance)


class telemetry_required(Variable):
    """
    Whether a Local Intelligence Device (LID) and telemetry connection
    to the NSW Data Acquisition Service (DAS) is required.

    Required for Tier 3 works only (≥100ML entitlement or ≥500mm pump).
    Optional for Tier 2 works (>15ML and <100ML).

    This variable is now DECOUPLED from metering_required. Under the 2018
    Regulation, telemetry tracked metering obligations. Under the 2025
    Regulation, telemetry is mandated only for Tier 3 — smaller works in
    Tier 2 must meter but may choose not to install a LID.

    Telemetry exemptions remain available where connectivity cannot be
    established (cl. 76, Ministerial exemption).

    Reference: Water Management (General) Regulation 2025, cl. 68; cl. 106;
               NSW Data Logging and Telemetry Specifications 2021
    """
    value_type = bool
    entity = WaterLicence
    definition_period = YEAR
    label = "Is LID/telemetry connection to the DAS required?"
    reference = [
        "Water Management (General) Regulation 2025, cl. 68; cl. 106",
        "NSW Data Logging and Telemetry Specifications 2021",
    ]

    def formula(water_licence, period, parameters):
        tier = water_licence("compliance_tier", period)
        return (tier == ComplianceTier.tier_3_full_compliance)


class compliance_deadline_year(Variable):
    """
    The year by which the required metering equipment must be installed.

    Deadlines under the Water Management (General) Regulation 2025:

      Tier 3 — inland (≥100ML or ≥500mm, inland regions):
        Deadline has passed — compliance required NOW.
        Represented as 2024 (pre-existing requirement carried forward).

      Tier 3 — coastal (≥100ML or ≥500mm pump, coastal region):
        1 December 2026.

      Tier 2 — all regions (>15ML and <100ML):
        1 December 2027, OR the works approval renewal date, whichever is first.
        This variable returns 2027; the renewal date must be checked separately.

      Exempt / not applicable:
        Returns 0 (no deadline applicable).

    Note: 500mm+ pumps anywhere in NSW were already required to be compliant
    before the 2025 Regulation. The 2025 Regulation did not change their deadline.

    Reference: Water Management (General) Regulation 2025, Part 5;
               Water Management (General) Regulation 2025, Schedule 7
    """
    value_type = int
    entity = WaterLicence
    definition_period = YEAR
    label = "Year by which metering equipment must be installed"
    reference = "Water Management (General) Regulation 2025, Part 5; Schedule 7"

    def formula(water_licence, period, parameters):
        tier = water_licence("compliance_tier", period)
        region = water_licence("water_region", period)

        is_tier_3 = (tier == ComplianceTier.tier_3_full_compliance)
        is_tier_2 = (tier == ComplianceTier.tier_2_meter_only)
        is_coastal = (region == WaterRegion.coastal)
        is_inland = np.logical_not(is_coastal)

        return np.select(
            [
                is_tier_3 * is_inland,    # Tier 3 inland — already overdue
                is_tier_3 * is_coastal,   # Tier 3 coastal — 1 Dec 2026
                is_tier_2,                # Tier 2 all regions — 1 Dec 2027
            ],
            [
                2024,   # Inland Tier 3 — compliance required now (pre-existing)
                2026,   # Coastal Tier 3 — 1 December 2026
                2027,   # Tier 2 — 1 December 2027 or works renewal (earlier applies)
            ],
            default=0,  # Exempt or not applicable — no deadline
        )


class revalidation_period_years(Variable):
    """
    The period in years after which meter installation must be revalidated
    by a DQP.

    Under the 2025 Regulation:
      - Initial revalidation: 10 years after installation
        (extended from 5 years under the 2018 Regulation)
      - Subsequent revalidations: every 5 years thereafter

    In-situ accuracy testing is no longer a mandatory revalidation requirement
    (removed to align with national AS4747 requirements).

    Only applies to Tier 3 works where DQP validation is required.
    Returns 0 for Tier 2 (DQP optional) and exempt/not-applicable works.

    Reference: Water Management (General) Regulation 2025, Schedule 5, cl. 6
    """
    value_type = int
    entity = WaterLicence
    definition_period = ETERNITY
    label = "Years between mandatory DQP revalidations (10 initial, 5 subsequent)"
    reference = "Water Management (General) Regulation 2025, Schedule 5, cl. 6"

    def formula(water_licence, period, parameters):
        tier = water_licence("compliance_tier", period)
        is_tier_3 = (tier == ComplianceTier.tier_3_full_compliance)
        # Returns the initial revalidation period (10 years).
        # Subsequent revalidation (5 years) must be tracked from installation date.
        return np.where(is_tier_3, 10, 0)


class metering_compliance_status(Variable):
    """
    Overall compliance status summary for this water licence.

    Returns one of:
      'compliant'            — works meet all requirements for their tier
      'action_required'      — meter must be installed by deadline
      'upgrade_required'     — existing meter must be upgraded to AS4747
      'lid_required'         — meter installed but LID/telemetry missing (Tier 3)
      'not_applicable'       — no licence, or inactive/unintended works
      'exempt'               — below size and volume thresholds

    Reference: Water Management Act 2000, s.101A;
               Water Management (General) Regulation 2025, Part 5
    """
    value_type = str
    entity = WaterLicence
    definition_period = YEAR
    label = "Overall metering compliance status"
    reference = [
        "Water Management Act 2000, s.101A",
        "Water Management (General) Regulation 2025, Part 5",
    ]

    def formula(water_licence, period, parameters):
        tier = water_licence("compliance_tier", period)
        meter_status = water_licence("current_meter_status", period)

        is_tier_3 = (tier == ComplianceTier.tier_3_full_compliance)
        is_tier_2 = (tier == ComplianceTier.tier_2_meter_only)
        is_exempt = (tier == ComplianceTier.exempt)
        is_not_applicable = (tier == ComplianceTier.not_applicable)

        has_approved_meter_with_lid = (
            meter_status == MeterStatus.pattern_approved_with_lid
        )
        has_approved_meter_no_lid = (
            meter_status == MeterStatus.pattern_approved_no_lid
        )
        has_non_approved_meter = (
            meter_status == MeterStatus.non_approved
        )
        has_no_meter = (
            meter_status == MeterStatus.none
        )

        # Tier 3: fully compliant only if AS4747 meter + LID installed
        tier_3_compliant = is_tier_3 * has_approved_meter_with_lid
        # Tier 3: meter OK but LID/telemetry missing
        tier_3_lid_missing = is_tier_3 * has_approved_meter_no_lid
        # Tier 3: old or no meter — needs upgrade or new install
        tier_3_upgrade = is_tier_3 * has_non_approved_meter
        tier_3_action = is_tier_3 * has_no_meter

        # Tier 2: compliant with any pattern-approved meter (LID optional)
        tier_2_compliant = is_tier_2 * (
            has_approved_meter_with_lid + has_approved_meter_no_lid
        )
        # Tier 2: old or no meter — needs upgrade or new install
        tier_2_upgrade = is_tier_2 * has_non_approved_meter
        tier_2_action = is_tier_2 * has_no_meter

        return np.select(
            [
                is_not_applicable > 0,
                is_exempt > 0,
                (tier_3_compliant + tier_2_compliant) > 0,
                tier_3_lid_missing > 0,
                (tier_3_upgrade + tier_2_upgrade) > 0,
                (tier_3_action + tier_2_action) > 0,
            ],
            [
                "not_applicable",
                "exempt",
                "compliant",
                "lid_required",
                "upgrade_required",
                "action_required",
            ],
            default="compliant",
        )
