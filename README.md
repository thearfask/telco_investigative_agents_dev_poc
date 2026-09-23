# Telco Fault Investigator V2 — Agentic War Room

A topology-aware, evidence-grounded telecom incident investigation portal.

## What changed from V1

V1 was a fixed deterministic workflow.

V2 adds:
- an **Incident Commander AI agent** that decides what evidence to request next;
- specialist tools for alarms, topology, telemetry, changes, impact, restoration and SQL;
- bounded LangGraph reasoning loop;
- explicit observed / inferred / ruled-out evidence;
- DuckDB operational store generated from CSVs;
- interactive topology map showing fault, blast radius and restoration path;
- an operator-friendly "war room" UI and agent timeline;
- deterministic fallback mode when no API key is supplied.

The key design principle is intentional:

> AI decides what to investigate and how to interpret ambiguity. Deterministic algorithms perform graph traversal, SQL, scoring and path calculations.

## Run

```bash
uv sync
uv run streamlit run src/app.py
```

Enter an OpenAI API key in the sidebar to enable the true agentic planner.
Without a key, the same portal runs in deterministic demo mode.

## Demo scenario

`INC-DEMO-001` contains:
- a real root-cause alarm on link `L-006`;
- propagated access/cell/service alarms;
- unrelated alarm noise;
- a recent but non-causal QoS change;
- telemetry showing optical deterioration and hard link-down;
- alternate restoration paths.

The evaluator-only ground truth is never loaded by the investigator.

## Architecture

```text
Incident
   |
   v
Incident Commander Agent
   |
   +--> Alarm Correlator
   +--> Topology Localizer
   +--> Telemetry Inspector
   +--> Change Investigator
   +--> Blast Radius Engine
   +--> Restoration Planner
   +--> Generic SQL Tool
   |
   v
Compact Evidence State
   |
   +--> ask for more evidence
   |
   +--> conclude
```

## Next scale step

Replace the 56-node demo with generated 5k–50k node topologies and inject randomized failures.
Keep the same tool contracts and evaluation metrics.


## V4 incident management

V4 persists incidents and investigation runs in the same local DuckDB database.

New tables:
- `incidents`
- `incident_runs`

The sidebar includes **New Incident**. Paste a real/synthetic NOC ticket, save it, and it becomes selectable from the command center. Manual incidents are runnable with the same LangGraph investigation workflow. Completed investigation JSON is also persisted, so reopening an incident can restore the latest run.

For the current demo, all incidents still investigate against the same synthetic operational dataset. That is intentional for the next test step; the incident database and run history are now separated from the network evidence tables.
