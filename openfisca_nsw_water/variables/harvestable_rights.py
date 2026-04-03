"""
Harvestable rights dam capacity variables.

Encodes the formula for calculating the maximum volume of water a
rural landholder may capture in farm dams under harvestable rights,
without requiring a water access licence.

Reference:
  - Water Management Act 2000, s.52 (harvestable rights)
  - Water Management (General) Regulation 2018, cl. 43-48
  - Water Sharing Plans (applicable to each catchment)
  - WaterNSW Harvestable Rights Technical Manual
"""

import numpy as np
from openfisca_core.periods import ETERNITY, YEAR
from openfisca_core.variables import Variable
from openfisca_core.indexed_enums import Enum

from openfisca_nsw_water.entities import LandHolding


# ── Enumerations ──────────────────────────────────────────────────────────────

class RainfallZone(Enum):
    """
    Annual rainfall zone for the landholding.
    The harvestable rights factor (and resulting dam capacity allowance)
    increases with rainfall, reflecting greater runoff potential.

    Reference: Water Management (General) Regulation 2018, Schedule 1
               (Harvestable Rights — rainfall zone factors)
    """
    arid = "Less than 400mm per year (arid)"
    low = "400mm to 600mm per year (low)"
    medium = "600mm to 800mm per year (medium)"
    high = "800mm to 1000mm per year (high)"
    very_high = "Greater than 1000mm per year (very high)"


class CatchmentType(Enum):
    """
    Whether the property is in a regulated or unregulated catchment.
    Properties within 3km of a regulated river may face additional
    restrictions regardless of harvestable rights.

    Reference: Water Management Act 2000, s.52(3)
    """
    unregulated = "Unregulated catchment"
    regulated = "Regulated river catchment"
    within_3km_regulated = "Within 3km of a regulated river"


# ── Parameters ────────────────────────────────────────────────────────────────
# In a full OpenFisca package these would live in parameters/ YAML files
# so they can be updated without changing code. Shown inline here for clarity.

# Harvestable rights factors (ML per hectare) by rainfall zone.
# These represent the approximate volumetric entitlement rate.
# Reference: Water Management (General) Regulation 2018, Schedule 1
HARVESTABLE_FACTORS = {
    RainfallZone.arid: 2.5,
    RainfallZone.low: 3.5,
    RainfallZone.medium: 5.0,
    RainfallZone.high: 6.2,
    RainfallZone.very_high: 7.2,
}


# ── Input Variables ───────────────────────────────────────────────────────────

class land_area_hectares(Variable):
    """
    Total area of the landholding in hectares.
    This is used directly in the harvestable rights formula.
    Reference: Water Management (General) Regulation 2018, cl. 43
    """
    value_type = float
    entity = LandHolding
    definition_period = ETERNITY
    label = "Total area of the landholding (hectares)"
    reference = "Water Management (General) Regulation 2018, cl. 43"


class rainfall_zone(Variable):
    """
    Annual rainfall zone in which the landholding is located.
    Determines the harvestable rights factor applied in the formula.
    Reference: Water Management (General) Regulation 2018, Schedule 1
    """
    value_type = Enum
    possible_values = RainfallZone
    default_value = RainfallZone.medium
    entity = LandHolding
    definition_period = ETERNITY
    label = "Annual rainfall zone"
    reference = "Water Management (General) Regulation 2018, Schedule 1"


class catchment_type(Variable):
    """
    Whether the property is in a regulated catchment or within 3km
    of a regulated river. This may trigger additional restrictions.
    Reference: Water Management Act 2000, s.52(3)
    """
    value_type = Enum
    possible_values = CatchmentType
    default_value = CatchmentType.unregulated
    entity = LandHolding
    definition_period = ETERNITY
    label = "Catchment type for the landholding"
    reference = "Water Management Act 2000, s.52(3)"


class existing_dam_volume_ml(Variable):
    """
    Total volume (in megalitres) of all existing farm dams on the property.
    This is deducted from the maximum harvestable rights entitlement
    to determine remaining capacity available for new dams.
    Reference: Water Management (General) Regulation 2018, cl. 44
    """
    value_type = float
    default_value = 0.0
    entity = LandHolding
    definition_period = ETERNITY
    label = "Volume of existing farm dams on the property (ML)"
    reference = "Water Management (General) Regulation 2018, cl. 44"


# ── Calculated Variables ──────────────────────────────────────────────────────

class harvestable_rights_factor(Variable):
    """
    The volumetric factor (ML/ha) that applies to this landholding,
    based on its rainfall zone.

    This factor, multiplied by the land area, gives the maximum total
    dam storage volume the landholder is entitled to under harvestable rights.

    Reference: Water Management (General) Regulation 2018, Schedule 1
    """
    value_type = float
    entity = LandHolding
    definition_period = YEAR
    label = "Harvestable rights factor (ML per hectare)"
    reference = "Water Management (General) Regulation 2018, Schedule 1"

    def formula(land_holding, period, parameters):
        zone = land_holding("rainfall_zone", period)

        return np.select(
            [
                zone == RainfallZone.arid,
                zone == RainfallZone.low,
                zone == RainfallZone.medium,
                zone == RainfallZone.high,
                zone == RainfallZone.very_high,
            ],
            [
                HARVESTABLE_FACTORS[RainfallZone.arid],
                HARVESTABLE_FACTORS[RainfallZone.low],
                HARVESTABLE_FACTORS[RainfallZone.medium],
                HARVESTABLE_FACTORS[RainfallZone.high],
                HARVESTABLE_FACTORS[RainfallZone.very_high],
            ],
            default=HARVESTABLE_FACTORS[RainfallZone.medium],
        )


class maximum_harvestable_dam_capacity_ml(Variable):
    """
    The maximum total volume of farm dams permitted on this landholding
    under harvestable rights, without a water access licence.

    Formula:
      max_capacity (ML) = land_area (ha) × harvestable_rights_factor (ML/ha)

    This is the GROSS entitlement — existing dam volumes must be
    subtracted to determine the REMAINING capacity available.

    Reference: Water Management Act 2000, s.52;
               Water Management (General) Regulation 2018, cl. 43
    """
    value_type = float
    entity = LandHolding
    definition_period = YEAR
    label = "Maximum total farm dam capacity under harvestable rights (ML)"
    reference = [
        "Water Management Act 2000, s.52",
        "Water Management (General) Regulation 2018, cl. 43",
    ]

    def formula(land_holding, period, parameters):
        area = land_holding("land_area_hectares", period)
        factor = land_holding("harvestable_rights_factor", period)
        return np.round(area * factor, 2)


class remaining_dam_capacity_ml(Variable):
    """
    The remaining volume of farm dam storage the landholder may still
    develop under harvestable rights, after accounting for existing dams.

    Formula:
      remaining (ML) = max_capacity (ML) - existing_dam_volume (ML)

    A negative result means existing dams already exceed the harvestable
    rights limit — this should be investigated with WaterNSW.

    Reference: Water Management (General) Regulation 2018, cl. 44
    """
    value_type = float
    entity = LandHolding
    definition_period = YEAR
    label = "Remaining dam capacity available under harvestable rights (ML)"
    reference = "Water Management (General) Regulation 2018, cl. 44"

    def formula(land_holding, period, parameters):
        max_cap = land_holding("maximum_harvestable_dam_capacity_ml", period)
        existing = land_holding("existing_dam_volume_ml", period)
        return np.round(max_cap - existing, 2)


class regulated_river_restriction_applies(Variable):
    """
    Whether additional restrictions apply because the property is within
    3km of a regulated river.

    Properties within 3km of a regulated river in a regulated catchment
    may require additional approval for new dams regardless of harvestable
    rights entitlement, particularly if the dam could intercept regulated
    river flows.

    Reference: Water Management Act 2000, s.52(3)
    """
    value_type = bool
    entity = LandHolding
    definition_period = YEAR
    label = "Do regulated river proximity restrictions apply?"
    reference = "Water Management Act 2000, s.52(3)"

    def formula(land_holding, period, parameters):
        catchment = land_holding("catchment_type", period)
        return catchment == CatchmentType.within_3km_regulated
