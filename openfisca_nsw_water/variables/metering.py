"""
Metering compliance variables for NSW water licences.

Encodes the NSW metering rules under:
  - Water Management Act 2000, Part 2, Division 3 (s.91I)
  - Water Management (General) Regulation 2018, Part 9 (cl. 174-180)
  - NSW Non-Urban Water Metering Policy (2019)

Variables are defined on the WaterLicence entity.
"""

import numpy as np
from openfisca_core.periods import ETERNITY, MONTH, YEAR
from openfisca_core.variables import Variable
from openfisca_core.indexed_enums import Enum

from openfisca_nsw_water.entities import WaterLicence


# ── Enumerations ─────────────────────────────────────────────────────────────

class LicenceType(Enum):
    """Type of NSW water access licence."""
    surface_water = "Surface water access licence"
    groundwater = "Groundwater access licence"
    interim = "Interim water access licence"
    none = "No water access licence"


class PumpDiameter(Enum):
    """
    Diameter category of the largest extraction works on the licence.
    Threshold is 100mm under cl. 174 of the Regulation.
    """
    small = "Less than 100mm"     # below threshold — lower priority tier
    medium = "100mm to 200mm"     # threshold tier — metering required
    large = "Greater than 200mm"  # large works — metering + telemetry required


class WaterRegion(Enum):
    """
    Water sharing plan region. Determines rollout phase and deadline.
    Reference: NSW Non-Urban Water Metering Policy, Appendix A.
    """
    murray_darling_regulated = "Murray-Darling Basin regulated rivers"
    coastal = "Coastal catchments"
    inland_unregulated = "Inland unregulated rivers"
    groundwater_mdb = "Murray-Darling Basin groundwater"


class MeterStatus(Enum):
    """Current metering status of the extraction works."""
    pattern_approved = "Pattern-approved meter installed"
    non_approved = "Older non-approved meter installed"
    none = "No meter installed"


# ── Input Variables ───────────────────────────────────────────────────────────

class licence_type(Variable):
    """
    The category of NSW water access licence held.
    Reference: Water Management Act 2000 s.55 (licence categories)
    """
    value_type = Enum
    possible_values = LicenceType
    default_value = LicenceType.surface_water
    entity = WaterLicence
    definition_period = ETERNITY
    label = "Type of water access licence"
    reference = "Water Management Act 2000, s.55"


class pump_diameter_category(Variable):
    """
    Diameter category of the largest pump or extraction works.
    This is the primary trigger for metering obligations.
    Reference: Water Management (General) Regulation 2018, cl. 174
    """
    value_type = Enum
    possible_values = PumpDiameter
    default_value = PumpDiameter.medium
    entity = WaterLicence
    definition_period = ETERNITY
    label = "Pump/works diameter category"
    reference = "Water Management (General) Regulation 2018, cl. 174"


class water_region(Variable):
    """
    The water sharing plan region covering the extraction works.
    Determines the compliance deadline phase.
    Reference: NSW Non-Urban Water Metering Policy (2019), Appendix A
    """
    value_type = Enum
    possible_values = WaterRegion
    default_value = WaterRegion.murray_darling_regulated
    entity = WaterLicence
    definition_period = ETERNITY
    label = "Water sharing plan region"
    reference = "NSW Non-Urban Water Metering Policy 2019, Appendix A"


class current_meter_status(Variable):
    """
    Current installation status of metering equipment at the works.
    Reference: Water Management (General) Regulation 2018, cl. 175
    """
    value_type = Enum
    possible_values = MeterStatus
    default_value = MeterStatus.none
    entity = WaterLicence
    definition_period = ETERNITY
    label = "Current meter installation status"
    reference = "Water Management (General) Regulation 2018, cl. 175"


# ── Calculated Variables ──────────────────────────────────────────────────────

class metering_required(Variable):
    """
    Whether a pattern-approved meter is required for this water licence.

    A licence holder must install a pattern-approved meter if:
      (a) they hold a surface water or groundwater access licence, AND
      (b) their extraction works have a pump diameter >= 100mm, AND
      (c) they do not already have a pattern-approved meter installed.

    Reference: Water Management Act 2000 s.91I;
               Water Management (General) Regulation 2018 cl. 174-176
    """
    value_type = bool
    entity = WaterLicence
    definition_period = YEAR
    label = "Is a pattern-approved meter required?"
    reference = [
        "Water Management Act 2000, s.91I",
        "Water Management (General) Regulation 2018, cl. 174",
    ]

    def formula(water_licence, period, parameters):
        has_licence = (
            (water_licence("licence_type", period) == LicenceType.surface_water) +
            (water_licence("licence_type", period) == LicenceType.groundwater) +
            (water_licence("licence_type", period) == LicenceType.interim)
        )

        pump_is_above_threshold = (
            (water_licence("pump_diameter_category", period) == PumpDiameter.medium) +
            (water_licence("pump_diameter_category", period) == PumpDiameter.large)
        )

        already_compliant = (
            water_licence("current_meter_status", period) == MeterStatus.pattern_approved
        )

        return has_licence * pump_is_above_threshold * np.logical_not(already_compliant)


class telemetry_required(Variable):
    """
    Whether real-time telemetry is required in addition to a meter.

    Telemetry is required for extraction works with a pump > 200mm diameter
    in regulated river and groundwater systems.

    Reference: NSW Non-Urban Water Metering Policy (2019), Section 4.3
    """
    value_type = bool
    entity = WaterLicence
    definition_period = YEAR
    label = "Is telemetry required in addition to a meter?"
    reference = "NSW Non-Urban Water Metering Policy 2019, s.4.3"

    def formula(water_licence, period, parameters):
        large_pump = (
            water_licence("pump_diameter_category", period) == PumpDiameter.large
        )

        regulated_system = (
            (water_licence("water_region", period) == WaterRegion.murray_darling_regulated) +
            (water_licence("water_region", period) == WaterRegion.groundwater_mdb)
        )

        return large_pump * regulated_system


class compliance_deadline_year(Variable):
    """
    The year by which a pattern-approved meter must be installed.

    Deadlines vary by water sharing plan region, reflecting the phased
    rollout of the NSW metering reforms.

    Reference: NSW Non-Urban Water Metering Policy (2019), Appendix A
    """
    value_type = int
    entity = WaterLicence
    definition_period = YEAR
    label = "Year by which meter installation must be complete"
    reference = "NSW Non-Urban Water Metering Policy 2019, Appendix A"

    def formula(water_licence, period, parameters):
        region = water_licence("water_region", period)

        # Phased rollout deadlines by region
        return np.select(
            [
                region == WaterRegion.murray_darling_regulated,
                region == WaterRegion.groundwater_mdb,
                region == WaterRegion.coastal,
                region == WaterRegion.inland_unregulated,
            ],
            [
                2024,   # MDB regulated — first phase
                2025,   # MDB groundwater — second phase
                2025,   # Coastal — second phase
                2026,   # Inland unregulated — third phase
            ],
            default=2026,
        )


class metering_compliance_status(Variable):
    """
    Overall compliance status summary for this water licence.

    Returns one of:
      'compliant'       — no action required
      'action_required' — meter must be installed by deadline
      'upgrade_required' — existing meter must be upgraded
      'not_applicable'  — no licence or works below threshold

    Reference: Water Management Act 2000 s.91I
    """
    value_type = str
    entity = WaterLicence
    definition_period = YEAR
    label = "Overall metering compliance status"
    reference = "Water Management Act 2000, s.91I"

    def formula(water_licence, period, parameters):
        no_licence = (
            water_licence("licence_type", period) == LicenceType.none
        )
        small_pump = (
            water_licence("pump_diameter_category", period) == PumpDiameter.small
        )
        pattern_approved = (
            water_licence("current_meter_status", period) == MeterStatus.pattern_approved
        )
        old_meter = (
            water_licence("current_meter_status", period) == MeterStatus.non_approved
        )
        meter_required = water_licence("metering_required", period)

        return np.select(
            [
                no_licence + small_pump,        # not applicable
                pattern_approved,               # already compliant
                meter_required * old_meter,     # needs upgrade
                meter_required,                 # needs new meter
            ],
            [
                "not_applicable",
                "compliant",
                "upgrade_required",
                "action_required",
            ],
            default="compliant",
        )
