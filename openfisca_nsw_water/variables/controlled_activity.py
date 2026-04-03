"""
Controlled Activity Approval (CAA) variables for NSW waterfront works.

Encodes the rules for determining whether a proposed activity on
waterfront land requires a Controlled Activity Approval or whether
an exemption applies.

Reference:
  - Water Management Act 2000, s.91 (controlled activities defined)
  - Water Management (General) Regulation 2018, Schedule 3 (exemptions)
  - NRAR Controlled Activity Approvals Guidelines
"""

import numpy as np
from openfisca_core.periods import ETERNITY, YEAR
from openfisca_core.variables import Variable
from openfisca_core.indexed_enums import Enum

from openfisca_nsw_water.entities import ControlledActivityApplication


# ── Enumerations ──────────────────────────────────────────────────────────────

class LocationCategory(Enum):
    """
    Distance of the proposed activity from a waterway or wetland.
    'Waterfront land' triggers controlled activity rules.
    Reference: Water Management Act 2000, s.91(1) — definition of waterfront land.
    """
    within_40m_river = "Within 40m of a river, stream or lake"
    within_40m_estuary = "Within 40m of an estuary or coastal wetland"
    outside_waterfront = "More than 40m from any waterway or wetland"
    unknown = "Distance not confirmed"


class ActivityType(Enum):
    """
    Category of proposed activity on or near the waterway.
    Reference: Water Management Act 2000, s.91(1)(a)-(e)
    """
    erect_structure = "Erecting, extending or altering a structure"
    vegetation_clearing = "Removing, cutting or clearing vegetation"
    fill_excavate = "Depositing material, filling or excavating"
    maintenance = "Maintenance of an existing approved structure"
    other = "Other activity"


class SpecialCircumstance(Enum):
    """
    Additional circumstances that may trigger exemptions or extra requirements.
    Reference: Water Management (General) Regulation 2018, Schedule 3
    """
    in_water = "Work physically in or over water"
    flood_plain = "Work on flood plain or floodway"
    emergency = "Emergency flood repair or maintenance"
    none = "None of the above"


class ActivityPurpose(Enum):
    """
    Purpose of the proposed activity.
    Some exemptions apply only to residential or agricultural activities.
    Reference: Water Management (General) Regulation 2018, Schedule 3, cl. 1-4
    """
    residential = "Residential / domestic"
    agricultural = "Agricultural / farming"
    commercial = "Commercial / industrial"
    public_infrastructure = "Public infrastructure or utilities"


# ── Input Variables ───────────────────────────────────────────────────────────

class activity_location(Variable):
    """
    Whether the proposed activity is on 'waterfront land'.
    This is the primary jurisdictional trigger for the CAA requirement.
    Reference: Water Management Act 2000, s.91(1) definition
    """
    value_type = Enum
    possible_values = LocationCategory
    default_value = LocationCategory.within_40m_river
    entity = ControlledActivityApplication
    definition_period = ETERNITY
    label = "Location of proposed activity relative to waterway"
    reference = "Water Management Act 2000, s.91(1)"


class activity_type(Variable):
    """
    The category of activity being proposed.
    Reference: Water Management Act 2000, s.91(1)(a)-(e)
    """
    value_type = Enum
    possible_values = ActivityType
    default_value = ActivityType.erect_structure
    entity = ControlledActivityApplication
    definition_period = ETERNITY
    label = "Type of proposed activity"
    reference = "Water Management Act 2000, s.91(1)(a)-(e)"


class special_circumstance(Variable):
    """
    Whether any special circumstance applies that may affect the exemption analysis.
    Reference: Water Management (General) Regulation 2018, Schedule 3
    """
    value_type = Enum
    possible_values = SpecialCircumstance
    default_value = SpecialCircumstance.none
    entity = ControlledActivityApplication
    definition_period = ETERNITY
    label = "Special circumstance affecting CAA requirement"
    reference = "Water Management (General) Regulation 2018, Schedule 3"


class activity_purpose(Variable):
    """
    The primary purpose of the proposed activity.
    Reference: Water Management (General) Regulation 2018, Schedule 3, cl. 1-4
    """
    value_type = Enum
    possible_values = ActivityPurpose
    default_value = ActivityPurpose.residential
    entity = ControlledActivityApplication
    definition_period = ETERNITY
    label = "Purpose of proposed activity"
    reference = "Water Management (General) Regulation 2018, Schedule 3, cl. 1-4"


# ── Calculated Variables ──────────────────────────────────────────────────────

class is_on_waterfront_land(Variable):
    """
    Whether the proposed activity is on 'waterfront land' as defined
    in the Water Management Act 2000 s.91(1).

    Waterfront land means land within:
      - 40m of the highest bank of a river or stream, or
      - 40m of the mean high-water mark of an estuary or coastal wetland.

    If the location is unknown, we conservatively treat it as waterfront land
    to ensure the user confirms before proceeding.

    Reference: Water Management Act 2000, s.91(1)
    """
    value_type = bool
    entity = ControlledActivityApplication
    definition_period = YEAR
    label = "Is the proposed activity on waterfront land?"
    reference = "Water Management Act 2000, s.91(1)"

    def formula(application, period, parameters):
        location = application("activity_location", period)
        return (
            (location == LocationCategory.within_40m_river) +
            (location == LocationCategory.within_40m_estuary) +
            (location == LocationCategory.unknown)  # conservative — assume yes if unknown
        )


class emergency_exemption_applies(Variable):
    """
    Whether the emergency flood works exemption applies.

    Emergency repair or maintenance to restore existing works to their
    pre-existing condition following a flood event is exempt from CAA
    requirements, provided:
      (a) the works are limited to restoring the pre-existing state, AND
      (b) NRAR is notified within 7 days of commencing works.

    Reference: Water Management (General) Regulation 2018, Schedule 3, cl. 8
    """
    value_type = bool
    entity = ControlledActivityApplication
    definition_period = YEAR
    label = "Does the emergency flood works exemption apply?"
    reference = "Water Management (General) Regulation 2018, Schedule 3, cl. 8"

    def formula(application, period, parameters):
        return (
            application("special_circumstance", period) == SpecialCircumstance.emergency
        )


class maintenance_exemption_applies(Variable):
    """
    Whether the routine maintenance exemption applies.

    Maintenance of an existing lawfully approved structure on waterfront
    land is exempt from CAA requirements, provided the works:
      (a) do not alter the structure, AND
      (b) do not expand the structure's footprint, AND
      (c) do not affect the flow of water.

    Reference: Water Management (General) Regulation 2018, Schedule 3, cl. 2
    """
    value_type = bool
    entity = ControlledActivityApplication
    definition_period = YEAR
    label = "Does the routine maintenance exemption apply?"
    reference = "Water Management (General) Regulation 2018, Schedule 3, cl. 2"

    def formula(application, period, parameters):
        is_maintenance = (
            application("activity_type", period) == ActivityType.maintenance
        )
        not_in_water = np.logical_not(
            application("special_circumstance", period) == SpecialCircumstance.in_water
        )
        return is_maintenance * not_in_water


class caa_exemption_applies(Variable):
    """
    Whether any exemption from the CAA requirement applies.

    An activity is exempt if:
      (a) It is not on waterfront land, OR
      (b) The emergency flood works exemption applies (Schedule 3 cl. 8), OR
      (c) The routine maintenance exemption applies (Schedule 3 cl. 2).

    Note: further exemptions exist in Schedule 3 (e.g. domestic/stock
    watering, minor fencing) but are not yet encoded in this version.

    Reference: Water Management (General) Regulation 2018, Schedule 3
    """
    value_type = bool
    entity = ControlledActivityApplication
    definition_period = YEAR
    label = "Is the activity exempt from requiring a CAA?"
    reference = "Water Management (General) Regulation 2018, Schedule 3"

    def formula(application, period, parameters):
        not_waterfront = np.logical_not(
            application("is_on_waterfront_land", period)
        )
        return (
            not_waterfront +
            application("emergency_exemption_applies", period) +
            application("maintenance_exemption_applies", period)
        )


class caa_required(Variable):
    """
    Whether a Controlled Activity Approval (CAA) is required before
    works may commence.

    A CAA is required when:
      (a) The activity is a 'controlled activity' under WMA 2000 s.91(1), AND
      (b) No exemption applies under Schedule 3 of the Regulation, AND
      (c) The activity is proposed on waterfront land.

    Commencing a controlled activity without a CAA is an offence under
    Water Management Act 2000 s.91A — maximum penalty $44,000 for
    an individual.

    Reference: Water Management Act 2000, s.91, s.91A
    """
    value_type = bool
    entity = ControlledActivityApplication
    definition_period = YEAR
    label = "Is a Controlled Activity Approval required?"
    reference = [
        "Water Management Act 2000, s.91",
        "Water Management Act 2000, s.91A (offence provision)",
        "Water Management (General) Regulation 2018, Schedule 3",
    ]

    def formula(application, period, parameters):
        on_waterfront = application("is_on_waterfront_land", period)
        not_exempt = np.logical_not(application("caa_exemption_applies", period))
        unknown_location = (
            application("activity_location", period) == LocationCategory.unknown
        )
        # If location is unknown, we cannot confirm exemption — flag as required
        return (on_waterfront * not_exempt) + unknown_location


class caa_outcome_code(Variable):
    """
    A string code summarising the CAA determination outcome.

    Codes:
      'not_waterfront'      — activity is outside waterfront land; no CAA needed
      'emergency_exempt'    — emergency flood works exemption applies
      'maintenance_exempt'  — routine maintenance exemption applies
      'location_unknown'    — location not confirmed; must verify before proceeding
      'caa_required'        — CAA must be obtained before works commence

    Reference: Water Management Act 2000, s.91; Schedule 3 of the Regulation
    """
    value_type = str
    entity = ControlledActivityApplication
    definition_period = YEAR
    label = "CAA outcome code"
    reference = "Water Management Act 2000, s.91"

    def formula(application, period, parameters):
        location = application("activity_location", period)
        emergency = application("emergency_exemption_applies", period)
        maintenance = application("maintenance_exemption_applies", period)
        caa_needed = application("caa_required", period)

        return np.select(
            [
                location == LocationCategory.outside_waterfront,
                emergency,
                maintenance,
                location == LocationCategory.unknown,
                caa_needed,
            ],
            [
                "not_waterfront",
                "emergency_exempt",
                "maintenance_exempt",
                "location_unknown",
                "caa_required",
            ],
            default="not_waterfront",
        )
