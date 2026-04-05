"""
NSW Water — Data Module: HTTP API Server
==========================================
Exposes the local database as a JSON REST API so the HTML demo files
can fetch real data via JavaScript fetch() calls.

Run this alongside the OpenFisca API server when demoing.

Usage:
    python serve_api.py              # Default: port 5001
    python serve_api.py --port 5002  # Custom port

Endpoints:
    GET /water-sources              List all water sources
    GET /water-sources/{id}         Get one water source
    GET /licence-categories         List all licence categories
    GET /metering/population        Metering compliance population summary
    GET /metering/compliance-summary  Aggregated compliance counts
    GET /trade/allocations          Allocation trade summary
    GET /trade/entitlements         Entitlement trade summary
    GET /trade/price-trend          Price trend for a source/category
    GET /gauges                     List gauge sites
    GET /gauges/{site_id}/latest    Latest reading for a gauge
    GET /gauges/{site_id}/series    Time series for a gauge
    GET /health                     Health check

Query params (where applicable):
    ?region=inland_regulated
    ?source_type=regulated_river
    ?water_source_id=murrumbidgee_regulated
    ?licence_category_id=general_security
    ?water_year=2023-24
    ?days=7

CORS is enabled for all origins (local dev only — restrict in production).
"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from query import WaterDataDB


def json_response(data, status=200):
    return status, json.dumps(data, default=str, indent=2)


def error(msg, status=400):
    return status, json.dumps({"error": msg})


class WaterAPIHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Quiet logging — only show errors
        if args and str(args[1]) not in ("200", "304"):
            super().log_message(format, *args)

    def send_json(self, status, body):
        encoded = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(encoded))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(encoded)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        try:
            status, body = self.route(path, params)
        except Exception as e:
            status, body = error(f"Internal error: {e}", 500)

        self.send_json(status, body)

    def route(self, path, params):
        parts = [p for p in path.split("/") if p]

        with WaterDataDB() as db:

            # ── Health ──────────────────────────────────────────────────────────
            if path == "/health":
                summary = db.compliance_summary()
                return json_response({
                    "status": "ok",
                    "total_licences": summary.get("total_licences"),
                    "db_source": "nsw_water.db",
                })

            # ── Water sources ────────────────────────────────────────────────────
            elif path == "/water-sources":
                data = db.list_water_sources(
                    region=params.get("region"),
                    source_type=params.get("source_type"),
                    basin=params.get("basin"),
                )
                return json_response({"count": len(data), "results": data})

            elif len(parts) == 2 and parts[0] == "water-sources":
                data = db.get_water_source(parts[1])
                if not data:
                    return error(f"Water source '{parts[1]}' not found", 404)
                return json_response(data)

            elif path == "/water-sources/summary":
                return json_response(db.water_source_summary())

            # ── Licence categories ───────────────────────────────────────────────
            elif path == "/licence-categories":
                data = db.list_licence_categories(
                    attestation_tier=params.get("attestation_tier"),
                    metering_tier=params.get("metering_tier"),
                )
                return json_response({"count": len(data), "results": data})

            elif len(parts) == 2 and parts[0] == "licence-categories":
                data = db.get_licence_category(parts[1])
                if not data:
                    return error(f"Licence category '{parts[1]}' not found", 404)
                return json_response(data)

            # ── Metering ─────────────────────────────────────────────────────────
            elif path == "/metering/population":
                data = db.metering_population(
                    region=params.get("region"),
                    compliance_tier=params.get("compliance_tier"),
                )
                return json_response({"count": len(data), "results": data})

            elif path == "/metering/compliance-summary":
                return json_response(db.compliance_summary())

            # ── Trade ────────────────────────────────────────────────────────────
            elif path == "/trade/allocations":
                data = db.allocation_trade_summary(
                    water_source_id=params.get("water_source_id"),
                    licence_category_id=params.get("licence_category_id"),
                    water_year=params.get("water_year"),
                )
                return json_response({"count": len(data), "results": data})

            elif path == "/trade/entitlements":
                data = db.entitlement_trade_summary(
                    water_source_id=params.get("water_source_id"),
                    licence_category_id=params.get("licence_category_id"),
                )
                return json_response({"count": len(data), "results": data})

            elif path == "/trade/price-trend":
                ws = params.get("water_source_id")
                lc = params.get("licence_category_id")
                kind = params.get("trade_kind", "allocation")
                if not ws or not lc:
                    return error("Required: water_source_id and licence_category_id")
                data = db.price_trend(ws, lc, trade_kind=kind)
                return json_response({"water_source_id": ws, "licence_category_id": lc,
                                      "trade_kind": kind, "results": data})

            # ── Gauges ───────────────────────────────────────────────────────────
            elif path == "/gauges":
                data = db.list_gauge_sites(
                    water_source_id=params.get("water_source_id"),
                    site_type=params.get("site_type"),
                    region=params.get("region"),
                )
                return json_response({"count": len(data), "results": data})

            elif len(parts) == 3 and parts[0] == "gauges" and parts[2] == "latest":
                data = db.latest_gauge_reading(parts[1], variable=params.get("variable"))
                if not data:
                    return error(f"No readings found for site '{parts[1]}'. "
                                 f"Run: python refresh.py --gauges --site {parts[1]}", 404)
                return json_response(data)

            elif len(parts) == 3 and parts[0] == "gauges" and parts[2] == "series":
                days = int(params.get("days", 7))
                data = db.gauge_time_series(
                    parts[1],
                    variable=params.get("variable"),
                    days=days,
                )
                return json_response({
                    "site_id": parts[1],
                    "days": days,
                    "count": len(data),
                    "results": data,
                })

            # ── Water sharing plans ──────────────────────────────────────────────
            elif path == "/water-sharing-plans":
                data = db.list_water_sharing_plans(
                    status=params.get("status", "in_force")
                )
                return json_response({"count": len(data), "results": data})

            # ── Refresh log ──────────────────────────────────────────────────────
            elif path == "/refresh-log":
                data = db.last_refresh(table_name=params.get("table"))
                return json_response({"results": data})

            else:
                return error(f"Unknown endpoint: {path}", 404)


def main():
    parser = argparse.ArgumentParser(description="NSW Water Data API Server")
    parser.add_argument("--port", type=int, default=5001, help="Port to listen on (default: 5001)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to")
    args = parser.parse_args()

    print(f"NSW Water Data API")
    print(f"Listening on http://{args.host}:{args.port}")
    print(f"OpenFisca API: http://localhost:5000")
    print()
    print("Key endpoints:")
    print(f"  GET http://localhost:{args.port}/health")
    print(f"  GET http://localhost:{args.port}/metering/compliance-summary")
    print(f"  GET http://localhost:{args.port}/water-sources?region=inland_regulated")
    print(f"  GET http://localhost:{args.port}/trade/allocations?water_source_id=murrumbidgee_regulated")
    print(f"  GET http://localhost:{args.port}/gauges/421001/latest")
    print()
    print("Ctrl+C to stop")

    server = HTTPServer((args.host, args.port), WaterAPIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
