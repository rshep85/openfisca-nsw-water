"""
Entities for the NSW Water OpenFisca package.

Builds on openfisca_nsw_base entities, adding water-specific
group entities (LandHolding, WaterLicence).

Reference: Water Management Act 2000 (NSW)
"""

from openfisca_core.entities import build_entity

# ── Person ──────────────────────────────────────────────────────────────────
# Represents an individual water user, licensee, or landholder.

Person = build_entity(
    key="person",
    plural="persons",
    label="Person",
    doc="An individual water user, licence holder, or land owner.",
    roles=[],
    is_person=True,
)

# ── LandHolding ─────────────────────────────────────────────────────────────
# A single cadastral parcel or aggregated landholding.
# Harvestable rights dam capacity is calculated at this level.

LandHolding = build_entity(
    key="land_holding",
    plural="land_holdings",
    label="Land Holding",
    doc=(
        "A rural landholding subject to NSW harvestable rights rules. "
        "Corresponds to a single property or group of properties under "
        "common ownership in a water sharing plan area. "
        "Reference: Water Management Act 2000 s.52"
    ),
    roles=[
        {
            "key": "owner",
            "plural": "owners",
            "label": "Owner / Occupier",
            "doc": "The person who owns or occupies the landholding.",
            "max": 1,
        }
    ],
)

# ── WaterLicence ─────────────────────────────────────────────────────────────
# A NSW water access licence, covering one or more extraction works.
# Metering compliance is calculated at this level.

WaterLicence = build_entity(
    key="water_licence",
    plural="water_licences",
    label="Water Licence",
    doc=(
        "A NSW water access licence (surface water or groundwater) issued "
        "under the Water Management Act 2000. Metering obligations, "
        "compliance deadlines, and entitlement calculations are assessed "
        "at this level. "
        "Reference: Water Management Act 2000 Part 2"
    ),
    roles=[
        {
            "key": "licence_holder",
            "plural": "licence_holders",
            "label": "Licence Holder",
            "doc": "The person who holds this water access licence.",
            "max": 1,
        }
    ],
)

# ── ControlledActivityApplication ───────────────────────────────────────────
# Represents a proposed activity on waterfront land.
# Permit eligibility / exemption is assessed at this level.

ControlledActivityApplication = build_entity(
    key="controlled_activity_application",
    plural="controlled_activity_applications",
    label="Controlled Activity Application",
    doc=(
        "A proposed activity on or near waterfront land in NSW. "
        "Used to determine whether a Controlled Activity Approval (CAA) "
        "is required or whether an exemption applies. "
        "Reference: Water Management Act 2000 s.91; "
        "Water Management (General) Regulation 2018 Schedule 3"
    ),
    roles=[
        {
            "key": "applicant",
            "plural": "applicants",
            "label": "Applicant",
            "doc": "The person proposing the controlled activity.",
            "max": 1,
        }
    ],
)

entities = [
    Person,
    LandHolding,
    WaterLicence,
    ControlledActivityApplication,
]
