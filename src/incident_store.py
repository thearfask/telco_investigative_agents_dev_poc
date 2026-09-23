from __future__ import annotations

from datetime import datetime
import json
import uuid

from data_store import connect


def ensure_incident_tables() -> None:
    con = connect(read_only=False)
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id VARCHAR PRIMARY KEY,
                title VARCHAR NOT NULL,
                priority VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                region VARCHAR,
                category VARCHAR,
                summary VARCHAR,
                incident_text VARCHAR NOT NULL,
                started VARCHAR,
                duration VARCHAR,
                services INTEGER DEFAULT 0,
                customers BIGINT DEFAULT 0,
                alarm_count INTEGER DEFAULT 0,
                confidence DOUBLE DEFAULT 0,
                root_cause VARCHAR,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                source VARCHAR NOT NULL DEFAULT 'manual'
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS incident_runs (
                run_id VARCHAR PRIMARY KEY,
                incident_id VARCHAR NOT NULL,
                mode VARCHAR,
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                elapsed_seconds DOUBLE,
                result_json VARCHAR,
                status VARCHAR NOT NULL DEFAULT 'running'
            )
        """)
    finally:
        con.close()


def seed_incidents(seed_rows: list[dict]) -> None:
    """Insert built-in demo incidents once; do not overwrite user edits."""
    ensure_incident_tables()
    con = connect(read_only=False)
    now = datetime.utcnow()
    try:
        for inc in seed_rows:
            exists = con.execute(
                "SELECT 1 FROM incidents WHERE incident_id = ?",
                [inc["incident_id"]],
            ).fetchone()
            if exists:
                continue
            incident_text = inc.get("incident_text") or (
                f"{inc['incident_id']} | {inc.get('priority','P2')}\n"
                f"{inc.get('summary','')}"
            )
            con.execute("""
                INSERT INTO incidents (
                    incident_id,title,priority,status,region,category,summary,
                    incident_text,started,duration,services,customers,alarm_count,
                    confidence,root_cause,created_at,updated_at,source
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, [
                inc["incident_id"],
                inc.get("title", inc["incident_id"]),
                inc.get("priority", "P2"),
                inc.get("status", "Open"),
                inc.get("region", "UNKNOWN"),
                inc.get("category", "Unknown"),
                inc.get("summary", ""),
                incident_text,
                inc.get("started", ""),
                inc.get("duration", ""),
                int(inc.get("services", 0) or 0),
                int(inc.get("customers", 0) or 0),
                int(inc.get("alarm_count", 0) or 0),
                float(inc.get("confidence", 0) or 0),
                inc.get("root_cause", ""),
                now,
                now,
                "seed",
            ])
    finally:
        con.close()


def list_incidents(limit: int = 50) -> list[dict]:
    ensure_incident_tables()
    con = connect()
    try:
        df = con.execute("""
            SELECT *
            FROM incidents
            ORDER BY
              CASE priority WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END,
              created_at DESC
            LIMIT ?
        """, [limit]).df()
        return df.to_dict("records")
    finally:
        con.close()


def get_incident(incident_id: str) -> dict | None:
    ensure_incident_tables()
    con = connect()
    try:
        df = con.execute(
            "SELECT * FROM incidents WHERE incident_id = ?",
            [incident_id],
        ).df()
        return None if df.empty else df.iloc[0].to_dict()
    finally:
        con.close()


def create_incident(
    incident_text: str,
    title: str,
    priority: str = "P1",
    region: str = "UNKNOWN",
    category: str = "Unknown",
    status: str = "Open",
    incident_id: str | None = None,
) -> dict:
    ensure_incident_tables()
    now = datetime.utcnow()
    if not incident_id:
        incident_id = f"INC-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    con = connect(read_only=False)
    try:
        con.execute("""
            INSERT INTO incidents (
                incident_id,title,priority,status,region,category,summary,
                incident_text,started,duration,services,customers,alarm_count,
                confidence,root_cause,created_at,updated_at,source
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, [
            incident_id,
            title.strip() or "Untitled Incident",
            priority,
            status,
            region.strip() or "UNKNOWN",
            category.strip() or "Unknown",
            incident_text.strip()[:500],
            incident_text.strip(),
            now.strftime("%H:%M:%S"),
            "0m",
            0, 0, 0, 0.0, "",
            now, now, "manual",
        ])
    finally:
        con.close()
    return get_incident(incident_id)


def update_incident_from_result(
    incident_id: str,
    result: dict,
    elapsed_seconds: float,
) -> None:
    report = result.get("final_report", {})
    tool_results = result.get("tool_results", {})
    impact = tool_results.get("compute_impact", {})
    alarms = tool_results.get("inspect_alarms", {})

    confidence_map = {"LOW": 0.45, "MEDIUM": 0.70, "HIGH": 0.92}
    confidence = confidence_map.get(str(report.get("confidence", "")).upper(), 0.0)

    con = connect(read_only=False)
    try:
        con.execute("""
            UPDATE incidents
            SET status = ?,
                services = ?,
                customers = ?,
                alarm_count = ?,
                confidence = ?,
                root_cause = ?,
                duration = ?,
                updated_at = ?
            WHERE incident_id = ?
        """, [
            "Investigated",
            int(impact.get("impacted_service_count", 0) or 0),
            int(impact.get("estimated_customers", 0) or 0),
            int(alarms.get("alarm_count", 0) or 0),
            confidence,
            str(report.get("root_cause", "")),
            f"{elapsed_seconds:.1f}s",
            datetime.utcnow(),
            incident_id,
        ])
    finally:
        con.close()


def start_run(incident_id: str, mode: str) -> str:
    ensure_incident_tables()
    run_id = f"RUN-{uuid.uuid4().hex[:10].upper()}"
    con = connect(read_only=False)
    try:
        con.execute("""
            INSERT INTO incident_runs (
                run_id,incident_id,mode,started_at,status
            ) VALUES (?,?,?,?,?)
        """, [run_id, incident_id, mode, datetime.utcnow(), "running"])
    finally:
        con.close()
    return run_id


def complete_run(run_id: str, result: dict, elapsed_seconds: float) -> None:
    con = connect(read_only=False)
    try:
        con.execute("""
            UPDATE incident_runs
            SET completed_at = ?, elapsed_seconds = ?, result_json = ?, status = ?
            WHERE run_id = ?
        """, [
            datetime.utcnow(),
            float(elapsed_seconds),
            json.dumps(result, default=str),
            "completed",
            run_id,
        ])
    finally:
        con.close()


def latest_run(incident_id: str) -> dict | None:
    ensure_incident_tables()
    con = connect()
    try:
        row = con.execute("""
            SELECT run_id, mode, started_at, completed_at, elapsed_seconds,
                   result_json, status
            FROM incident_runs
            WHERE incident_id = ?
            ORDER BY started_at DESC
            LIMIT 1
        """, [incident_id]).fetchone()
        if not row:
            return None
        result = {
            "run_id": row[0],
            "mode": row[1],
            "started_at": row[2],
            "completed_at": row[3],
            "elapsed_seconds": row[4],
            "status": row[6],
        }
        if row[5]:
            result["result"] = json.loads(row[5])
        return result
    finally:
        con.close()
