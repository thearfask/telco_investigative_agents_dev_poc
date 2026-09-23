from __future__ import annotations

import json
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

from models import AgentDecision, EvidenceItem, FinalReport
from tools import (
    inspect_alarms,
    topology_localize,
    inspect_telemetry,
    inspect_changes,
    compute_impact,
    plan_restoration,
    query_sql,
)

MAX_STEPS = 8

COMMANDER_PROMPT = """
You are the Incident Commander for a telecom P1 network incident.

Your job is NOT to do graph math or invent network facts. Your job is to decide
which deterministic evidence tool should run next, based on what is already known.

Available actions:
- inspect_alarms
- localize_topology
- inspect_telemetry
- inspect_changes
- compute_impact
- plan_restoration
- query_sql
- conclude

Investigation principles:
1. Find the earliest causal event, not the loudest downstream symptom.
2. Use topology to test common-upstream hypotheses.
3. Treat recent changes as hypotheses, never automatic causes.
4. Prefer physical evidence when distinguishing physical failure from config issues.
5. Compute customer/service impact once a credible candidate exists.
6. Recommend restoration only after excluding the failed component.
7. Do not repeat a tool unless a materially different target/question exists.
8. Conclude once the root-cause hypothesis is strongly supported and impact/restoration
   are sufficiently understood.
9. If evidence is insufficient, say so rather than fabricating a cause.
"""

FINALIZER_PROMPT = """
You are a senior telecom incident commander writing an operator-facing P1 incident assessment.

Use ONLY the provided evidence. Distinguish observed facts from inference.
Do not claim that a recent change caused the outage unless the evidence supports it.
Do not claim a restoration is safe to execute automatically; recommend controlled validation.

Produce a concise, technically credible final report.
"""

class State(TypedDict, total=False):
    incident_text: str
    api_key: str
    evidence: list[dict]
    trace: list[dict]
    tool_results: dict
    steps: int
    next_decision: dict
    final_report: dict
    mode: str

def _llm(api_key: str, structured=None):
    model = ChatOpenAI(
        model="gpt-5.4-nano",
        api_key=api_key,
        temperature=0,
        reasoning_effort="low",
        max_completion_tokens=4000,
    )
    return model.with_structured_output(structured) if structured else model

def _compact(state: State) -> str:
    items = state.get("evidence", [])[-12:]
    return json.dumps(items, indent=2)

def _deterministic_decision(state: State) -> AgentDecision:
    done = set(state.get("tool_results", {}).keys())
    order = [
        ("inspect_alarms", None),
        ("localize_topology", None),
        ("inspect_telemetry", None),
        ("inspect_changes", None),
        ("compute_impact", None),
        ("plan_restoration", None),
    ]
    for action, target in order:
        if action not in done:
            return AgentDecision(action=action, reason=f"Deterministic demo sequence: collect {action} evidence.", target=target)
    return AgentDecision(action="conclude", reason="Core fault, impact, and restoration evidence are collected.")

def commander_node(state: State):
    if state.get("steps", 0) >= MAX_STEPS:
        decision = AgentDecision(action="conclude", reason="Maximum investigation steps reached.")
    elif not state.get("api_key"):
        decision = _deterministic_decision(state)
    else:
        planner = _llm(state["api_key"], AgentDecision)
        prompt = f"""
{COMMANDER_PROMPT}

INCIDENT:
{state['incident_text']}

CURRENT EVIDENCE:
{_compact(state)}

TOOLS ALREADY USED:
{json.dumps(list(state.get('tool_results', {}).keys()))}

Choose exactly one next action.
If inspect_telemetry, target the strongest candidate link when known.
If compute_impact or plan_restoration, target the strongest candidate link.
If query_sql, populate sql_question.
"""
        decision = planner.invoke(prompt)

    trace = state.get("trace", []) + [{
        "step": int(state.get("steps", 0)) + 1,
        "actor": "Incident Commander",
        "action": decision.action,
        "reason": decision.reason,
        "target": decision.target,
    }]
    return {
        "next_decision": decision.model_dump(),
        "trace": trace,
        "steps": int(state.get("steps", 0)) + 1,
    }

def _candidate_link(state: State) -> str | None:
    tr = state.get("tool_results", {})
    topo = tr.get("localize_topology", {})
    if topo.get("best_candidate"):
        return topo["best_candidate"]["link_id"]
    telem = tr.get("inspect_telemetry", {})
    summaries = telem.get("link_summaries", [])
    return summaries[0]["link_id"] if summaries else None

def tool_node(state: State):
    d = state["next_decision"]
    action = d["action"]
    target = d.get("target") or _candidate_link(state)
    results = dict(state.get("tool_results", {}))

    if action == "inspect_alarms":
        result = inspect_alarms()
    elif action == "localize_topology":
        result = topology_localize()
    elif action == "inspect_telemetry":
        result = inspect_telemetry(target)
    elif action == "inspect_changes":
        topo = results.get("localize_topology", {}).get("best_candidate") or {}
        entities = [x for x in [topo.get("src_node"), topo.get("dst_node")] if x]
        result = inspect_changes(entities)
    elif action == "compute_impact":
        result = compute_impact(target) if target else {"finding": "No fault candidate available yet."}
    elif action == "plan_restoration":
        result = plan_restoration(target) if target else {"finding": "No fault candidate available yet."}
    elif action == "query_sql":
        llm = _llm(state["api_key"]) if state.get("api_key") else None
        result = query_sql(d.get("sql_question") or "Summarize the incident evidence.", llm=llm)
    else:
        result = {"finding": "No tool executed."}

    results[action] = result

    evidence = list(state.get("evidence", []))
    finding = result.get("finding", "Tool completed.")
    evidence.append(EvidenceItem(
        id=f"E-{len(evidence)+1:02d}",
        kind="observed",
        source=action,
        statement=finding,
        confidence="HIGH" if action in {"inspect_alarms","localize_topology","inspect_telemetry","compute_impact"} else "MEDIUM",
        entities=[target] if target else [],
    ).model_dump())

    trace = state.get("trace", []) + [{
        "step": state.get("steps", 0),
        "actor": action.replace("_", " ").title(),
        "action": "evidence_returned",
        "reason": finding,
        "target": target,
    }]

    return {"tool_results": results, "evidence": evidence, "trace": trace}

def finalize_node(state: State):
    tr = state.get("tool_results", {})
    topo = tr.get("localize_topology", {})
    candidate = topo.get("best_candidate") or {}
    impact = tr.get("compute_impact", {})
    restoration = tr.get("plan_restoration", {})
    changes = tr.get("inspect_changes", {})
    alarms = tr.get("inspect_alarms", {})
    telem = tr.get("inspect_telemetry", {})

    if state.get("api_key"):
        finalizer = _llm(state["api_key"], FinalReport)
        prompt = f"""
{FINALIZER_PROMPT}

INCIDENT:
{state['incident_text']}

EVIDENCE:
{json.dumps(state.get('evidence', []), indent=2)}

TOOL RESULTS:
{json.dumps(tr, indent=2, default=str)}
"""
        report = finalizer.invoke(prompt)
    else:
        link = candidate.get("link_id", "unknown link")
        src = candidate.get("src_node", "?")
        dst = candidate.get("dst_node", "?")
        p1 = impact.get("p1_services", [])
        report = FinalReport(
            root_cause=f"Probable physical transport failure on {link} ({src} <-> {dst})",
            confidence="HIGH" if candidate and telem else "MEDIUM",
            causal_chain=[
                alarms.get("finding", "Alarm evidence unavailable."),
                topo.get("finding", "Topology evidence unavailable."),
                telem.get("finding", "Telemetry evidence unavailable."),
            ],
            blast_radius=impact.get("finding", "Impact not computed."),
            priority_services=p1,
            restoration=restoration.get("finding", "Restoration not computed."),
            evidence=[x["statement"] for x in state.get("evidence", [])],
            ruled_out=[changes.get("finding", "No change evidence collected.")],
            operator_action=(
                f"Validate optical/physical state of {link}; if confirmed failed, use controlled "
                f"restoration path {restoration.get('recommended_path','N/A')} after standard change/traffic checks."
            ),
            next_checks=[
                "Confirm optical levels at both ends and field/fiber status.",
                "Validate alternate-path headroom before reroute.",
                "Monitor customer/service recovery after restoration.",
            ],
        )

    return {"final_report": report.model_dump()}

def route_after_commander(state: State):
    return "finalize" if state["next_decision"]["action"] == "conclude" else "tool"

def build_graph():
    g = StateGraph(State)
    g.add_node("commander", commander_node)
    g.add_node("tool", tool_node)
    g.add_node("finalize", finalize_node)
    g.add_edge(START, "commander")
    g.add_conditional_edges("commander", route_after_commander, {"tool": "tool", "finalize": "finalize"})
    g.add_edge("tool", "commander")
    g.add_edge("finalize", END)
    return g.compile()

GRAPH = build_graph()

def run_investigation(incident_text: str, api_key: str = "") -> dict:
    return GRAPH.invoke({
        "incident_text": incident_text,
        "api_key": api_key.strip(),
        "evidence": [],
        "trace": [],
        "tool_results": {},
        "steps": 0,
        "mode": "agentic" if api_key.strip() else "deterministic",
    })
