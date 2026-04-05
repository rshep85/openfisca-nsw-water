"""
NSW Water — Data Module: Query API
====================================
Clean query interface over the local SQLite database.
Used by OpenFisca variables, demo apps (via a thin HTTP layer), and analysis scripts.

Usage:
    from query import WaterDataDB

    db = WaterDataDB()

    # Water source lookup
    src = db.get_water_source("murrumbidgee_regulated")
    sources = db.list_water_sources(region="inland_regulated")

    # Licence category
    cat = db.get_licence_category("general_security")

    # Metering population (for policy simulation)
    pop = db.metering_population(region="coastal")
    total = db.total_licence_count()

    # Trade data
    trades = db.allocation_trade_summary(water_source_id="murrumbidgee_regulated")
    prices = db.price_trend(water_source_id="murrumbidgee_regulated", licence_category_id="general_security")

    # Gauge readings
    latest = db.latest_gauge_reading("421001")
    series = db.gauge_time_series("421001", days=7)

    db.close()
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import os


DB_PATH = Path(os.environ.get("NRAR_DATA_DB_PATH",
               Path(__file__).parent / "data" / "db" / "nsw_water.db"))

QUALITY_CODE_LABELS = {
    10: "Good", 15: "No flow", 20: "Fair", 30: "Poor", 60: "Estimate", 130: "Interim"
}


class WaterDataDB:
    """Query interface for the NSW Water local database."""

    def __init__(self, db_path=None):
        path = db_path or DB_PATH
        if not Path(path).exists():
            raise FileNotFoundError(
                f"Database not found at {path}. Run seed_db.py first.\n"
                f"  cd data_module && python seed_db.py"
            )
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA query_only=ON")

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _q(self, sql, params=()):
        return self._conn.execute(sql, params).fetchall()

    def _one(self, sql, params=()):
        return self._conn.execute(sql, params).fetchone()

    def _to_dict(self, row):
        if row is None:
            return None
        return dict(row)

    def _to_dicts(self, rows):
        return [dict(r) for r in rows]

    # ── WATER SOURCES ───────────────────────────────────────────────────────────

    def get_water_source(self, source_id: str) -> dict | None:
        """Get a single water source by ID."""
        return self._to_dict(self._one(
            "SELECT * FROM water_sources WHERE id=?", (source_id,)
        ))

    def list_water_sources(self,
                            region: str = None,
                            source_type: str = None,
                            basin: str = None) -> list[dict]:
        """
        List water sources with optional filters.

        Args:
            region: 'inland_regulated' | 'inland_unregulated' | 'coastal'
            source_type: 'regulated_river' | 'unregulated_river' | 'groundwater'
            basin: 'murray_darling' | None for coastal
        """
        clauses, params = [], []
        if region:
            clauses.append("region=?"); params.append(region)
        if source_type:
            clauses.append("source_type=?"); params.append(source_type)
        if basin:
            clauses.append("basin=?"); params.append(basin)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return self._to_dicts(self._q(
            f"SELECT * FROM water_sources {where} ORDER BY total_share_ml DESC NULLS LAST",
            params
        ))

    def water_source_summary(self) -> dict:
        """
        Returns summary counts and totals by region and source type.
        Useful for populating the policy simulation lens.
        """
        rows = self._q("""
            SELECT region, source_type,
                   COUNT(*) as source_count,
                   SUM(licence_count) as total_licences,
                   SUM(total_share_ml) as total_share_ml
            FROM water_sources
            GROUP BY region, source_type
            ORDER BY region, source_type
        """)
        return self._to_dicts(rows)

    # ── LICENCE CATEGORIES ──────────────────────────────────────────────────────

    def get_licence_category(self, category_id: str) -> dict | None:
        """Get a licence category by ID."""
        return self._to_dict(self._one(
            "SELECT * FROM licence_categories WHERE id=?", (category_id,)
        ))

    def list_licence_categories(self,
                                 attestation_tier: str = None,
                                 metering_tier: str = None) -> list[dict]:
        """List licence categories with optional filters."""
        clauses, params = [], []
        if attestation_tier:
            clauses.append("attestation_tier=?"); params.append(attestation_tier)
        if metering_tier:
            clauses.append("metering_tier=?"); params.append(metering_tier)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return self._to_dicts(self._q(
            f"SELECT * FROM licence_categories {where} ORDER BY id", params
        ))

    # ── METERING COMPLIANCE POPULATION ─────────────────────────────────────────

    def metering_population(self,
                             region: str = None,
                             compliance_tier: str = None) -> list[dict]:
        """
        Get metering compliance population stats.

        Args:
            region: Filter by region
            compliance_tier: 'tier_3' | 'tier_2' | 'exempt'

        Returns list of rows with licence_count, estimated_share_ml, compliance_deadline.
        """
        clauses, params = [], []
        if region:
            clauses.append("region=?"); params.append(region)
        if compliance_tier:
            clauses.append("compliance_tier=?"); params.append(compliance_tier)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return self._to_dicts(self._q(
            f"SELECT * FROM metering_population {where} ORDER BY region, compliance_tier",
            params
        ))

    def total_licence_count(self, region: str = None) -> int:
        """Total licence count across all tiers, optionally filtered by region."""
        if region:
            row = self._one(
                "SELECT SUM(licence_count) as total FROM metering_population WHERE region=?",
                (region,)
            )
        else:
            row = self._one("SELECT SUM(licence_count) as total FROM metering_population")
        return row["total"] or 0

    def compliance_summary(self) -> dict:
        """
        Returns a summary dict suitable for the policy simulation and regulator dashboard.
        Aggregates across all regions.
        """
        rows = self._q("""
            SELECT compliance_tier,
                   SUM(licence_count) as licence_count,
                   SUM(estimated_share_ml) as total_share_ml,
                   MIN(compliance_deadline) as earliest_deadline
            FROM metering_population
            GROUP BY compliance_tier
        """)

        result = {r["compliance_tier"]: dict(r) for r in rows}

        total = sum(r.get("licence_count") or 0 for r in result.values())
        result["total_licences"] = total
        result["source"] = "WM(G) Regulation 2025 + DCCEEW metering review data"
        result["last_updated"] = self._one(
            "SELECT MAX(last_updated) as lu FROM metering_population"
        )["lu"]
        return result

    # ── TRADE DATA ──────────────────────────────────────────────────────────────

    def allocation_trade_summary(self,
                                  water_source_id: str = None,
                                  licence_category_id: str = None,
                                  water_year: str = None) -> list[dict]:
        """
        Summarised allocation trade data (temporary trades, 71T).

        Args:
            water_source_id: Filter by water source
            licence_category_id: Filter by licence category
            water_year: Filter by water year e.g. '2023-24'
        """
        clauses, params = [], []
        if water_source_id:
            clauses.append("t.water_source_id=?"); params.append(water_source_id)
        if licence_category_id:
            clauses.append("t.licence_category_id=?"); params.append(licence_category_id)
        if water_year:
            clauses.append("t.water_year=?"); params.append(water_year)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        return self._to_dicts(self._q(f"""
            SELECT
                t.water_source_id,
                ws.name as water_source_name,
                t.licence_category_id,
                lc.name as licence_category_name,
                t.water_year,
                t.trade_type,
                SUM(t.volume_ml) as total_volume_ml,
                AVG(t.price_per_ml) as avg_price_per_ml,
                MIN(t.price_per_ml) as min_price_per_ml,
                MAX(t.price_per_ml) as max_price_per_ml,
                COUNT(*) as trade_count
            FROM allocation_trades t
            LEFT JOIN water_sources ws ON t.water_source_id = ws.id
            LEFT JOIN licence_categories lc ON t.licence_category_id = lc.id
            {where}
            GROUP BY t.water_source_id, t.licence_category_id, t.water_year, t.trade_type
            ORDER BY t.water_year DESC, total_volume_ml DESC
        """, params))

    def entitlement_trade_summary(self,
                                   water_source_id: str = None,
                                   licence_category_id: str = None) -> list[dict]:
        """Summarised entitlement trade data (permanent trades, 71Q)."""
        clauses, params = [], []
        if water_source_id:
            clauses.append("t.water_source_id=?"); params.append(water_source_id)
        if licence_category_id:
            clauses.append("t.licence_category_id=?"); params.append(licence_category_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        return self._to_dicts(self._q(f"""
            SELECT
                t.water_source_id,
                ws.name as water_source_name,
                t.licence_category_id,
                lc.name as licence_category_name,
                t.water_year,
                t.trade_type,
                SUM(t.volume_ml) as total_volume_ml,
                AVG(t.price_per_ml) as avg_price_per_ml,
                COUNT(*) as trade_count
            FROM entitlement_trades t
            LEFT JOIN water_sources ws ON t.water_source_id = ws.id
            LEFT JOIN licence_categories lc ON t.licence_category_id = lc.id
            {where}
            GROUP BY t.water_source_id, t.licence_category_id, t.water_year, t.trade_type
            ORDER BY t.water_year DESC, avg_price_per_ml DESC
        """, params))

    def price_trend(self,
                    water_source_id: str,
                    licence_category_id: str,
                    trade_kind: str = "allocation") -> list[dict]:
        """
        Price trend by water year for a specific water source and licence category.
        Useful for populating price charts in the demo.

        Args:
            trade_kind: 'allocation' (71T) | 'entitlement' (71Q)
        """
        table = "allocation_trades" if trade_kind == "allocation" else "entitlement_trades"
        return self._to_dicts(self._q(f"""
            SELECT water_year,
                   AVG(price_per_ml) as avg_price_per_ml,
                   SUM(volume_ml) as total_volume_ml,
                   COUNT(*) as trade_count
            FROM {table}
            WHERE water_source_id=? AND licence_category_id=?
            GROUP BY water_year
            ORDER BY water_year
        """, (water_source_id, licence_category_id)))

    # ── GAUGE SITES ─────────────────────────────────────────────────────────────

    def list_gauge_sites(self,
                          water_source_id: str = None,
                          site_type: str = None,
                          region: str = None) -> list[dict]:
        """List gauge sites with optional filters."""
        clauses, params = ["active=1"], []
        if water_source_id:
            clauses.append("water_source_id=?"); params.append(water_source_id)
        if site_type:
            clauses.append("site_type=?"); params.append(site_type)
        if region:
            clauses.append("region=?"); params.append(region)
        where = f"WHERE {' AND '.join(clauses)}"
        return self._to_dicts(self._q(
            f"SELECT * FROM gauge_sites {where} ORDER BY site_id", params
        ))

    def latest_gauge_reading(self, site_id: str, variable: str = None) -> dict | None:
        """
        Get the most recent reading for a gauge site.

        Args:
            site_id: WaterNSW site ID e.g. '421001'
            variable: Optional variable code e.g. '141.00' for discharge
        """
        clauses = ["site_id=?"]
        params = [site_id]
        if variable:
            clauses.append("variable=?"); params.append(variable)

        row = self._one(f"""
            SELECT r.*, g.name as site_name, g.site_type
            FROM gauge_readings r
            JOIN gauge_sites g ON r.site_id = g.site_id
            WHERE {' AND '.join(clauses)}
            ORDER BY r.timestamp DESC
            LIMIT 1
        """, params)

        if row is None:
            return None

        result = dict(row)
        result["quality_label"] = QUALITY_CODE_LABELS.get(result.get("quality_code"), "Unknown")
        return result

    def gauge_time_series(self,
                           site_id: str,
                           variable: str = None,
                           days: int = 7) -> list[dict]:
        """
        Get time-series readings for a gauge site.

        Args:
            site_id: WaterNSW site ID
            variable: Variable code (defaults to all variables for site)
            days: Number of days of history to return
        """
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        clauses = ["r.site_id=?", "r.timestamp >= ?"]
        params = [site_id, since]
        if variable:
            clauses.append("r.variable=?"); params.append(variable)

        rows = self._q(f"""
            SELECT r.timestamp, r.variable, r.value, r.quality_code,
                   g.name as site_name, g.primary_variable
            FROM gauge_readings r
            JOIN gauge_sites g ON r.site_id = g.site_id
            WHERE {' AND '.join(clauses)}
            ORDER BY r.timestamp ASC
        """, params)

        result = []
        for row in rows:
            d = dict(row)
            d["quality_label"] = QUALITY_CODE_LABELS.get(d.get("quality_code"), "Unknown")
            result.append(d)
        return result

    def has_live_data(self, site_id: str, max_age_hours: int = 2) -> bool:
        """
        Check if a gauge site has recent readings.
        Useful for T1 attestation — only flag as verified if data is fresh.
        """
        threshold = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()
        row = self._one(
            "SELECT COUNT(*) as n FROM gauge_readings WHERE site_id=? AND timestamp >= ?",
            (site_id, threshold)
        )
        return (row["n"] or 0) > 0

    # ── WATER SHARING PLANS ─────────────────────────────────────────────────────

    def list_water_sharing_plans(self, status: str = "in_force") -> list[dict]:
        """List water sharing plans."""
        clauses, params = [], []
        if status:
            clauses.append("status=?"); params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return self._to_dicts(self._q(
            f"SELECT * FROM water_sharing_plans {where} ORDER BY commenced", params
        ))

    # ── OPENFISCA INTEGRATION ───────────────────────────────────────────────────

    def get_openfisca_region(self, water_source_id: str) -> str | None:
        """
        Map a water source ID to the OpenFisca WaterRegion enum value.
        Used to populate OpenFisca inputs from the database.
        """
        source = self.get_water_source(water_source_id)
        if not source:
            return None
        return source["region"]  # already matches OpenFisca enum: inland_regulated | inland_unregulated | coastal

    def get_metering_context(self, water_source_id: str) -> dict:
        """
        Returns context needed to populate OpenFisca metering variables
        for licences in a given water source.
        """
        source = self.get_water_source(water_source_id)
        if not source:
            return {}

        # Get dominant licence categories for this source
        shares = self._q(
            "SELECT * FROM source_licence_shares WHERE water_source_id=? ORDER BY share_component_ml DESC",
            (water_source_id,)
        )

        return {
            "water_source_id": water_source_id,
            "water_source_name": source["name"],
            "openfisca_region": source["region"],
            "licence_count": source["licence_count"],
            "total_share_ml": source["total_share_ml"],
            "compliance_population": self.metering_population(region=source["region"]),
        }

    # ── REFRESH LOG ─────────────────────────────────────────────────────────────

    def last_refresh(self, table_name: str = None) -> list[dict]:
        """Get recent refresh log entries."""
        if table_name:
            rows = self._q(
                "SELECT * FROM refresh_log WHERE table_name=? ORDER BY run_at DESC LIMIT 10",
                (table_name,)
            )
        else:
            rows = self._q(
                "SELECT * FROM refresh_log ORDER BY run_at DESC LIMIT 20"
            )
        return self._to_dicts(rows)
