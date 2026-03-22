from __future__ import annotations

import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SUPPORTED_LIVE_INDUSTRIES = ("energy", "water", "weather", "airport", "healthcare")

SOURCE_SYSTEMS = {
    "energy": "U.S. Energy Information Administration",
    "water": "U.S. Geological Survey Water Services",
    "weather": "NOAA National Weather Service",
    "airport": "Federal Aviation Administration NAS Status",
    "healthcare": "Centers for Medicare & Medicaid Services Provider Data",
}

DEFAULT_THRESHOLDS = {
    "energy": {"queue": 20, "processing": 300, "throughput": 5},
    "water": {"queue": 15, "processing": 600, "throughput": 3},
    "weather": {"queue": 30, "processing": 900, "throughput": 2},
    "airport": {"queue": 80, "processing": 600, "throughput": 8},
    "healthcare": {"queue": 20, "processing": 3600, "throughput": 5},
}

INCIDENT_STAGE_MAP = {
    "energy": "generation_dispatch",
    "water": "distribution_pumping",
    "weather": "storm_response",
    "airport": "traffic_flow_management",
    "healthcare": "ed_triage",
}

SEVERITY_FACTORS = {
    "low": {"queue": 1.05, "processing": 1.0, "throughput": 0.95},
    "medium": {"queue": 1.2, "processing": 1.15, "throughput": 0.82},
    "high": {"queue": 1.45, "processing": 1.35, "throughput": 0.65},
    "critical": {"queue": 1.85, "processing": 1.7, "throughput": 0.45},
}

FALLBACK_INCIDENTS = {
    "energy": [
        {
            "title": "ERCOT demand spike stressing reserve margin",
            "description": "Power demand is rising materially faster than recent generation output, narrowing reserve headroom across the balancing area.",
            "severity": "high",
            "region": "Texas",
            "affected_system": "generation_dispatch",
            "user_impact": "Grid operators may need to rebalance generation and protect industrial and commercial load commitments.",
            "source_system": SOURCE_SYSTEMS["energy"],
            "external_event_id": "fallback-energy-ercot",
            "confidence": 0.71,
            "metadata": {"signal_type": "fallback_demand_spike", "demand_mw": 74250, "net_generation_mw": 68410},
        }
    ],
    "water": [
        {
            "title": "River gauge showing rapid rise near monitored flood stage",
            "description": "USGS-style monitoring indicates river level is climbing quickly and approaching a local action threshold.",
            "severity": "medium",
            "region": "Lower Mississippi Basin",
            "affected_system": "distribution_pumping",
            "user_impact": "Utility and field teams may need to monitor flood-prone assets and shift pumping plans.",
            "source_system": SOURCE_SYSTEMS["water"],
            "external_event_id": "fallback-water-lmr",
            "confidence": 0.68,
            "metadata": {"signal_type": "fallback_rapid_rise", "gage_height_ft": 21.6, "rise_ft_6h": 2.1},
        }
    ],
    "weather": [
        {
            "title": "Severe weather watch affecting regional operations",
            "description": "Active weather alerts indicate elevated storm risk with potential downstream impact on field operations and logistics.",
            "severity": "high",
            "region": "Southeast U.S.",
            "affected_system": "storm_response",
            "user_impact": "Dispatch timing, staffing, and safety-related operating windows may be constrained.",
            "source_system": SOURCE_SYSTEMS["weather"],
            "external_event_id": "fallback-weather-severe",
            "confidence": 0.73,
            "metadata": {"signal_type": "fallback_weather_alert", "alert_event": "Severe Thunderstorm Watch"},
        }
    ],
    "airport": [
        {
            "title": "Traffic management initiative delaying airport operations",
            "description": "FAA-style status signals indicate a delay program or ground management constraint at a major airport.",
            "severity": "medium",
            "region": "Northeast Corridor",
            "affected_system": "traffic_flow_management",
            "user_impact": "Passenger throughput and gate utilization may degrade as arrival and departure sequencing slips.",
            "source_system": SOURCE_SYSTEMS["airport"],
            "external_event_id": "fallback-airport-tmi",
            "confidence": 0.66,
            "metadata": {"signal_type": "fallback_delay_program", "airport_code": "JFK"},
        }
    ],
    "healthcare": [
        {
            "title": "Emergency department boarding pressure rising",
            "description": "Hospital performance indicators show elevated emergency department time-to-departure pressure relative to normal operating levels.",
            "severity": "medium",
            "region": "National sample",
            "affected_system": "ed_triage",
            "user_impact": "Patient throughput, bed assignment, and discharge coordination may slow materially.",
            "source_system": SOURCE_SYSTEMS["healthcare"],
            "external_event_id": "fallback-healthcare-ed",
            "confidence": 0.7,
            "metadata": {"signal_type": "fallback_ed_pressure", "median_minutes": 214},
        }
    ],
}


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.chunks.append(text)

    def get_text(self) -> str:
        return "\n".join(self.chunks)


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value in (None, "", "null", "None"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def parse_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        dt = value
    else:
        text = safe_str(value)
        if not text:
            return datetime.now(timezone.utc).isoformat()
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    dt = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
            else:
                return datetime.now(timezone.utc).isoformat()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def classify_severity_from_signal(signal_type: str, value: float | None = None, secondary_value: float | None = None) -> str:
    primary = value or 0.0
    secondary = secondary_value or 0.0

    if signal_type == "energy_demand_spike":
        if primary >= 25 or secondary >= 10:
            return "critical"
        if primary >= 15 or secondary >= 6:
            return "high"
        if primary >= 8 or secondary >= 3:
            return "medium"
        return "low"

    if signal_type == "energy_generation_shortfall":
        if primary <= -12:
            return "critical"
        if primary <= -8:
            return "high"
        if primary <= -4:
            return "medium"
        return "low"

    if signal_type == "energy_interchange_anomaly":
        if primary >= 2500:
            return "high"
        if primary >= 1200:
            return "medium"
        return "low"

    if signal_type == "water_level_threshold":
        if primary >= 1.5:
            return "critical"
        if primary >= 0.75:
            return "high"
        if primary >= 0.25:
            return "medium"
        return "low"

    if signal_type == "water_rapid_rise":
        if primary >= 6:
            return "critical"
        if primary >= 3:
            return "high"
        if primary >= 1.5:
            return "medium"
        return "low"

    if signal_type == "weather_alert":
        if secondary >= 3 or primary >= 3:
            return "critical"
        if secondary >= 2 or primary >= 2:
            return "high"
        if secondary >= 1 or primary >= 1:
            return "medium"
        return "low"

    if signal_type == "airport_constraint":
        if primary >= 3:
            return "critical"
        if primary >= 2:
            return "high"
        if primary >= 1:
            return "medium"
        return "low"

    if signal_type == "healthcare_strain":
        if primary >= 360:
            return "critical"
        if primary >= 300:
            return "high"
        if primary >= 210:
            return "medium"
        return "low"

    return "medium"


def build_incident_record(
    *,
    title: str,
    description: str,
    industry: str,
    severity: str,
    region: str,
    affected_system: str,
    user_impact: str,
    source_system: str,
    external_event_id: str | None,
    event_timestamp: Any,
    confidence: float,
    metadata: dict[str, Any] | None = None,
    data_mode: str = "live",
) -> dict[str, Any]:
    record = {
        "title": safe_str(title),
        "description": safe_str(description),
        "industry": safe_str(industry),
        "severity": safe_str(severity, "medium"),
        "region": safe_str(region, "Unknown"),
        "affected_system": safe_str(affected_system),
        "user_impact": safe_str(user_impact),
        "detection_source": "live_api",
        "source_system": safe_str(source_system),
        "external_event_id": safe_str(external_event_id) or None,
        "event_timestamp": parse_timestamp(event_timestamp),
        "confidence": max(0.0, min(1.0, float(confidence))),
        "metadata": metadata or {},
    }
    record["metadata"]["data_mode"] = data_mode
    return record


def build_metric_event(incident: dict[str, Any], thresholds: dict[str, float]) -> dict[str, Any]:
    severity = incident.get("severity", "medium")
    factors = SEVERITY_FACTORS.get(severity, SEVERITY_FACTORS["medium"])
    return {
        "stage": incident["affected_system"],
        "queue_size": round(thresholds["queue"] * factors["queue"], 1),
        "processing_time_seconds": round(thresholds["processing"] * factors["processing"], 1),
        "throughput": round(max(0.1, thresholds["throughput"] * factors["throughput"]), 1),
        "industry": incident["industry"],
        "source": incident["source_system"],
    }


async def fetch_live_incident_bundle(industry: str = "all") -> dict[str, Any]:
    targets = list(SUPPORTED_LIVE_INDUSTRIES) if industry == "all" else [industry]
    summary: dict[str, Any] = {}

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        for target in targets:
            if target not in SUPPORTED_LIVE_INDUSTRIES:
                summary[target] = {
                    "supported": False,
                    "data_mode": "fallback",
                    "incidents": [],
                    "metric_events": [],
                    "error": f"Industry '{target}' is not supported for live data.",
                    "source_systems": [],
                }
                continue

            try:
                incidents = await _fetch_industry(client, target)
                summary[target] = {
                    "supported": True,
                    "data_mode": "live",
                    "incidents": incidents,
                    "metric_events": [build_metric_event(incident, DEFAULT_THRESHOLDS[target]) for incident in incidents],
                    "error": None,
                    "source_systems": sorted({incident["source_system"] for incident in incidents}) or [SOURCE_SYSTEMS[target]],
                }
            except Exception as exc:
                logger.exception("Live connector failed for %s", target)
                fallback_incidents = _build_fallback_incidents(target)
                summary[target] = {
                    "supported": True,
                    "data_mode": "fallback",
                    "incidents": fallback_incidents,
                    "metric_events": [build_metric_event(incident, DEFAULT_THRESHOLDS[target]) for incident in fallback_incidents],
                    "error": str(exc),
                    "source_systems": [SOURCE_SYSTEMS[target]],
                }

    return {
        "requested_industry": industry,
        "industries": summary,
        "supported_live_industries": list(SUPPORTED_LIVE_INDUSTRIES),
    }


async def _fetch_industry(client: httpx.AsyncClient, industry: str) -> list[dict[str, Any]]:
    if industry == "energy":
        return await fetch_energy(client)
    if industry == "water":
        return await fetch_water(client)
    if industry == "weather":
        return await fetch_weather(client)
    if industry == "airport":
        return await fetch_airport(client)
    if industry == "healthcare":
        return await fetch_healthcare(client)
    raise ValueError(f"Unsupported live industry: {industry}")


def _build_fallback_incidents(industry: str) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    return [
        build_incident_record(
            title=item["title"],
            description=item["description"],
            industry=industry,
            severity=item["severity"],
            region=item["region"],
            affected_system=item["affected_system"],
            user_impact=item["user_impact"],
            source_system=item["source_system"],
            external_event_id=item["external_event_id"],
            event_timestamp=now,
            confidence=item["confidence"],
            metadata=dict(item["metadata"]),
            data_mode="fallback",
        )
        for item in FALLBACK_INCIDENTS[industry]
    ]


async def fetch_energy(client: httpx.AsyncClient | None = None) -> list[dict[str, Any]]:
    api_key = os.getenv("EIA_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("EIA_API_KEY is not configured")

    own_client = client is None
    client = client or httpx.AsyncClient(timeout=20.0, follow_redirects=True)
    try:
        params_base = {
            "api_key": api_key,
            "frequency": "hourly",
            "length": 48,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "data[0]": "value",
        }
        series_map = {"D": "demand", "NG": "generation", "TI": "interchange"}
        values_by_respondent: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(dict)

        for series_type, key in series_map.items():
            response = await client.get(
                "https://api.eia.gov/v2/electricity/rto/region-data/data/",
                params={**params_base, "facets[type][]": series_type},
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json().get("response", {}).get("data", [])
            for row in payload:
                respondent = safe_str(row.get("respondent"), "Unknown BA")
                values_by_respondent[respondent][key] = values_by_respondent[respondent].get(key, []) + [row]

        incidents: list[dict[str, Any]] = []
        for respondent, series in values_by_respondent.items():
            demand_rows = series.get("demand", [])
            generation_rows = series.get("generation", [])
            interchange_rows = series.get("interchange", [])
            if not demand_rows or not generation_rows:
                continue

            latest_demand = safe_float(demand_rows[0].get("value"), 0.0) or 0.0
            demand_baseline = _average([safe_float(row.get("value"), 0.0) for row in demand_rows[1:13]])
            latest_generation = safe_float(generation_rows[0].get("value"), 0.0) or 0.0
            latest_interchange = abs(safe_float(interchange_rows[0].get("value"), 0.0) or 0.0) if interchange_rows else 0.0
            demand_spike_pct = ((latest_demand - demand_baseline) / demand_baseline * 100) if demand_baseline else 0.0
            generation_gap_pct = ((latest_generation - latest_demand) / latest_demand * 100) if latest_demand else 0.0

            if demand_spike_pct >= 8:
                severity = classify_severity_from_signal("energy_demand_spike", demand_spike_pct, latest_demand - demand_baseline)
                incidents.append(
                    build_incident_record(
                        title=f"{respondent} demand spike above recent baseline",
                        description=f"Latest balancing authority demand is {latest_demand:.0f} MW, up {demand_spike_pct:.1f}% versus the recent trailing baseline of {demand_baseline:.0f} MW.",
                        industry="energy",
                        severity=severity,
                        region=respondent,
                        affected_system="generation_dispatch",
                        user_impact="Dispatchers may need to rebalance supply and protect downstream load commitments.",
                        source_system=SOURCE_SYSTEMS["energy"],
                        external_event_id=f"energy-demand-{respondent}-{safe_str(demand_rows[0].get('period'))}",
                        event_timestamp=demand_rows[0].get("period"),
                        confidence=0.83,
                        metadata={
                            "signal_type": "demand_spike",
                            "demand_mw": latest_demand,
                            "baseline_mw": round(demand_baseline, 1),
                            "demand_spike_pct": round(demand_spike_pct, 1),
                        },
                    )
                )

            if generation_gap_pct <= -4:
                severity = classify_severity_from_signal("energy_generation_shortfall", generation_gap_pct)
                incidents.append(
                    build_incident_record(
                        title=f"{respondent} generation running below observed demand",
                        description=f"Net generation is {latest_generation:.0f} MW against {latest_demand:.0f} MW of demand, a {abs(generation_gap_pct):.1f}% shortfall that may require imports or reserve support.",
                        industry="energy",
                        severity=severity,
                        region=respondent,
                        affected_system="load_balancing",
                        user_impact="Reserve margin is tightening and interchange dependence may increase operational risk.",
                        source_system=SOURCE_SYSTEMS["energy"],
                        external_event_id=f"energy-gap-{respondent}-{safe_str(generation_rows[0].get('period'))}",
                        event_timestamp=generation_rows[0].get("period"),
                        confidence=0.87,
                        metadata={
                            "signal_type": "generation_shortfall",
                            "generation_mw": latest_generation,
                            "demand_mw": latest_demand,
                            "generation_gap_pct": round(generation_gap_pct, 1),
                        },
                    )
                )

            if latest_interchange >= 1200:
                severity = classify_severity_from_signal("energy_interchange_anomaly", latest_interchange)
                period = interchange_rows[0].get("period") if interchange_rows else demand_rows[0].get("period")
                incidents.append(
                    build_incident_record(
                        title=f"{respondent} interchange flow materially elevated",
                        description=f"Observed interchange is {latest_interchange:.0f} MW, indicating unusual import/export dependence relative to normal balancing activity.",
                        industry="energy",
                        severity=severity,
                        region=respondent,
                        affected_system="transmission_routing",
                        user_impact="Transmission routing and balancing workflows may face additional coordination pressure.",
                        source_system=SOURCE_SYSTEMS["energy"],
                        external_event_id=f"energy-interchange-{respondent}-{safe_str(period)}",
                        event_timestamp=period,
                        confidence=0.76,
                        metadata={"signal_type": "interchange_anomaly", "interchange_mw": latest_interchange},
                    )
                )

        return incidents[:8]
    finally:
        if own_client:
            await client.aclose()


async def fetch_water(client: httpx.AsyncClient | None = None) -> list[dict[str, Any]]:
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=20.0, follow_redirects=True)
    try:
        site_configs = [
            {"site": "01646500", "name": "Potomac River at Point of Rocks, MD", "region": "Mid-Atlantic", "action_ft": 15.0},
            {"site": "07374000", "name": "Mississippi River at Baton Rouge, LA", "region": "Lower Mississippi", "action_ft": 30.0},
            {"site": "08068000", "name": "Brazos River at Richmond, TX", "region": "Texas Gulf", "action_ft": 40.0},
        ]
        headers = {"Accept": "application/json"}
        api_key = os.getenv("USGS_API_KEY", "").strip()
        if api_key:
            headers["X-API-KEY"] = api_key

        incidents: list[dict[str, Any]] = []
        for site in site_configs:
            response = await client.get(
                "https://waterservices.usgs.gov/nwis/iv/",
                params={
                    "format": "json",
                    "sites": site["site"],
                    "parameterCd": "00065,00060",
                    "period": "P2D",
                },
                headers=headers,
            )
            response.raise_for_status()
            series = response.json().get("value", {}).get("timeSeries", [])
            gage_height = _extract_usgs_values(series, "00065")
            discharge = _extract_usgs_values(series, "00060")
            if not gage_height:
                continue

            latest_height = gage_height[0]["value"]
            prior_height = gage_height[min(3, len(gage_height) - 1)]["value"] if len(gage_height) > 1 else latest_height
            rise_amount = latest_height - prior_height
            threshold_delta = latest_height - site["action_ft"]

            if threshold_delta >= 0.25:
                severity = classify_severity_from_signal("water_level_threshold", threshold_delta)
                incidents.append(
                    build_incident_record(
                        title=f"{site['name']} above action level",
                        description=f"Latest gauge height is {latest_height:.2f} ft, which is {threshold_delta:.2f} ft above the configured action level of {site['action_ft']:.2f} ft.",
                        industry="water",
                        severity=severity,
                        region=site["region"],
                        affected_system="treatment_filtration",
                        user_impact="Operators may need to review treatment, intake, and field monitoring plans as river conditions worsen.",
                        source_system=SOURCE_SYSTEMS["water"],
                        external_event_id=f"water-level-{site['site']}-{gage_height[0]['timestamp']}",
                        event_timestamp=gage_height[0]["timestamp"],
                        confidence=0.84,
                        metadata={
                            "signal_type": "above_threshold_level",
                            "site_id": site["site"],
                            "gage_height_ft": latest_height,
                            "action_level_ft": site["action_ft"],
                            "discharge_cfs": discharge[0]["value"] if discharge else None,
                        },
                    )
                )

            if rise_amount >= 1.5:
                severity = classify_severity_from_signal("water_rapid_rise", rise_amount)
                incidents.append(
                    build_incident_record(
                        title=f"{site['name']} rising rapidly",
                        description=f"Gauge height increased by {rise_amount:.2f} ft over recent readings, signaling accelerating hydrologic pressure.",
                        industry="water",
                        severity=severity,
                        region=site["region"],
                        affected_system="distribution_pumping",
                        user_impact="Rapid water movement can force changes to pumping, distribution, and field crew deployment.",
                        source_system=SOURCE_SYSTEMS["water"],
                        external_event_id=f"water-rise-{site['site']}-{gage_height[0]['timestamp']}",
                        event_timestamp=gage_height[0]["timestamp"],
                        confidence=0.8,
                        metadata={
                            "signal_type": "rapid_rise",
                            "site_id": site["site"],
                            "gage_height_ft": latest_height,
                            "rise_ft": round(rise_amount, 2),
                        },
                    )
                )

        return incidents[:8]
    finally:
        if own_client:
            await client.aclose()


async def fetch_weather(client: httpx.AsyncClient | None = None) -> list[dict[str, Any]]:
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=20.0, follow_redirects=True)
    try:
        headers = {
            "Accept": "application/geo+json",
            "User-Agent": os.getenv("NOAA_USER_AGENT", "OpsIntelligence/1.0 (ops-intelligence@example.com)"),
        }
        response = await client.get(
            "https://api.weather.gov/alerts/active",
            params={"status": "actual", "message_type": "alert"},
            headers=headers,
        )
        response.raise_for_status()
        features = response.json().get("features", [])

        incidents: list[dict[str, Any]] = []
        keyword_weights = {
            "tornado": 3,
            "hurricane": 3,
            "flash flood": 3,
            "extreme heat": 2,
            "severe thunderstorm": 2,
            "storm": 2,
            "flood": 2,
            "winter storm": 2,
            "high wind": 2,
        }
        severity_weights = {"Extreme": 3, "Severe": 2, "Moderate": 1, "Minor": 0}
        urgency_weights = {"Immediate": 3, "Expected": 2, "Future": 1}

        for feature in features[:40]:
            props = feature.get("properties") or {}
            event_name = safe_str(props.get("event"))
            area_desc = safe_str(props.get("areaDesc"), "United States")
            headline = safe_str(props.get("headline"))
            description = safe_str(props.get("description"))
            event_lower = event_name.lower()
            keyword_score = max((score for word, score in keyword_weights.items() if word in event_lower), default=0)
            severity_score = severity_weights.get(safe_str(props.get("severity")), 0)
            urgency_score = urgency_weights.get(safe_str(props.get("urgency")), 0)
            severity = classify_severity_from_signal("weather_alert", severity_score, max(keyword_score, urgency_score))

            if keyword_score == 0 and severity_score == 0 and urgency_score == 0:
                continue

            incidents.append(
                build_incident_record(
                    title=event_name or "Active NOAA weather alert",
                    description=headline or description[:240] or "NOAA issued an operationally relevant weather alert.",
                    industry="weather",
                    severity=severity,
                    region=area_desc.split(";")[0],
                    affected_system=_weather_affected_system(event_lower),
                    user_impact="Field operations, travel, staffing, and safety-related workflow windows may be constrained.",
                    source_system=SOURCE_SYSTEMS["weather"],
                    external_event_id=safe_str(props.get("id")) or safe_str(feature.get("id")) or None,
                    event_timestamp=props.get("sent") or props.get("onset") or datetime.now(timezone.utc),
                    confidence=0.9,
                    metadata={
                        "signal_type": "weather_alert",
                        "event": event_name,
                        "severity": props.get("severity"),
                        "urgency": props.get("urgency"),
                        "certainty": props.get("certainty"),
                    },
                )
            )

        return incidents[:10]
    finally:
        if own_client:
            await client.aclose()


async def fetch_airport(client: httpx.AsyncClient | None = None) -> list[dict[str, Any]]:
    if os.getenv("FAA_ENABLED", "true").lower() in {"0", "false", "no"}:
        raise RuntimeError("FAA live connector is disabled by configuration")

    own_client = client is None
    client = client or httpx.AsyncClient(timeout=20.0, follow_redirects=True)
    try:
        response = await client.get("https://www.faa.gov/delays/", headers={"User-Agent": "OpsIntelligence/1.0"})
        response.raise_for_status()
        text_parser = _HTMLTextExtractor()
        text_parser.feed(response.text)
        page_text = text_parser.get_text()
        incidents: list[dict[str, Any]] = []

        section_patterns = {
            "ground stop": r"([A-Z]{3,4}):\s*([^\n]*ground stop[^\n]*)",
            "ground delay": r"([A-Z]{3,4}):\s*([^\n]*ground delay[^\n]*)",
            "closure": r"([A-Z]{3,4}):\s*([^\n]*clsd[^\n]*)",
            "tmi": r"([A-Z]{3,4}):\s*([^\n]*TM Initiatives:[^\n]*)",
        }
        matched = False
        for signal_type, pattern in section_patterns.items():
            for airport_code, details in re.findall(pattern, page_text, flags=re.IGNORECASE):
                matched = True
                severity_value = 3 if signal_type in {"ground stop", "closure"} else 2
                incidents.append(
                    build_incident_record(
                        title=f"{airport_code} {signal_type} detected",
                        description=details.strip(),
                        industry="airport",
                        severity=classify_severity_from_signal("airport_constraint", severity_value),
                        region=airport_code,
                        affected_system="traffic_flow_management",
                        user_impact="Passenger throughput, gate planning, and downstream turn times may degrade while FAA constraints remain active.",
                        source_system=SOURCE_SYSTEMS["airport"],
                        external_event_id=f"airport-{airport_code}-{signal_type}-{datetime.now(timezone.utc).strftime('%Y%m%d%H')}",
                        event_timestamp=datetime.now(timezone.utc),
                        confidence=0.82,
                        metadata={"signal_type": signal_type, "airport_code": airport_code},
                    )
                )

        if not matched:
            return []

        return incidents[:8]
    finally:
        if own_client:
            await client.aclose()


async def fetch_healthcare(client: httpx.AsyncClient | None = None) -> list[dict[str, Any]]:
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=20.0, follow_redirects=True)
    try:
        response = await client.get(
            "https://data.cms.gov/provider-data/api/1/datastore/query/yv7e-xc69/0",
            params={
                "limit": 100,
                "filters[0][property]": "measure_id",
                "filters[0][value]": "OP_18b",
                "filters[0][operator]": "=",
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        records = response.json().get("results", [])
        valid_records = []
        for record in records:
            median_minutes = safe_float(record.get("score"))
            if median_minutes is None:
                continue
            valid_records.append((median_minutes, record))

        valid_records.sort(key=lambda item: item[0], reverse=True)

        incidents: list[dict[str, Any]] = []
        for median_minutes, record in valid_records[:6]:
            state = safe_str(record.get("state"), "US")
            hospital = safe_str(record.get("facility_name"), "Hospital")
            severity = classify_severity_from_signal("healthcare_strain", median_minutes)
            if severity == "low":
                continue

            incidents.append(
                build_incident_record(
                    title=f"{hospital} ED throughput strain",
                    description=f"CMS hospital measure OP_18b reports a median ED departure time of {median_minutes:.0f} minutes for admitted patients.",
                    industry="healthcare",
                    severity=severity,
                    region=state,
                    affected_system="ed_triage",
                    user_impact="Patient flow, bed assignment, and discharge coordination are likely under measurable strain.",
                    source_system=SOURCE_SYSTEMS["healthcare"],
                    external_event_id=f"healthcare-{safe_str(record.get('facility_id'))}-{safe_str(record.get('release_date'))}",
                    event_timestamp=record.get("release_date") or datetime.now(timezone.utc),
                    confidence=0.79,
                    metadata={
                        "signal_type": "operational_strain",
                        "facility_name": hospital,
                        "measure_id": record.get("measure_id"),
                        "median_minutes": median_minutes,
                    },
                )
            )

        return incidents
    finally:
        if own_client:
            await client.aclose()


def _average(values: list[float | None]) -> float:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else 0.0


def _extract_usgs_values(series: list[dict[str, Any]], parameter_cd: str) -> list[dict[str, Any]]:
    extracted: list[dict[str, Any]] = []
    for item in series:
        variable = item.get("variable") or {}
        variable_code = (((variable.get("variableCode") or [{}])[0]).get("value"))
        if variable_code != parameter_cd:
            continue
        values = (((item.get("values") or [{}])[0]).get("value")) or []
        for entry in values:
            value = safe_float(entry.get("value"))
            if value is None:
                continue
            extracted.append({"value": value, "timestamp": parse_timestamp(entry.get("dateTime"))})
    extracted.sort(key=lambda item: item["timestamp"], reverse=True)
    return extracted


def _weather_affected_system(event_name: str) -> str:
    if "flood" in event_name:
        return "flood_response"
    if "heat" in event_name:
        return "heat_response"
    if "hurricane" in event_name or "tropical" in event_name:
        return "hurricane_response"
    return INCIDENT_STAGE_MAP["weather"]
