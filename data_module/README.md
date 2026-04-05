# NSW Water — Data Module

Local data layer for the `openfisca-nsw-water` Rules as Code platform.

Provides a structured, queryable SQLite database of NSW water licensing reference data,
trade data, gauge sites, and metering compliance population — with refresh scripts wired
to public NSW government data sources.

---

## What's in here

```
data_module/
├── seed_db.py      ← Build the database from embedded reference data (run first)
├── refresh.py      ← Pull live data from NSW water APIs
├── query.py        ← Python query API (used by OpenFisca and analysis scripts)
├── serve_api.py    ← HTTP JSON API server (used by HTML demos)
└── data/
    ├── db/
    │   └── nsw_water.db    ← SQLite database (created by seed_db.py)
    └── raw/                ← Drop CSV exports from DCCEEW dashboards here
```

---

## Quick start

```bash
cd data_module

# 1. Build the database
python seed_db.py

# 2. Start the data API (alongside the OpenFisca API)
python serve_api.py          # http://localhost:5001

# In another terminal:
make serve                   # OpenFisca API: http://localhost:5000
```

---

## Database contents (seeded)

| Table | Rows | Source |
|---|---|---|
| `water_sources` | 13 | NSW WSPs, SEED portal, NRAR |
| `licence_categories` | 8 | Water Management Act 2000 |
| `gauge_sites` | 16 | WaterNSW real-time portal |
| `water_sharing_plans` | 7 | legislation.nsw.gov.au |
| `metering_population` | 9 | DCCEEW metering review + NRAR |
| `allocation_trades` | 10 | DCCEEW Trade Dashboard (summary) |
| `entitlement_trades` | 8 | DCCEEW Trade Dashboard (summary) |

---

## Refresh — live data sources

### 1. Gauge readings (WaterNSW Real-Time Data API)
No authentication required.

```bash
# Refresh all gauge sites (last 3 days)
python refresh.py --gauges

# Refresh a specific site
python refresh.py --gauges --site 421001

# Refresh with 7 days of history
python refresh.py --gauges --days 7

# Dry run
python refresh.py --gauges --dry-run
```

**Site IDs for key gauges:**

| Site ID | Name | Variable |
|---|---|---|
| 410001 | Murrumbidgee at Wagga Wagga | 141.00 (discharge ML/d) |
| 421001 | Macquarie at Dubbo | 141.00 (discharge ML/d) |
| 421019 | Burrendong Dam | 130.00 (reservoir level m) |
| 419049 | Keepit Dam | 130.00 (reservoir level m) |
| 210022 | Hunter at Singleton | 141.00 (discharge ML/d) |

**Quality codes:** 10=Good · 20=Fair · 30=Poor · 60=Estimate

### 2. Dam levels (WaterInsights API via API.NSW)
Requires an API key from [api.nsw.gov.au](https://api.nsw.gov.au/Product/Index/26).

```bash
export NSW_WATERINSIGHTS_API_KEY=your_key_here
python refresh.py --dams
```

### 3. Trade data (DCCEEW Trade Dashboard)
The DCCEEW dashboard uses Tableau — no public REST API.

**Manual process:**
1. Visit: https://water.dpie.nsw.gov.au/.../trade-dashboard
2. Download → Data → CSV
3. Save as `data/raw/allocation_trades.csv` or `data/raw/entitlement_trades.csv`
4. Run: `python refresh.py --trades`

**Future:** CRO-level data-sharing agreement with DCCEEW to automate this feed.

### Suggested cron schedule

```cron
# Gauge readings every 30 min
*/30 * * * * cd /path/to/data_module && python refresh.py --gauges >> logs/refresh.log 2>&1

# Dam levels daily at 7am
0 7 * * * cd /path/to/data_module && python refresh.py --dams >> logs/refresh.log 2>&1
```

---

## HTTP API endpoints

Base URL: `http://localhost:5001`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/water-sources` | List water sources (`?region=`, `?source_type=`) |
| GET | `/water-sources/{id}` | Get one water source |
| GET | `/licence-categories` | List licence categories (`?attestation_tier=`) |
| GET | `/metering/population` | Population by region/tier (`?region=`, `?compliance_tier=`) |
| GET | `/metering/compliance-summary` | Aggregated compliance counts |
| GET | `/trade/allocations` | Allocation trade summary |
| GET | `/trade/entitlements` | Entitlement trade summary |
| GET | `/trade/price-trend` | Price trend for source+category |
| GET | `/gauges` | List gauge sites |
| GET | `/gauges/{site_id}/latest` | Latest reading for a site |
| GET | `/gauges/{site_id}/series` | Time series (`?days=7`) |
| GET | `/water-sharing-plans` | List water sharing plans |
| GET | `/refresh-log` | Recent refresh log |

---

## Python query API

```python
from query import WaterDataDB

with WaterDataDB() as db:
    # Water sources
    sources = db.list_water_sources(region="inland_regulated")
    source  = db.get_water_source("murrumbidgee_regulated")

    # Metering compliance population (for policy simulation)
    summary = db.compliance_summary()
    # Returns: {'tier_3': {...}, 'tier_2': {...}, 'exempt': {...}, 'total_licences': 4287}

    # Trade data
    trades = db.allocation_trade_summary(water_source_id="murrumbidgee_regulated")
    trend  = db.price_trend("murrumbidgee_regulated", "general_security")

    # Gauge readings (populated after running refresh.py --gauges)
    latest = db.latest_gauge_reading("421001")
    series = db.gauge_time_series("421001", days=7)

    # OpenFisca integration
    context = db.get_metering_context("murrumbidgee_regulated")
    region  = db.get_openfisca_region("murrumbidgee_regulated")
    # Returns: "inland_regulated" — matches WaterRegion enum in metering.py
```

---

## Data sources and attribution

| Data | Source | Licence |
|---|---|---|
| Water sharing plan names and areas | legislation.nsw.gov.au (Parliamentary Counsel) | CC-BY 4.0 |
| Gauge site IDs and locations | WaterNSW real-time portal | WaterNSW copyright |
| Water source share components (approx.) | DCCEEW SEED portal dashboards | CC-BY 4.0 |
| Metering population figures | DCCEEW metering review report (2023–24) | Open government |
| Trade price summary data | DCCEEW Trade Dashboard | CC-BY 4.0 |
| Licence categories | Water Management Act 2000 (public law) | Public domain |

All embedded data is sourced from public NSW government sources.
Attribution: © State of NSW, Department of Climate Change, Energy, the Environment and Water.
