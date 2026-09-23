from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

EvidenceKind = Literal["observed", "inferred", "ruled_out"]

class EvidenceItem(BaseModel):
    id: str
    kind: EvidenceKind
    source: str
    statement: str
    confidence: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    entities: list[str] = Field(default_factory=list)

class AgentDecision(BaseModel):
    action: Literal[
        "inspect_alarms",
        "localize_topology",
        "inspect_telemetry",
        "inspect_changes",
        "compute_impact",
        "plan_restoration",
        "query_sql",
        "conclude",
    ]
    reason: str
    target: str | None = None
    sql_question: str | None = None

class FinalReport(BaseModel):
    root_cause: str
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    causal_chain: list[str] = Field(default_factory=list)
    blast_radius: str
    priority_services: list[str] = Field(default_factory=list)
    restoration: str
    evidence: list[str] = Field(default_factory=list)
    ruled_out: list[str] = Field(default_factory=list)
    operator_action: str
    next_checks: list[str] = Field(default_factory=list)
