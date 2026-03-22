"""
Fetch free official/public live data signals and print or post summaries.

This script reuses the same connector implementation as the FastAPI backend so
scheduled runs and dashboard-triggered runs stay consistent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone

from backend.services.live_data_service import fetch_live_incident_bundle


async def _run(industry: str, dry_run: bool) -> None:
    bundle = await fetch_live_incident_bundle(industry)
    for key, result in bundle["industries"].items():
        _print_industry(key, result["incidents"], dry_run, result["data_mode"], result.get("error"))


def _print_industry(industry: str, incidents: list[dict], dry_run: bool, data_mode: str = "live", error: str | None = None) -> None:
    print(f"\n[{industry.upper()}] mode={data_mode} incidents={len(incidents)}")
    if error:
        print(f"  error: {error}")
    if dry_run:
        print(json.dumps(incidents, indent=2))
        return
    for incident in incidents[:5]:
        print(f"  - {incident['severity'].upper()} | {incident['title']} | {incident['region']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ops Intelligence - free live connector audit")
    parser.add_argument("--industry", choices=["energy", "water", "weather", "airport", "healthcare"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"\n{'=' * 60}")
    print("  Ops Intelligence Platform - Live Connector Runner")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'=' * 60}")

    target = "all" if args.all or not args.industry else args.industry
    asyncio.run(_run(target, args.dry_run))

    print(f"\n{'=' * 60}")
    print("  Done.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
