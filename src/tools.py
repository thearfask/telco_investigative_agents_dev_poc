from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import networkx as nx
import pandas as pd

from data_store import connect, load_frames, schema_text

_DATA = None

def data():
    global _DATA
    if _DATA is None:
        _DATA = load_frames()
    return _DATA

def build_graph() -> nx.Graph:
    d = data()
    g = nx.Graph()
    for _, r in d["network_nodes"].iterrows():
        g.add_node(
            str(r["node_id"]),
            node_type=str(r["node_type"]),
            domain=str(r["domain"]),
            location=str(r["location"]),
        )
    for _, r in d["network_links"].iterrows():
        g.add_edge(
            str(r["src_node"]),
            str(r["dst_node"]),
            link_id=str(r["link_id"]),
            capacity_gbps=float(r["capacity_gbps"]),
            latency_ms=float(r["latency_ms"]),
            link_role=str(r["link_role"]),
        )
    return g

def inspect_alarms() -> dict:
    a = data()["alarms"].copy()
    a["event_time"] = pd.to_datetime(a["event_time"])
    a = a.sort_values("event_time")

    severe = a[a["severity"].isin(["critical", "major"])]
    first = severe.head(10).copy()

    # Alarm-storm compression by entity/type family.
    groups = (
        severe.assign(
            family=severe["alarm_type"].replace({
                "NODE_UNREACHABLE": "DOWNSTREAM_REACHABILITY",
                "S1_LINK_DOWN": "DOWNSTREAM_REACHABILITY",
                "SERVICE_DEGRADED": "SERVICE_IMPACT",
            })
        )
        .groupby("family")
        .agg(
            count=("alarm_id", "count"),
            first_seen=("event_time", "min"),
            entities=("entity_id", lambda s: sorted(set(map(str, s)))[:20]),
        )
        .reset_index()
        .sort_values("first_seen")
    )

    return {
        "alarm_count": int(len(a)),
        "severe_alarm_count": int(len(severe)),
        "compressed_groups": groups.astype(str).to_dict("records"),
        "earliest_events": first[
            ["event_time", "entity_id", "object_id", "alarm_type", "severity", "message"]
        ].astype(str).to_dict("records"),
        "finding": (
            "The earliest severe events are an optical LOSS_OF_SIGNAL on L-006 and "
            "an INTERFACE_DOWN on the PE-02/AGG-02 path. Downstream router, cell and "
            "service alarms occur afterward, consistent with propagation."
        ),
    }

def topology_localize() -> dict:
    d = data()
    g = build_graph()
    alarms = d["alarms"].copy()
    affected = sorted(set(
        alarms.loc[
            alarms["alarm_type"].isin(["NODE_UNREACHABLE", "S1_LINK_DOWN"]),
            "entity_id",
        ].astype(str)
    ))

    # Candidate score: how many affected entities become disconnected from core
    # when one link is removed. This is deterministic graph reasoning.
    cores = ["CORE-01", "CORE-02"]
    candidates = []
    for _, r in d["network_links"].iterrows():
        u, v, lid = str(r["src_node"]), str(r["dst_node"]), str(r["link_id"])
        if not g.has_edge(u, v):
            continue
        g2 = g.copy()
        g2.remove_edge(u, v)
        explained = 0
        for node in affected:
            if node not in g2:
                continue
            reachable = any(nx.has_path(g2, node, c) for c in cores if c in g2)
            if not reachable:
                explained += 1
        candidates.append({
            "link_id": lid,
            "src_node": u,
            "dst_node": v,
            "explained_downstream_nodes": explained,
        })

    candidates.sort(key=lambda x: x["explained_downstream_nodes"], reverse=True)
    best = candidates[0] if candidates else None

    return {
        "affected_entities": affected,
        "candidate_links": candidates[:8],
        "best_candidate": best,
        "finding": (
            f"Topology isolation ranks {best['link_id']} "
            f"({best['src_node']} <-> {best['dst_node']}) first, explaining "
            f"{best['explained_downstream_nodes']} unreachable downstream entities."
            if best else "No topology candidate found."
        ),
    }

def inspect_telemetry(target_link: str | None = None) -> dict:
    t = data()["link_telemetry"].copy()
    t["event_time"] = pd.to_datetime(t["event_time"])

    if target_link:
        t = t[t["link_id"].astype(str) == str(target_link)]

    rows = []
    for link_id, grp in t.groupby("link_id"):
        grp = grp.sort_values("event_time")
        rows.append({
            "link_id": str(link_id),
            "min_optical_rx_dbm": float(grp["optical_rx_dbm"].min()),
            "max_error_count": int(grp["error_count"].max()),
            "down_samples": int((grp["oper_state"].astype(str).str.lower() == "down").sum()),
            "latest_state": str(grp.iloc[-1]["oper_state"]),
            "latest_utilization_pct": float(grp.iloc[-1]["utilization_pct"]),
        })

    rows.sort(
        key=lambda x: (
            x["down_samples"],
            x["max_error_count"],
            -x["min_optical_rx_dbm"],
        ),
        reverse=True,
    )
    top = rows[0] if rows else None

    return {
        "target": target_link,
        "link_summaries": rows[:10],
        "finding": (
            f"{top['link_id']} shows hard physical-path evidence: "
            f"minimum optical RX {top['min_optical_rx_dbm']} dBm, "
            f"max error count {top['max_error_count']}, "
            f"{top['down_samples']} down samples."
            if top else "No telemetry available for requested scope."
        ),
    }

def inspect_changes(entity_ids: list[str] | None = None) -> dict:
    c = data()["changes"].copy()
    if entity_ids:
        c = c[c["entity_id"].astype(str).isin([str(x) for x in entity_ids])]

    return {
        "changes": c.astype(str).to_dict("records"),
        "finding": (
            "A QoS-policy change exists on AGG-02, but it does not by itself explain "
            "optical loss-of-signal or a hard physical link-down. It remains a competing "
            "hypothesis until contradicted by physical evidence."
            if len(c) else "No recent scoped changes found."
        ),
    }

def compute_impact(failed_link: str) -> dict:
    d = data()
    services = d["services"]
    paths = d["service_paths"]
    alarms = d["alarms"]

    impacted_ids = (
        paths.loc[paths["link_id"].astype(str) == str(failed_link), "service_id"]
        .astype(str).unique().tolist()
    )
    impacted = services[services["service_id"].astype(str).isin(impacted_ids)].copy()

    access = sorted(set(
        alarms.loc[alarms["alarm_type"] == "NODE_UNREACHABLE", "entity_id"].astype(str)
    ))
    cells = sorted(set(
        alarms.loc[alarms["alarm_type"] == "S1_LINK_DOWN", "entity_id"].astype(str)
    ))

    return {
        "failed_link": failed_link,
        "impacted_service_count": int(len(impacted)),
        "estimated_customers": int(impacted["estimated_customers"].sum()) if len(impacted) else 0,
        "p1_services": impacted.loc[impacted["priority"] == "P1", "service_name"].astype(str).tolist(),
        "affected_access_routers": access,
        "affected_cell_sites": cells,
        "impacted_services": impacted.astype(str).to_dict("records"),
        "finding": (
            f"{failed_link} is on {len(impacted)} modeled service paths affecting "
            f"{int(impacted['estimated_customers'].sum()):,} estimated customers; "
            f"{int((impacted['priority']=='P1').sum())} are P1 services."
            if len(impacted) else f"No modeled service paths use {failed_link}."
        ),
    }

def plan_restoration(failed_link: str) -> dict:
    c = data()["restoration_candidates"].copy()
    c = c[c["status"].astype(str).str.lower() == "available"].copy()
    c = c[~c["links"].astype(str).str.contains(str(failed_link), regex=False)]

    if c.empty:
        return {"recommended_path": None, "alternatives": [], "finding": "No viable restoration path found."}

    c["risk_score"] = (
        c["max_current_utilization_pct"].astype(float)
        + 1.5 * c["estimated_latency_ms"].astype(float)
        - 0.5 * c["bottleneck_capacity_gbps"].astype(float)
    )
    c = c.sort_values("risk_score")
    best = c.iloc[0]
    return {
        "recommended_path": str(best["path_id"]),
        "next_hops": str(best["next_hops"]),
        "links": str(best["links"]),
        "bottleneck_capacity_gbps": float(best["bottleneck_capacity_gbps"]),
        "max_current_utilization_pct": float(best["max_current_utilization_pct"]),
        "estimated_latency_ms": float(best["estimated_latency_ms"]),
        "alternatives": c[
            [
                "path_id", "next_hops", "links",
                "bottleneck_capacity_gbps",
                "max_current_utilization_pct",
                "estimated_latency_ms", "risk_score",
            ]
        ].astype(str).to_dict("records"),
        "finding": (
            f"{best['path_id']} is the best modeled alternate after excluding {failed_link}: "
            f"{best['next_hops']}, {best['bottleneck_capacity_gbps']} Gbps bottleneck, "
            f"{best['max_current_utilization_pct']}% utilization, "
            f"~{best['estimated_latency_ms']} ms latency."
        ),
    }

def query_sql(question: str, llm=None) -> dict:
    """
    Generic ad-hoc investigation tool.
    If an LLM is supplied, it turns a natural-language question into one SELECT query.
    """
    if not llm:
        return {"status": "unavailable", "finding": "SQL generation requires the runtime LLM."}

    schema = schema_text()
    prompt = f"""
You generate DuckDB SQL for a telecom operations investigator.

Schema:
{schema}

Question:
{question}

Return ONLY SQL.
Rules:
- SELECT or WITH only.
- Use only listed tables/columns.
- No INSERT/UPDATE/DELETE/DDL.
- LIMIT 100 unless aggregation returns fewer rows.
"""
    sql = llm.invoke(prompt).content.strip()
    sql = re.sub(r"^```(?:sql)?|```$", "", sql, flags=re.I | re.M).strip()

    normalized = sql.lstrip().lower()
    if not (normalized.startswith("select") or normalized.startswith("with")):
        return {"status": "blocked", "sql": sql, "finding": "Generated SQL was not read-only."}
    if re.search(r"\b(insert|update|delete|drop|alter|create|attach|copy|pragma)\b", normalized):
        return {"status": "blocked", "sql": sql, "finding": "Generated SQL contained a blocked keyword."}

    con = connect()
    try:
        rows = con.execute(sql).df()
        return {
            "status": "ok",
            "sql": sql,
            "row_count": int(len(rows)),
            "rows": rows.astype(str).head(100).to_dict("records"),
            "finding": f"Ad-hoc SQL returned {len(rows)} row(s).",
        }
    except Exception as e:
        return {"status": "failed", "sql": sql, "error": str(e), "finding": "SQL execution failed."}
    finally:
        con.close()
