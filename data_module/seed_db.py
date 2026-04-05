"""
NSW Water — Data Module: Database Seeder
========================================
Builds the local SQLite database from embedded reference data and any
previously fetched raw data files in data/raw/.

Run this first before using the API or refresh scripts.

Usage:
    python seed_db.py

Output:
    data/db/nsw_water.db
"""

import sqlite3
import json
import os
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "db" / "nsw_water.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_schema(conn):
    conn.executescript("""
    -- ── WATER SOURCES ────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS water_sources (
        id                  TEXT PRIMARY KEY,   -- e.g. 'murrumbidgee_regulated'
        name                TEXT NOT NULL,
        water_sharing_plan  TEXT,
        source_type         TEXT NOT NULL,      -- regulated_river | unregulated_river | groundwater
        region              TEXT NOT NULL,      -- inland_regulated | inland_unregulated | coastal
        basin               TEXT,               -- e.g. 'murray_darling'
        state_area          TEXT,               -- e.g. 'southern_inland'
        total_share_ml      REAL,               -- total share component (ML) if known
        licence_count       INTEGER,            -- approximate number of licences
        notes               TEXT,
        data_source         TEXT DEFAULT 'embedded',
        last_updated        TEXT
    );

    -- ── LICENCE CATEGORIES ────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS licence_categories (
        id                  TEXT PRIMARY KEY,   -- e.g. 'general_security'
        name                TEXT NOT NULL,
        wma_section         TEXT,               -- e.g. 's.56'
        description         TEXT,
        reliability         TEXT,               -- high | medium | low | variable
        metering_tier       TEXT,               -- typically tier_3 | tier_2 | variable
        attestation_tier    TEXT,               -- T1 | T2 | T3 (ObligateIQ)
        tradeable           INTEGER DEFAULT 1,  -- boolean
        notes               TEXT
    );

    -- ── LICENCE CATEGORY × WATER SOURCE (share component) ────────────────────
    CREATE TABLE IF NOT EXISTS source_licence_shares (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        water_source_id         TEXT REFERENCES water_sources(id),
        licence_category_id     TEXT REFERENCES licence_categories(id),
        water_year              TEXT,           -- e.g. '2023-24'
        share_component_ml      REAL,           -- share component (entitlement ML)
        allocation_pct          REAL,           -- available water determination %
        usage_ml                REAL,
        utilisation_pct         REAL,
        data_source             TEXT DEFAULT 'embedded',
        last_updated            TEXT,
        UNIQUE(water_source_id, licence_category_id, water_year)
    );

    -- ── ALLOCATION TRADES (71T) ───────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS allocation_trades (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_id            TEXT UNIQUE,        -- DCCEEW trade reference
        water_source_id     TEXT REFERENCES water_sources(id),
        licence_category_id TEXT REFERENCES licence_categories(id),
        trade_date          TEXT,               -- ISO date
        water_year          TEXT,               -- e.g. '2023-24'
        volume_ml           REAL,
        price_per_ml        REAL,
        trade_type          TEXT,               -- temporary | permanent
        zone                TEXT,
        data_source         TEXT DEFAULT 'embedded',
        last_updated        TEXT
    );

    -- ── ENTITLEMENT TRADES (71Q) ──────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS entitlement_trades (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_id            TEXT UNIQUE,
        water_source_id     TEXT REFERENCES water_sources(id),
        licence_category_id TEXT REFERENCES licence_categories(id),
        trade_date          TEXT,
        water_year          TEXT,
        volume_ml           REAL,
        price_per_ml        REAL,
        trade_type          TEXT,               -- assignment_of_rights | transfer_of_shares
        data_source         TEXT DEFAULT 'embedded',
        last_updated        TEXT
    );

    -- ── GAUGE SITES (real-time monitoring) ───────────────────────────────────
    CREATE TABLE IF NOT EXISTS gauge_sites (
        site_id             TEXT PRIMARY KEY,   -- WaterNSW site number e.g. '421001'
        name                TEXT NOT NULL,
        water_source_id     TEXT REFERENCES water_sources(id),
        region              TEXT,
        latitude            REAL,
        longitude           REAL,
        site_type           TEXT,               -- river | dam | groundwater
        primary_variable    TEXT,               -- level | discharge | storage
        active              INTEGER DEFAULT 1,
        data_source         TEXT DEFAULT 'embedded',
        last_updated        TEXT
    );

    -- ── GAUGE READINGS (time series, fetched by refresh script) ─────────────
    CREATE TABLE IF NOT EXISTS gauge_readings (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        site_id             TEXT REFERENCES gauge_sites(site_id),
        timestamp           TEXT NOT NULL,
        variable            TEXT NOT NULL,      -- e.g. '141.00' (discharge ML/d)
        value               REAL,
        quality_code        INTEGER,            -- 10=Good 20=Fair 30=Poor 60=Estimate
        data_source         TEXT DEFAULT 'realtimedata_api',
        fetched_at          TEXT,
        UNIQUE(site_id, timestamp, variable)
    );

    -- ── WATER SHARING PLANS ───────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS water_sharing_plans (
        id                  TEXT PRIMARY KEY,   -- e.g. 'wsp_murrumbidgee_reg_2016'
        name                TEXT NOT NULL,
        water_source_id     TEXT REFERENCES water_sources(id),
        commenced           TEXT,               -- ISO date
        expires             TEXT,
        gazette_url         TEXT,
        status              TEXT DEFAULT 'in_force',
        notes               TEXT
    );

    -- ── METERING COMPLIANCE POPULATION ────────────────────────────────────────
    -- Aggregated counts by region/tier for policy simulation
    CREATE TABLE IF NOT EXISTS metering_population (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        region              TEXT NOT NULL,
        compliance_tier     TEXT NOT NULL,      -- tier_3 | tier_2 | exempt
        licence_count       INTEGER,
        estimated_share_ml  REAL,
        compliance_deadline TEXT,               -- ISO date
        compliant_count     INTEGER,            -- known compliant (from DQP portal)
        notes               TEXT,
        data_source         TEXT DEFAULT 'embedded',
        last_updated        TEXT,
        UNIQUE(region, compliance_tier)
    );

    -- ── METADATA / REFRESH LOG ────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS refresh_log (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name      TEXT NOT NULL,
        data_source     TEXT NOT NULL,
        rows_upserted   INTEGER,
        status          TEXT,           -- success | error
        message         TEXT,
        run_at          TEXT NOT NULL
    );
    """)
    conn.commit()
    print("✓ Schema created")


# ── WATER SOURCES ──────────────────────────────────────────────────────────────
# Sources drawn from:
#   - NSW Water Sharing Plans (legislation.nsw.gov.au)
#   - DCCEEW Water Source data (SEED portal)
#   - WaterNSW public register regions
#   - NRAR compliance population figures (4,287 licences total per strategic brief)

WATER_SOURCES = [
    # ── MURRAY-DARLING BASIN — REGULATED RIVERS ──
    {
        "id": "murrumbidgee_regulated",
        "name": "Murrumbidgee Regulated River",
        "water_sharing_plan": "Water Sharing Plan for the Murrumbidgee Regulated River Water Source 2016",
        "source_type": "regulated_river",
        "region": "inland_regulated",
        "basin": "murray_darling",
        "state_area": "southern_inland",
        "total_share_ml": 1_980_000,
        "licence_count": 1842,
        "notes": "Largest regulated river by share component in NSW. Predominantly general security and high security licences.",
    },
    {
        "id": "murray_regulated",
        "name": "Murray Regulated River",
        "water_sharing_plan": "Water Sharing Plan for the New South Wales Murray and Lower Darling Regulated Rivers Water Sources 2016",
        "source_type": "regulated_river",
        "region": "inland_regulated",
        "basin": "murray_darling",
        "state_area": "southern_inland",
        "total_share_ml": 1_540_000,
        "licence_count": 612,
        "notes": "Murray regulated river; includes Lower Darling. High proportion of high security irrigation licences.",
    },
    {
        "id": "macquarie_regulated",
        "name": "Macquarie and Cudgegong Regulated Rivers",
        "water_sharing_plan": "Water Sharing Plan for the Macquarie and Cudgegong Regulated Rivers Water Source 2011",
        "source_type": "regulated_river",
        "region": "inland_regulated",
        "basin": "murray_darling",
        "state_area": "northern_inland",
        "total_share_ml": 520_000,
        "licence_count": 487,
        "notes": "Macquarie Valley — significant cotton irrigation. Burrendong Dam storage.",
    },
    {
        "id": "namoi_regulated",
        "name": "Namoi Regulated River",
        "water_sharing_plan": "Water Sharing Plan for the Namoi Regulated River Water Source 2016",
        "source_type": "regulated_river",
        "region": "inland_regulated",
        "basin": "murray_darling",
        "state_area": "northern_inland",
        "total_share_ml": 395_000,
        "licence_count": 342,
        "notes": "Cotton and mixed farming. Keepit Dam and Split Rock Dam.",
    },
    {
        "id": "gwydir_regulated",
        "name": "Gwydir Regulated River",
        "water_sharing_plan": "Water Sharing Plan for the Gwydir Regulated River Water Source 2016",
        "source_type": "regulated_river",
        "region": "inland_regulated",
        "basin": "murray_darling",
        "state_area": "northern_inland",
        "total_share_ml": 340_000,
        "licence_count": 278,
        "notes": "Copeton Dam. Significant floodplain harvesting activity.",
    },
    {
        "id": "lachlan_regulated",
        "name": "Lachlan Regulated River",
        "water_sharing_plan": "Water Sharing Plan for the Lachlan Regulated River Water Source 2016",
        "source_type": "regulated_river",
        "region": "inland_regulated",
        "basin": "murray_darling",
        "state_area": "southern_inland",
        "total_share_ml": 380_000,
        "licence_count": 321,
        "notes": "Wyangala Dam. Mixed irrigation and stock/domestic.",
    },
    {
        "id": "hunter_regulated",
        "name": "Hunter Regulated River",
        "water_sharing_plan": "Water Sharing Plan for the Hunter Regulated River Water Source 2016",
        "source_type": "regulated_river",
        "region": "coastal",
        "basin": None,
        "state_area": "hunter",
        "total_share_ml": 285_000,
        "licence_count": 389,
        "notes": "Only major regulated coastal river system. Glenbawn and Glennies Creek Dams.",
    },
    # ── INLAND UNREGULATED ──
    {
        "id": "namoi_unregulated",
        "name": "Namoi Unregulated Rivers",
        "water_sharing_plan": "Water Sharing Plan for the Namoi Unregulated and Alluvial Water Sources 2019",
        "source_type": "unregulated_river",
        "region": "inland_unregulated",
        "basin": "murray_darling",
        "state_area": "northern_inland",
        "total_share_ml": 42_000,
        "licence_count": 198,
        "notes": "Covers unregulated tributaries across the Namoi catchment.",
    },
    {
        "id": "barwon_darling_unregulated",
        "name": "Barwon-Darling Unregulated River",
        "water_sharing_plan": "Water Sharing Plan for the Barwon-Darling Unregulated and Alluvial Water Sources 2012",
        "source_type": "unregulated_river",
        "region": "inland_unregulated",
        "basin": "murray_darling",
        "state_area": "far_west",
        "total_share_ml": 58_000,
        "licence_count": 143,
        "notes": "Highly variable flows. Significant floodplain activity in wet years.",
    },
    # ── GROUNDWATER ──
    {
        "id": "namoi_alluvial_groundwater",
        "name": "Namoi Alluvial Groundwater",
        "water_sharing_plan": "Water Sharing Plan for the Namoi Unregulated and Alluvial Water Sources 2019",
        "source_type": "groundwater",
        "region": "inland_unregulated",
        "basin": "murray_darling",
        "state_area": "northern_inland",
        "total_share_ml": 89_000,
        "licence_count": 412,
        "notes": "Porous rock and alluvial aquifers. Extraction limit tracked by DCCEEW.",
    },
    {
        "id": "murray_darling_deep_groundwater",
        "name": "Murray-Darling Basin Deep Groundwater",
        "water_sharing_plan": "Various WSPs (porous rock sources)",
        "source_type": "groundwater",
        "region": "inland_unregulated",
        "basin": "murray_darling",
        "state_area": "southern_inland",
        "total_share_ml": 125_000,
        "licence_count": 263,
        "notes": "Porous rock aquifers. Includes Lachlan and Murray deep groundwater sources.",
    },
    # ── COASTAL ──
    {
        "id": "north_coast_unregulated",
        "name": "North Coast Unregulated Rivers",
        "water_sharing_plan": "Various North Coast WSPs (Richmond, Tweed, Clarence, etc.)",
        "source_type": "unregulated_river",
        "region": "coastal",
        "basin": None,
        "state_area": "north_coast",
        "total_share_ml": 47_000,
        "licence_count": 389,
        "notes": "Multiple WSPs covering far north coast rivers. Coastal deadline 1 Dec 2026.",
    },
    {
        "id": "south_coast_unregulated",
        "name": "South Coast Unregulated Rivers",
        "water_sharing_plan": "Various South Coast WSPs (Shoalhaven, Moruya, etc.)",
        "source_type": "unregulated_river",
        "region": "coastal",
        "basin": None,
        "state_area": "south_coast",
        "total_share_ml": 18_000,
        "licence_count": 176,
        "notes": "Lower entitlements, mixed rural and semi-rural uses.",
    },
]


# ── LICENCE CATEGORIES ─────────────────────────────────────────────────────────
# Reference: Water Management Act 2000 s.56, s.57, s.60A

LICENCE_CATEGORIES = [
    {
        "id": "general_security",
        "name": "General Security",
        "wma_section": "s.56(1)(b)",
        "description": "Access to a share of the available water in the water source after high security entitlements are met. Allocation varies year to year based on storage and catchment conditions. Most common licence type in NSW.",
        "reliability": "medium",
        "metering_tier": "tier_3",
        "attestation_tier": "T1",
        "tradeable": 1,
        "notes": "Typically 0.1–1.1 ML/unit share AWD. Metered with telemetry for ≥100ML works.",
    },
    {
        "id": "high_security",
        "name": "High Security",
        "wma_section": "s.56(1)(a)",
        "description": "Priority access before general security. Used for permanent plantings, town water supply, critical industries. Usually receives near-full allocation even in dry years.",
        "reliability": "high",
        "metering_tier": "tier_3",
        "attestation_tier": "T1",
        "tradeable": 1,
        "notes": "Highest priority in AWD process. Commands premium market price.",
    },
    {
        "id": "supplementary",
        "name": "Supplementary Water",
        "wma_section": "s.56(1)(c)",
        "description": "Access to surplus flows announced by WaterNSW when water is spilling or not able to be stored. Windows are event-based and time-limited. Typically 1 ML/unit share at 100% allocation.",
        "reliability": "variable",
        "metering_tier": "tier_3",
        "attestation_tier": "T1",
        "tradeable": 1,
        "notes": "Timing verification cross-referenced against WaterNSW announcement records. Strong T1 case.",
    },
    {
        "id": "floodplain_harvesting",
        "name": "Floodplain Harvesting",
        "wma_section": "s.60A",
        "description": "Licences for capturing overland flows during flood events into on-farm storages. Commenced 2021. Volume measurement relies on storage surveys and inflow modelling — structurally estimated.",
        "reliability": "variable",
        "metering_tier": "variable",
        "attestation_tier": "T2",
        "tradeable": 0,
        "notes": "Central data integrity gap in NSW water compliance. Storage survey methodology declared, satellite cross-check partially available. Cannot achieve T1 without independent volume verification.",
    },
    {
        "id": "local_water_utility",
        "name": "Local Water Utility",
        "wma_section": "s.56(1)(d)",
        "description": "Held by local councils and water utilities for town water supply purposes.",
        "reliability": "high",
        "metering_tier": "tier_3",
        "attestation_tier": "T1",
        "tradeable": 0,
        "notes": "Non-transferable. Bulk supply to reticulated networks.",
    },
    {
        "id": "domestic_stock",
        "name": "Domestic and Stock",
        "wma_section": "s.52 / s.55",
        "description": "Small entitlements for household and livestock watering. Low entitlement volumes — typically exempt from mandatory metering under the 2025 Regulation.",
        "reliability": "high",
        "metering_tier": "exempt",
        "attestation_tier": "T3",
        "tradeable": 0,
        "notes": "Most fall below 15ML threshold. Recording and reporting still mandatory. Unmetered = T3 attestation.",
    },
    {
        "id": "environmental",
        "name": "Held Environmental Water",
        "wma_section": "s.8",
        "description": "Water held by the Commonwealth or NSW Environmental Water Holder for environmental purposes — releasing flows to support river health, wetlands, and ecosystems.",
        "reliability": "high",
        "metering_tier": "tier_3",
        "attestation_tier": "T1",
        "tradeable": 1,
        "notes": "Environmental water trades tracked by DCCEEW. High transparency requirements.",
    },
    {
        "id": "aquifer_access",
        "name": "Aquifer Access Licence",
        "wma_section": "s.56(1)(e)",
        "description": "Access to water stored in groundwater aquifers. Includes both alluvial and fractured rock aquifer sources.",
        "reliability": "medium",
        "metering_tier": "variable",
        "attestation_tier": "T1",
        "tradeable": 1,
        "notes": "Single bores <200mm may be exempt. ≥200mm bores with ≥100ML = Tier 3 full compliance.",
    },
]


# ── METERING COMPLIANCE POPULATION ────────────────────────────────────────────
# Source: DCCEEW metering review figures + NRAR compliance data
# Total NSW licences: ~4,287 (per strategic brief)
# MDB regulated: ~1,842 | Coastal: ~1,205 | Inland unregulated: ~1,240

METERING_POPULATION = [
    # INLAND REGULATED — Tier 3 (≥100ML or ≥500mm): already overdue
    {
        "region": "inland_regulated",
        "compliance_tier": "tier_3",
        "licence_count": 1842,
        "estimated_share_ml": 4_155_000,
        "compliance_deadline": "2024-01-01",
        "compliant_count": None,
        "notes": "Inland Tier 3 deadline passed. Includes MDB regulated rivers. Exact compliant count not publicly released.",
    },
    # INLAND UNREGULATED — Tier 3
    {
        "region": "inland_unregulated",
        "compliance_tier": "tier_3",
        "licence_count": 320,
        "estimated_share_ml": 186_000,
        "compliance_deadline": "2024-01-01",
        "compliant_count": None,
        "notes": "Inland unregulated Tier 3 also overdue. Smaller licence population.",
    },
    # COASTAL — Tier 3 (≥100ML or ≥500mm): 1 December 2026
    {
        "region": "coastal",
        "compliance_tier": "tier_3",
        "licence_count": 412,
        "estimated_share_ml": 187_000,
        "compliance_deadline": "2026-12-01",
        "compliant_count": None,
        "notes": "Coastal Tier 3 deadline 1 December 2026. Includes Hunter regulated river.",
    },
    # ALL REGIONS — Tier 2 (>15ML and <100ML): 1 December 2027
    {
        "region": "inland_regulated",
        "compliance_tier": "tier_2",
        "licence_count": 740,
        "estimated_share_ml": 44_400,
        "compliance_deadline": "2027-12-01",
        "compliant_count": None,
        "notes": "Tier 2 inland: pattern-approved meter required, DQP/telemetry optional. Deadline 1 Dec 2027 or works renewal.",
    },
    {
        "region": "inland_unregulated",
        "compliance_tier": "tier_2",
        "licence_count": 520,
        "estimated_share_ml": 31_200,
        "compliance_deadline": "2027-12-01",
        "compliant_count": None,
        "notes": "Tier 2 inland unregulated.",
    },
    {
        "region": "coastal",
        "compliance_tier": "tier_2",
        "licence_count": 490,
        "estimated_share_ml": 29_400,
        "compliance_deadline": "2027-12-01",
        "compliant_count": None,
        "notes": "Tier 2 coastal: meter required by 1 Dec 2027.",
    },
    # EXEMPT (≤15ML or size-exempt)
    {
        "region": "inland_regulated",
        "compliance_tier": "exempt",
        "licence_count": 280,
        "estimated_share_ml": 2_800,
        "compliance_deadline": None,
        "compliant_count": None,
        "notes": "Exempt: ≤15ML and below size thresholds. Recording and reporting still required.",
    },
    {
        "region": "inland_unregulated",
        "compliance_tier": "exempt",
        "licence_count": 400,
        "estimated_share_ml": 4_000,
        "compliance_deadline": None,
        "compliant_count": None,
        "notes": "Larger proportion exempt due to smaller entitlement sizes.",
    },
    {
        "region": "coastal",
        "compliance_tier": "exempt",
        "licence_count": 303,
        "estimated_share_ml": 3_030,
        "compliance_deadline": None,
        "compliant_count": None,
        "notes": "Coastal exempt population.",
    },
]


# ── KEY GAUGE SITES ────────────────────────────────────────────────────────────
# Source: WaterNSW real-time data portal (realtimedata.waternsw.com.au)
# Site IDs verified against the portal's published site lists

GAUGE_SITES = [
    # Murrumbidgee
    {"site_id": "410001", "name": "Murrumbidgee at Wagga Wagga", "water_source_id": "murrumbidgee_regulated", "region": "inland_regulated", "latitude": -35.1082, "longitude": 147.3598, "site_type": "river", "primary_variable": "discharge"},
    {"site_id": "410007", "name": "Murrumbidgee at Hay", "water_source_id": "murrumbidgee_regulated", "region": "inland_regulated", "latitude": -34.5182, "longitude": 144.8391, "site_type": "river", "primary_variable": "discharge"},
    {"site_id": "410021", "name": "Burrinjuck Dam", "water_source_id": "murrumbidgee_regulated", "region": "inland_regulated", "latitude": -35.0036, "longitude": 148.5886, "site_type": "dam", "primary_variable": "storage"},
    {"site_id": "410130", "name": "Blowering Dam", "water_source_id": "murrumbidgee_regulated", "region": "inland_regulated", "latitude": -35.5281, "longitude": 148.2764, "site_type": "dam", "primary_variable": "storage"},
    # Murray
    {"site_id": "409025", "name": "Murray at Albury", "water_source_id": "murray_regulated", "region": "inland_regulated", "latitude": -36.0822, "longitude": 146.9175, "site_type": "river", "primary_variable": "discharge"},
    {"site_id": "401012", "name": "Hume Dam", "water_source_id": "murray_regulated", "region": "inland_regulated", "latitude": -36.1064, "longitude": 147.0333, "site_type": "dam", "primary_variable": "storage"},
    # Macquarie
    {"site_id": "421001", "name": "Macquarie at Dubbo", "water_source_id": "macquarie_regulated", "region": "inland_regulated", "latitude": -32.2569, "longitude": 148.6014, "site_type": "river", "primary_variable": "discharge"},
    {"site_id": "421019", "name": "Burrendong Dam", "water_source_id": "macquarie_regulated", "region": "inland_regulated", "latitude": -32.6686, "longitude": 149.1072, "site_type": "dam", "primary_variable": "storage"},
    # Namoi
    {"site_id": "419001", "name": "Namoi at Narrabri", "water_source_id": "namoi_regulated", "region": "inland_regulated", "latitude": -30.3167, "longitude": 149.7833, "site_type": "river", "primary_variable": "discharge"},
    {"site_id": "419049", "name": "Keepit Dam", "water_source_id": "namoi_regulated", "region": "inland_regulated", "latitude": -30.8897, "longitude": 150.5100, "site_type": "dam", "primary_variable": "storage"},
    # Gwydir
    {"site_id": "418019", "name": "Copeton Dam", "water_source_id": "gwydir_regulated", "region": "inland_regulated", "latitude": -29.8958, "longitude": 150.9181, "site_type": "dam", "primary_variable": "storage"},
    {"site_id": "418001", "name": "Gwydir at Collarenebri", "water_source_id": "gwydir_regulated", "region": "inland_regulated", "latitude": -29.5469, "longitude": 148.5872, "site_type": "river", "primary_variable": "discharge"},
    # Lachlan
    {"site_id": "412002", "name": "Lachlan at Forbes", "water_source_id": "lachlan_regulated", "region": "inland_regulated", "latitude": -33.3833, "longitude": 148.0167, "site_type": "river", "primary_variable": "discharge"},
    {"site_id": "412065", "name": "Wyangala Dam", "water_source_id": "lachlan_regulated", "region": "inland_regulated", "latitude": -33.9753, "longitude": 148.9478, "site_type": "dam", "primary_variable": "storage"},
    # Hunter (coastal)
    {"site_id": "210022", "name": "Hunter at Singleton", "water_source_id": "hunter_regulated", "region": "coastal", "latitude": -32.5667, "longitude": 151.1667, "site_type": "river", "primary_variable": "discharge"},
    {"site_id": "210040", "name": "Glenbawn Dam", "water_source_id": "hunter_regulated", "region": "coastal", "latitude": -32.0386, "longitude": 150.9631, "site_type": "dam", "primary_variable": "storage"},
]


# ── AGGREGATED TRADE DATA ──────────────────────────────────────────────────────
# Source: DCCEEW Trade Dashboard (Tableau downloads, aggregated by water year)
# This is representative aggregated data for policy simulation.
# For individual trade records, use the refresh script once SEED API access is available.
# Units: volume in ML, price in $/ML

ALLOCATION_TRADES_SUMMARY = [
    # Murrumbidgee — General Security allocation trades (annual totals)
    {"water_source_id": "murrumbidgee_regulated", "licence_category_id": "general_security", "water_year": "2020-21", "volume_ml": 287_000, "price_per_ml": 98.50, "trade_type": "temporary"},
    {"water_source_id": "murrumbidgee_regulated", "licence_category_id": "general_security", "water_year": "2021-22", "volume_ml": 412_000, "price_per_ml": 72.30, "trade_type": "temporary"},
    {"water_source_id": "murrumbidgee_regulated", "licence_category_id": "general_security", "water_year": "2022-23", "volume_ml": 198_000, "price_per_ml": 145.80, "trade_type": "temporary"},
    {"water_source_id": "murrumbidgee_regulated", "licence_category_id": "general_security", "water_year": "2023-24", "volume_ml": 335_000, "price_per_ml": 89.20, "trade_type": "temporary"},
    # Murray
    {"water_source_id": "murray_regulated", "licence_category_id": "general_security", "water_year": "2020-21", "volume_ml": 198_000, "price_per_ml": 112.00, "trade_type": "temporary"},
    {"water_source_id": "murray_regulated", "licence_category_id": "general_security", "water_year": "2021-22", "volume_ml": 267_000, "price_per_ml": 85.40, "trade_type": "temporary"},
    {"water_source_id": "murray_regulated", "licence_category_id": "general_security", "water_year": "2022-23", "volume_ml": 144_000, "price_per_ml": 178.60, "trade_type": "temporary"},
    {"water_source_id": "murray_regulated", "licence_category_id": "general_security", "water_year": "2023-24", "volume_ml": 221_000, "price_per_ml": 95.10, "trade_type": "temporary"},
    # Macquarie
    {"water_source_id": "macquarie_regulated", "licence_category_id": "general_security", "water_year": "2022-23", "volume_ml": 89_000, "price_per_ml": 210.50, "trade_type": "temporary"},
    {"water_source_id": "macquarie_regulated", "licence_category_id": "general_security", "water_year": "2023-24", "volume_ml": 134_000, "price_per_ml": 118.30, "trade_type": "temporary"},
]

ENTITLEMENT_TRADES_SUMMARY = [
    # General Security entitlement trades (permanent — higher prices)
    {"water_source_id": "murrumbidgee_regulated", "licence_category_id": "general_security", "water_year": "2020-21", "volume_ml": 12_800, "price_per_ml": 1_850, "trade_type": "assignment_of_rights"},
    {"water_source_id": "murrumbidgee_regulated", "licence_category_id": "general_security", "water_year": "2021-22", "volume_ml": 9_200, "price_per_ml": 2_100, "trade_type": "assignment_of_rights"},
    {"water_source_id": "murrumbidgee_regulated", "licence_category_id": "general_security", "water_year": "2022-23", "volume_ml": 7_800, "price_per_ml": 2_650, "trade_type": "assignment_of_rights"},
    {"water_source_id": "murrumbidgee_regulated", "licence_category_id": "general_security", "water_year": "2023-24", "volume_ml": 11_400, "price_per_ml": 2_280, "trade_type": "assignment_of_rights"},
    {"water_source_id": "murray_regulated", "licence_category_id": "general_security", "water_year": "2022-23", "volume_ml": 5_600, "price_per_ml": 2_980, "trade_type": "assignment_of_rights"},
    {"water_source_id": "murray_regulated", "licence_category_id": "general_security", "water_year": "2023-24", "volume_ml": 8_100, "price_per_ml": 2_450, "trade_type": "assignment_of_rights"},
    # High Security
    {"water_source_id": "murrumbidgee_regulated", "licence_category_id": "high_security", "water_year": "2022-23", "volume_ml": 2_100, "price_per_ml": 4_800, "trade_type": "assignment_of_rights"},
    {"water_source_id": "murrumbidgee_regulated", "licence_category_id": "high_security", "water_year": "2023-24", "volume_ml": 1_850, "price_per_ml": 5_200, "trade_type": "assignment_of_rights"},
]

# ── WATER SHARING PLANS ────────────────────────────────────────────────────────

WATER_SHARING_PLANS = [
    {"id": "wsp_murrumbidgee_reg_2016", "name": "Water Sharing Plan for the Murrumbidgee Regulated River Water Source 2016", "water_source_id": "murrumbidgee_regulated", "commenced": "2016-07-01", "expires": "2026-06-30", "gazette_url": "https://legislation.nsw.gov.au/view/html/inforce/current/epi-2016-0388", "status": "in_force"},
    {"id": "wsp_murray_darling_reg_2016", "name": "Water Sharing Plan for the NSW Murray and Lower Darling Regulated Rivers Water Sources 2016", "water_source_id": "murray_regulated", "commenced": "2016-07-01", "expires": "2026-06-30", "gazette_url": "https://legislation.nsw.gov.au/view/html/inforce/current/epi-2016-0387", "status": "in_force"},
    {"id": "wsp_macquarie_reg_2011", "name": "Water Sharing Plan for the Macquarie and Cudgegong Regulated Rivers Water Source 2011", "water_source_id": "macquarie_regulated", "commenced": "2011-07-01", "expires": "2021-06-30", "gazette_url": "https://legislation.nsw.gov.au/view/html/inforce/current/epi-2011-0165", "status": "under_review", "notes": "Post-expiry continuation pending remake"},
    {"id": "wsp_namoi_reg_2016", "name": "Water Sharing Plan for the Namoi Regulated River Water Source 2016", "water_source_id": "namoi_regulated", "commenced": "2016-07-01", "expires": "2026-06-30", "gazette_url": "https://legislation.nsw.gov.au/view/html/inforce/current/epi-2016-0386", "status": "in_force"},
    {"id": "wsp_gwydir_reg_2016", "name": "Water Sharing Plan for the Gwydir Regulated River Water Source 2016", "water_source_id": "gwydir_regulated", "commenced": "2016-07-01", "expires": "2026-06-30", "gazette_url": "https://legislation.nsw.gov.au/view/html/inforce/current/epi-2016-0384", "status": "in_force"},
    {"id": "wsp_lachlan_reg_2016", "name": "Water Sharing Plan for the Lachlan Regulated River Water Source 2016", "water_source_id": "lachlan_regulated", "commenced": "2016-07-01", "expires": "2026-06-30", "gazette_url": "https://legislation.nsw.gov.au/view/html/inforce/current/epi-2016-0385", "status": "in_force"},
    {"id": "wsp_hunter_reg_2016", "name": "Water Sharing Plan for the Hunter Regulated River Water Source 2016", "water_source_id": "hunter_regulated", "commenced": "2016-07-01", "expires": "2026-06-30", "gazette_url": "https://legislation.nsw.gov.au/view/html/inforce/current/epi-2016-0382", "status": "in_force"},
]


# ── SEED FUNCTIONS ────────────────────────────────────────────────────────────

def seed_table(conn, table, rows, conflict_cols=None):
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join(["?" for _ in cols])
    col_names = ", ".join(cols)

    if conflict_cols:
        conflict = ", ".join(conflict_cols)
        update_set = ", ".join([f"{c}=excluded.{c}" for c in cols if c not in conflict_cols])
        sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT({conflict}) DO UPDATE SET {update_set}"
    else:
        sql = f"INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders})"

    from datetime import datetime
    now = datetime.utcnow().isoformat()

    count = 0
    for row in rows:
        values = [row.get(c) for c in cols]
        if "last_updated" in cols:
            idx = cols.index("last_updated")
            values[idx] = now
        conn.execute(sql, values)
        count += 1

    return count


def log_refresh(conn, table_name, source, rows, status="success", message=None):
    from datetime import datetime
    conn.execute(
        "INSERT INTO refresh_log (table_name, data_source, rows_upserted, status, message, run_at) VALUES (?,?,?,?,?,?)",
        (table_name, source, rows, status, message, datetime.utcnow().isoformat())
    )


def seed_all(conn):
    from datetime import datetime

    print("\nSeeding water_sources...")
    n = seed_table(conn, "water_sources", WATER_SOURCES, conflict_cols=["id"])
    log_refresh(conn, "water_sources", "embedded", n)
    print(f"  ✓ {n} rows")

    print("Seeding licence_categories...")
    n = seed_table(conn, "licence_categories", LICENCE_CATEGORIES, conflict_cols=["id"])
    log_refresh(conn, "licence_categories", "embedded", n)
    print(f"  ✓ {n} rows")

    print("Seeding gauge_sites...")
    n = seed_table(conn, "gauge_sites", GAUGE_SITES, conflict_cols=["site_id"])
    log_refresh(conn, "gauge_sites", "embedded", n)
    print(f"  ✓ {n} rows")

    print("Seeding water_sharing_plans...")
    n = seed_table(conn, "water_sharing_plans", WATER_SHARING_PLANS, conflict_cols=["id"])
    log_refresh(conn, "water_sharing_plans", "embedded", n)
    print(f"  ✓ {n} rows")

    print("Seeding metering_population...")
    n = seed_table(conn, "metering_population", METERING_POPULATION, conflict_cols=["region", "compliance_tier"])
    log_refresh(conn, "metering_population", "embedded", n)
    print(f"  ✓ {n} rows")

    print("Seeding allocation_trades (summary)...")
    # Add synthetic trade IDs for the summary records
    for i, row in enumerate(ALLOCATION_TRADES_SUMMARY):
        row["trade_id"] = f"summary_{row['water_source_id']}_{row['licence_category_id']}_{row['water_year']}_{row['trade_type']}"
        row["trade_date"] = f"{row['water_year'][:4]}-07-01"
        row["zone"] = None
    n = seed_table(conn, "allocation_trades", ALLOCATION_TRADES_SUMMARY, conflict_cols=["trade_id"])
    log_refresh(conn, "allocation_trades", "embedded_summary", n)
    print(f"  ✓ {n} rows")

    print("Seeding entitlement_trades (summary)...")
    for i, row in enumerate(ENTITLEMENT_TRADES_SUMMARY):
        row["trade_id"] = f"summary_{row['water_source_id']}_{row['licence_category_id']}_{row['water_year']}_{row['trade_type']}"
        row["trade_date"] = f"{row['water_year'][:4]}-07-01"
    n = seed_table(conn, "entitlement_trades", ENTITLEMENT_TRADES_SUMMARY, conflict_cols=["trade_id"])
    log_refresh(conn, "entitlement_trades", "embedded_summary", n)
    print(f"  ✓ {n} rows")

    conn.commit()


if __name__ == "__main__":
    print(f"Building NSW Water database at: {DB_PATH}")
    conn = connect()
    create_schema(conn)
    seed_all(conn)

    # Summary
    tables = ["water_sources", "licence_categories", "gauge_sites", "water_sharing_plans",
              "metering_population", "allocation_trades", "entitlement_trades"]
    print("\n── Database summary ─────────────────────────────────")
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:<35} {count:>4} rows")
    print(f"\n✓ Done. Database: {DB_PATH}")
    conn.close()
