from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timedelta
import pandas as pd

# Five incident cards for the command-center landing page.
# INC-DEMO-001 uses the live investigation dataset. The remaining four are
# synthetic portfolio scenarios used to demonstrate the multi-incident portal.
INCIDENTS = [
    {
        "incident_id": "INC-DEMO-001", "title": "Metro-B Transport Outage",
        "priority": "P1", "status": "Investigating", "region": "METRO-B",
        "started": "10:02:13", "duration": "11m 42s", "services": 7,
        "customers": 29730, "alarm_count": 31, "confidence": 0.94,
        "category": "Transport", "root_cause": "PE-02 ↔ AGG-02 uplink / Link L-006",
        "summary": "Multiple mobile sites and enterprise services became unreachable within seconds.",
        "live": True,
    },
    {
        "incident_id": "INC-DEMO-002", "title": "RAN Congestion Cluster",
        "priority": "P1", "status": "Open", "region": "METRO-A",
        "started": "09:41:05", "duration": "32m 10s", "services": 4,
        "customers": 18420, "alarm_count": 47, "confidence": 0.87,
        "category": "RAN", "root_cause": "Suspected PRB saturation across ACC-03 sector cluster",
        "summary": "Mobile-data degradation and elevated BLER across a dense RAN cluster.",
        "live": False,
    },
    {
        "incident_id": "INC-DEMO-003", "title": "BGP Route Instability",
        "priority": "P2", "status": "Monitoring", "region": "CORE",
        "started": "08:53:18", "duration": "1h 19m", "services": 3,
        "customers": 8100, "alarm_count": 19, "confidence": 0.81,
        "category": "Core/IP", "root_cause": "PE-03 BGP adjacency instability",
        "summary": "Intermittent reachability and route churn affecting enterprise VPN services.",
        "live": False,
    },
    {
        "incident_id": "INC-DEMO-004", "title": "Fiber Degradation",
        "priority": "P2", "status": "Open", "region": "METRO-C",
        "started": "07:24:40", "duration": "2h 48m", "services": 5,
        "customers": 12660, "alarm_count": 26, "confidence": 0.76,
        "category": "Optical", "root_cause": "Optical degradation under investigation",
        "summary": "Increasing optical loss and packet errors without a complete link failure.",
        "live": False,
    },
    {
        "incident_id": "INC-DEMO-005", "title": "Enterprise VPN Impact",
        "priority": "P3", "status": "Resolved", "region": "METRO-A",
        "started": "06:12:02", "duration": "47m 55s", "services": 2,
        "customers": 2200, "alarm_count": 12, "confidence": 0.91,
        "category": "Service", "root_cause": "Access-path configuration mismatch",
        "summary": "Two enterprise VPN services experienced asymmetric reachability.",
        "live": False,
    },
]

def incident_by_id(incident_id: str):
    return next((x for x in INCIDENTS if x["incident_id"] == incident_id), INCIDENTS[0])

def demo_result_for(incident: dict) -> dict:
    """UI-only result for non-live scenarios. Clearly synthetic; no hidden agent claim."""
    return {
        "final_report": {
            "root_cause": incident["root_cause"],
            "confidence": "HIGH" if incident["confidence"] >= .85 else "MEDIUM",
            "causal_chain": [
                f"{incident['alarm_count']} alarms clustered around {incident['region']}.",
                f"Topology/service correlation narrowed the scope to {incident['category']}.",
                "Telemetry and dependency evidence support the displayed working hypothesis.",
            ],
            "blast_radius": f"{incident['services']} modeled services / {incident['customers']:,} estimated customers.",
            "priority_services": ["Synthetic demonstration service"],
            "restoration": "Restoration recommendation available after validating current network state.",
            "evidence": [],
            "ruled_out": ["Synthetic dashboard scenario — run INC-DEMO-001 for the live evidence-backed investigation."],
            "operator_action": "Validate the working hypothesis against current device state before any network change.",
            "next_checks": ["Inspect current telemetry", "Validate topology dependency", "Confirm service recovery criteria"],
        },
        "trace": [
            {"step":1,"actor":"Incident Commander","action":"triage","reason":"Correlate alarm storm and establish affected domain.","target":incident["region"]},
            {"step":2,"actor":"Topology Localizer","action":"evidence_returned","reason":"Identified shared dependency candidates.","target":incident["region"]},
            {"step":3,"actor":"Telemetry Analyst","action":"evidence_returned","reason":"Validated working hypothesis against KPI state.","target":incident["category"]},
            {"step":4,"actor":"Impact Engine","action":"evidence_returned","reason":f"{incident['services']} services / {incident['customers']:,} customers potentially impacted.","target":incident["region"]},
        ],
        "evidence": [],
        "tool_results": {},
        "mode": "synthetic-dashboard-preview",
    }
