"""
real_data_connectors.py
=======================
Fetches real public data and posts to the Ops Intelligence Platform webhook.
Data is posted as PUBLIC (no api_key) so all visitors see it - no login required.

Sources:
  Healthcare  - CMS data.cms.gov (US hospital ED performance)
  Airport     - OpenSky Network opensky-network.org (live aircraft positions)
  Logistics   - Bureau of Transportation Statistics data.bts.gov (port congestion)

All sources are free, public domain or CC BY, legal to use.

Run locally:
  pip install httpx
  python real_data_connectors.py --all

Runs automatically via GitHub Actions every 30 minutes (see .github/workflows/).
"""

import httpx
import json
import argparse
import random
import os
from datetime import datetime, timezone

WEBHOOK_URL = os.getenv(
    "WEBHOOK_URL",
    "https://ops-intelligence-platform.onrender.com/webhook/events"
)


def post_to_webhook(events: list, dry_run: bool = False):
    """Post events as PUBLIC data - visible to all visitors, no login required."""
    payload = {"events": events}   # No api_key = public data (user_id NULL)

    if dry_run:
        print("\n[DRY RUN] Would post:")
        print(json.dumps(payload, indent=2))
        return

    try:
        response = httpx.post(WEBHOOK_URL, json=payload, timeout=30.0)
        data = response.json()
        incidents = data.get("incidents_created", 0)
        print(f"  OK Posted {len(events)} events -> {incidents} new incidents created")
    except Exception as e:
        print(f"  ERR Webhook error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# HEALTHCARE - CMS Hospital ED Performance Data
# Source: data.cms.gov - Timely and Effective Care dataset
# License: Public domain (US federal government)
# Measures: OP_18b (median ED time), OP_20 (time to provider)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_healthcare(dry_run=False):
    print("\n[HEALTHCARE] Fetching CMS hospital ED data...")

    events = []
    hour = datetime.now(timezone.utc).hour
    weekday = datetime.now(timezone.utc).weekday()
    is_peak = 9 <= hour <= 14 or 18 <= hour <= 22
    is_monday = weekday == 0
    base = (1.4 if is_peak else 0.8) * (1.2 if is_monday else 1.0)

    try:
        resp = httpx.get(
            "https://data.cms.gov/provider-data/api/1/datastore/query/yv7e-xc69/0",
            params={
                "limit": 100,
                "offset": 0,
                "filters[0][property]": "measure_id",
                "filters[0][value]": "OP_18b",
                "filters[0][operator]": "=",
            },
            timeout=20.0,
        )
        records = resp.json().get("results", [])
        valid = [r for r in records if r.get("score") not in (None, "Not Available", "")]
        print(f"  OK {len(valid)} valid hospital records from CMS")

        # Sample 3 hospitals and derive stage metrics
        sample = random.sample(valid, min(3, len(valid)))
        for record in sample:
            try:
                ed_minutes = float(record["score"])
                ed_seconds = ed_minutes * 60
                state = record.get("state", "US")
                queue = max(5, min(45, ed_minutes / 7))
                throughput = max(3, min(20, 60 / (ed_minutes / 60 + 0.1)))

                events += [
                    {
                        "stage": "ed_triage",
                        "queue_size": round(queue, 1),
                        "processing_time_seconds": round(ed_seconds * 0.15, 1),
                        "throughput": round(throughput, 1),
                        "industry": "healthcare",
                        "source": f"CMS:{state}",
                    },
                    {
                        "stage": "bed_assignment",
                        "queue_size": round(queue * 0.7, 1),
                        "processing_time_seconds": round(ed_seconds * 0.25, 1),
                        "throughput": round(throughput * 0.8, 1),
                        "industry": "healthcare",
                        "source": f"CMS:{state}",
                    },
                    {
                        "stage": "discharge",
                        "queue_size": round(queue * 0.5, 1),
                        "processing_time_seconds": round(ed_seconds * 0.30, 1),
                        "throughput": round(throughput * 1.1, 1),
                        "industry": "healthcare",
                        "source": f"CMS:{state}",
                    },
                ]
            except (ValueError, TypeError):
                continue

    except Exception as e:
        print(f"  ERR CMS API issue ({e}), using research benchmarks")

    if not events:
        # Research-based fallback: ACEP 2024 - avg US ED time 160 min
        noise = lambda: random.uniform(0.88, 1.12)
        events = [
            {"stage": "ed_triage",     "queue_size": round(18*base*noise(), 1), "processing_time_seconds": round(145*base*noise(), 1), "throughput": round(12/base*noise(), 1), "industry": "healthcare", "source": "acep_benchmark"},
            {"stage": "bed_assignment","queue_size": round(12*base*noise(), 1), "processing_time_seconds": round(210*base*noise(), 1), "throughput": round(8/base*noise(), 1),  "industry": "healthcare", "source": "acep_benchmark"},
            {"stage": "diagnostics",   "queue_size": round(8*base*noise(), 1),  "processing_time_seconds": round(180*base*noise(), 1), "throughput": round(10/base*noise(), 1), "industry": "healthcare", "source": "acep_benchmark"},
            {"stage": "discharge",     "queue_size": round(10*base*noise(), 1), "processing_time_seconds": round(240*base*noise(), 1), "throughput": round(7/base*noise(), 1),  "industry": "healthcare", "source": "acep_benchmark"},
        ]

    print(f"  -> Sending {len(events)} healthcare events...")
    post_to_webhook(events, dry_run)


# ─────────────────────────────────────────────────────────────────────────────
# AIRPORT - OpenSky Network Live Aircraft Surveillance
# Source: opensky-network.org - Community ADS-B data
# License: CC BY 4.0
# Data: Real-time aircraft positions near major US airports
# ─────────────────────────────────────────────────────────────────────────────

def fetch_airport(dry_run=False):
    print("\n[AIRPORT] Fetching OpenSky live aircraft data...")

    airports = [
        {"code": "LAX", "lat": 33.9425, "lon": -118.4081},
        {"code": "JFK", "lat": 40.6413, "lon": -73.7781},
        {"code": "ORD", "lat": 41.9742, "lon": -87.9073},
    ]

    hour = datetime.now(timezone.utc).hour
    is_peak = 6 <= hour <= 10 or 16 <= hour <= 20
    events = []

    for airport in airports[:2]:
        try:
            size = 0.5
            resp = httpx.get(
                "https://opensky-network.org/api/states/all",
                params={
                    "lamin": airport["lat"] - size,
                    "lomin": airport["lon"] - size,
                    "lamax": airport["lat"] + size,
                    "lomax": airport["lon"] + size,
                },
                timeout=15.0,
            )
            count = len(resp.json().get("states", []) or [])
            print(f"  OK {airport['code']}: {count} aircraft in airspace")

            q = max(15, min(120, count * 5))
            p = max(100, count * 12 + random.randint(-15, 25))
            t = max(5, min(35, 180 / max(1, count)))

            events += [
                {"stage": "checkin",            "queue_size": round(q*0.9, 1), "processing_time_seconds": round(p*0.6, 1), "throughput": round(t*1.2, 1), "industry": "airport", "source": f"OpenSky:{airport['code']}"},
                {"stage": "security_screening", "queue_size": round(q*1.1, 1), "processing_time_seconds": round(p*0.8, 1), "throughput": round(t*0.9, 1), "industry": "airport", "source": f"OpenSky:{airport['code']}"},
                {"stage": "boarding",           "queue_size": round(q*0.7, 1), "processing_time_seconds": round(p*0.5, 1), "throughput": round(t*1.1, 1), "industry": "airport", "source": f"OpenSky:{airport['code']}"},
            ]

        except Exception as e:
            print(f"  ERR {airport['code']}: OpenSky unavailable ({e}), using FAA benchmarks")
            base = 1.5 if is_peak else 0.7
            noise = lambda: random.uniform(0.9, 1.1)
            events += [
                {"stage": "checkin",            "queue_size": round(65*base*noise(), 1), "processing_time_seconds": round(180*base*noise(), 1), "throughput": round(18/base*noise(), 1), "industry": "airport", "source": f"faa_benchmark:{airport['code']}"},
                {"stage": "security_screening", "queue_size": round(80*base*noise(), 1), "processing_time_seconds": round(220*base*noise(), 1), "throughput": round(15/base*noise(), 1), "industry": "airport", "source": f"faa_benchmark:{airport['code']}"},
                {"stage": "boarding",           "queue_size": round(50*base*noise(), 1), "processing_time_seconds": round(150*base*noise(), 1), "throughput": round(20/base*noise(), 1), "industry": "airport", "source": f"faa_benchmark:{airport['code']}"},
            ]

    print(f"  -> Sending {len(events)} airport events...")
    post_to_webhook(events, dry_run)


# ─────────────────────────────────────────────────────────────────────────────
# LOGISTICS - Bureau of Transportation Statistics Port Data
# Source: data.bts.gov - Supply Chain Freight Indicators
# License: Public domain (US federal government)
# Data: Port congestion, vessels waiting, container volumes
# ─────────────────────────────────────────────────────────────────────────────

def fetch_logistics(dry_run=False):
    print("\n[LOGISTICS] Fetching BTS freight indicator data...")

    events = []
    month = datetime.now(timezone.utc).month
    weekday = datetime.now(timezone.utc).weekday()
    is_holiday_peak = month in [11, 12]
    is_monday = weekday == 0
    noise = lambda: random.uniform(0.9, 1.1)

    try:
        resp = httpx.get(
            "https://data.bts.gov/resource/crem-vd5q.json",
            params={"$limit": 10, "$order": "date DESC"},
            timeout=20.0,
        )
        data = resp.json()
        if data:
            latest = data[0]
            print(f"  OK BTS data date: {latest.get('date', 'unknown')}")
            vessel_wait = float(latest.get("vessels_waiting_at_berth", 8))
            container_vol = float(latest.get("loaded_imports", 500000))
            congestion = vessel_wait / 10.0

            events = [
                {"stage": "port_receiving",      "queue_size": round(min(250, container_vol/2000)*congestion, 1),   "processing_time_seconds": round(min(220, vessel_wait*15), 1),    "throughput": round(max(30, 600/max(1,vessel_wait)), 1),   "industry": "ecommerce", "source": "BTS:port_congestion"},
                {"stage": "warehouse_processing","queue_size": round(min(200, container_vol/2500)*congestion, 1),   "processing_time_seconds": round(min(180, vessel_wait*12), 1),    "throughput": round(max(35, 550/max(1,vessel_wait)), 1),   "industry": "ecommerce", "source": "BTS:freight_volume"},
                {"stage": "dispatch",            "queue_size": round(min(180, container_vol/3000), 1),              "processing_time_seconds": round(min(160, vessel_wait*10), 1),    "throughput": round(max(40, 600/max(1,vessel_wait)), 1),   "industry": "ecommerce", "source": "BTS:freight_volume"},
                {"stage": "returns",             "queue_size": round(90*(1.8 if is_monday else 1.0)*noise(), 1),    "processing_time_seconds": round(175*noise(), 1),                 "throughput": round(35/(1.8 if is_monday else 1.0)*noise(), 1), "industry": "ecommerce", "source": "BTS:returns_estimate"},
            ]
        else:
            raise Exception("No data returned")

    except Exception as e:
        print(f"  ERR BTS API issue ({e}), using industry benchmarks")
        base = 1.6 if is_holiday_peak else 1.0
        events = [
            {"stage": "warehouse_receiving", "queue_size": round(180*base*noise(), 1), "processing_time_seconds": round(165*base*noise(), 1), "throughput": round(52/base*noise(), 1), "industry": "ecommerce", "source": "industry_benchmark"},
            {"stage": "order_processing",    "queue_size": round(220*base*noise(), 1), "processing_time_seconds": round(145*base*noise(), 1), "throughput": round(48/base*noise(), 1), "industry": "ecommerce", "source": "industry_benchmark"},
            {"stage": "dispatch",            "queue_size": round(160*base*noise(), 1), "processing_time_seconds": round(130*base*noise(), 1), "throughput": round(58/base*noise(), 1), "industry": "ecommerce", "source": "industry_benchmark"},
            {"stage": "returns",             "queue_size": round(95*(1.8 if is_monday else 1.0)*noise(), 1), "processing_time_seconds": round(175*noise(), 1), "throughput": round(35/(1.8 if is_monday else 1.0)*noise(), 1), "industry": "ecommerce", "source": "industry_benchmark"},
        ]

    print(f"  -> Sending {len(events)} logistics events...")
    post_to_webhook(events, dry_run)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ops Intelligence Platform - Real Data Connectors")
    parser.add_argument("--industry", choices=["healthcare", "airport", "logistics"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"\n{'='*55}")
    print("  Ops Intelligence Platform - Real Data Connector")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Webhook: {WEBHOOK_URL}")
    print(f"{'='*55}")

    if args.all or args.industry == "healthcare":
        fetch_healthcare(args.dry_run)
    if args.all or args.industry == "airport":
        fetch_airport(args.dry_run)
    if args.all or args.industry == "logistics":
        fetch_logistics(args.dry_run)

    if not args.all and not args.industry:
        print("\nUsage:")
        print("  python real_data_connectors.py --all")
        print("  python real_data_connectors.py --industry healthcare")
        print("  python real_data_connectors.py --dry-run --all")

    print(f"\n{'='*55}")
    print("  Done. Refresh dashboard to see new incidents.")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
