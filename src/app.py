from __future__ import annotations
from pathlib import Path
import json, time
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from agents import run_investigation
from data_store import load_frames, ensure_database
from portal_data import INCIDENTS as SEED_INCIDENTS, demo_result_for
from incident_store import (
    seed_incidents, list_incidents, get_incident, create_incident,
    update_incident_from_result, start_run, complete_run, latest_run,
)
from viz import topology_figure

st.set_page_config(page_title="Telco AI War Room", page_icon="📡", layout="wide", initial_sidebar_state="expanded")
ensure_database()
frames = load_frames()
seed_incidents(SEED_INCIDENTS)
INCIDENTS = list_incidents()

# ──────────────────────────────────────────────────────────────────────────
# ICON LIBRARY — inline SVG (stroke-based, currentColor) so every icon
# inherits theme color and can be animated with pure CSS.
# ──────────────────────────────────────────────────────────────────────────
def icon(name: str, size: int = 18, cls: str = "") -> str:
    paths = {
        "radar": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.3" fill="currentColor" stroke="none"/><path d="M12 12 L19 6" class="sweep"/>',
        "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
        "map": '<path d="M9 3 3 6v15l6-3 6 3 6-3V3l-6 3-6-3Z"/><path d="M9 3v15M15 6v15"/>',
        "impact": '<path d="M13 2 3 14h7l-1 8 11-14h-7l1-6Z"/>',
        "restore": '<path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 3v6h-6"/>',
        "brain": '<path d="M9 3a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5v1a2 2 0 0 0 4 0V6a3 3 0 0 0-1-3Z"/><path d="M15 3a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5v1a2 2 0 0 1-4 0V6a3 3 0 0 1 1-3Z"/>',
        "board": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M14 8h4M14 13h4"/>',
        "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/>',
        "users": '<circle cx="9" cy="8" r="3.2"/><path d="M2.5 20c.7-3.6 3.2-5.5 6.5-5.5s5.8 1.9 6.5 5.5"/><circle cx="18" cy="9" r="2.6"/><path d="M16 14.3c2.6.3 4.3 2 4.8 4.7"/>',
        "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/>',
        "bolt": '<path d="M13 2 3 14h7l-1 8 11-14h-7l1-6Z" fill="currentColor" stroke="none"/>',
        "signal": '<path d="M4 20h2v-4H4v4Z" fill="currentColor" stroke="none"/><path d="M9 20h2V10H9v10Z" fill="currentColor" stroke="none"/><path d="M14 20h2V6h-2v14Z" fill="currentColor" stroke="none"/><path d="M19 20h2V3h-2v17Z" fill="currentColor" stroke="none"/>',
        "key": '<circle cx="8" cy="15" r="4"/><path d="M11 12 20 3M17 6l3 3M14 9l2.5 2.5"/>',
        "chevron": '<path d="m9 6 6 6-6 6"/>',
        "check": '<path d="m5 13 4 4L19 7"/>',
        "download": '<path d="M12 3v13M6 11l6 6 6-6"/><path d="M4 21h16"/>',
        "layers": '<path d="M12 2 2 8l10 6 10-6-10-6Z"/><path d="M2 14l10 6 10-6"/>',
        "compass": '<circle cx="12" cy="12" r="9"/><path d="m14.5 9.5-1.7 5.2-5.2 1.7 1.7-5.2 5.2-1.7Z"/>',
    }
    p = paths.get(name, "")
    return f'<svg class="ico {cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{p}</svg>'

# ──────────────────────────────────────────────────────────────────────────
# THEME / CSS
# ──────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg:#05080e; --bg2:#070d16; --panel:rgba(15,25,38,.62); --panel-solid:#0c1520;
  --border:rgba(255,255,255,.07); --border-strong:rgba(120,170,255,.28);
  --text:#eef4fb; --muted:#8ea0b5; --muted2:#5f7387;
  --cyan:#22d3ee; --violet:#8b5cf6; --blue:#4f8cff;
  --red:#fb4d5c; --amber:#f4b042; --green:#3ddc97;
  --glow-red: 0 0 18px rgba(251,77,92,.55); --glow-cyan: 0 0 16px rgba(34,211,238,.35);
}

html, body, [class*="css"] { font-family:'Inter',sans-serif; }
h1,h2,h3,h4,.small-title,.card-label { font-family:'Space Grotesk',sans-serif; }
code, .mono { font-family:'JetBrains Mono',monospace; }

.stApp {
  background:
    radial-gradient(ellipse 1100px 600px at 18% -10%, rgba(79,140,255,.16) 0%, transparent 55%),
    radial-gradient(ellipse 900px 700px at 100% 0%, rgba(139,92,246,.14) 0%, transparent 55%),
    repeating-linear-gradient(0deg, rgba(255,255,255,.018) 0px, rgba(255,255,255,.018) 1px, transparent 1px, transparent 34px),
    repeating-linear-gradient(90deg, rgba(255,255,255,.018) 0px, rgba(255,255,255,.018) 1px, transparent 1px, transparent 34px),
    linear-gradient(180deg, var(--bg2) 0%, var(--bg) 45%, #04070c 100%);
  color: var(--text);
}
::-webkit-scrollbar { width:9px; height:9px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:#22384d; border-radius:8px; }
::-webkit-scrollbar-thumb:hover { background:#2d4a63; }

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #081019 0%, #060b12 100%);
  border-right:1px solid var(--border);
}
[data-testid="stSidebar"] * { color:#dce6ee; }
.block-container { padding-top:4.25rem; padding-bottom:2.4rem; padding-left:2.4rem; padding-right:2.4rem; max-width:100% !important; }
[data-testid="stAppViewContainer"] > .main { width:100%; }
[data-testid="stHeader"] { background:rgba(7,13,20,.96); border-bottom:1px solid #1d2b38; }
[data-testid="stToolbar"] { top:.35rem; }

.ico { display:inline-block; vertical-align:-4px; color:var(--cyan); opacity:.95; }
.small-title .ico, .kpi-label .ico, .nav-section .ico { color:var(--cyan); }
h3 .ico, h4 .ico { color:var(--blue); margin-right:2px; }
.ico .sweep { transform-origin:12px 12px; animation: sweep 2.6s linear infinite; }
@keyframes sweep { to { transform:rotate(360deg); } }

@keyframes fadeUp { from { opacity:0; transform:translateY(8px);} to { opacity:1; transform:translateY(0);} }
.fade { animation: fadeUp .5s cubic-bezier(.2,.7,.3,1) both; }
.fade.d1 { animation-delay:.04s; } .fade.d2 { animation-delay:.09s; } .fade.d3 { animation-delay:.14s; } .fade.d4 { animation-delay:.19s; }

/* ---- Brand header ---- */
.brand-row { display:flex; align-items:center; gap:10px; margin-bottom:2px; }
.brand-mark {
  width:34px; height:34px; border-radius:9px; display:flex; align-items:center; justify-content:center;
  background:linear-gradient(145deg, rgba(79,140,255,.22), rgba(139,92,246,.22));
  border:1px solid var(--border-strong); color:var(--cyan);
}
.brand-title { font-weight:700; font-size:1.02rem; letter-spacing:-.01em; }
.brand-sub { color:var(--muted2); font-size:.74rem; margin-left:44px; margin-top:-4px; }

/* ---- Sidebar nav ---- */
.nav-section { color:#6c8098; text-transform:uppercase; font-size:.68rem; font-weight:700; letter-spacing:.09em; margin:14px 0 6px 2px; }
.nav-view { color:#5f7387; font-size:.7rem; margin-top:2px; }
[data-testid="stSidebar"] .stButton>button {
  background:transparent !important; border:1px solid transparent !important; color:#b9c8d8 !important;
  text-align:left !important; justify-content:flex-start !important; border-radius:8px !important;
  padding:8px 10px !important; font-size:.87rem !important; transition:all .15s ease !important;
}
[data-testid="stSidebar"] .stButton>button:hover {
  background:rgba(79,140,255,.1) !important; border-color:var(--border-strong) !important; color:#fff !important; transform:translateX(2px);
}
[data-testid="stSidebar"] .stButton>button:focus:not(:active) { border-color:var(--border-strong) !important; }
.nav-active [data-testid="stSidebar"] .stButton>button { background:rgba(79,140,255,.14) !important; border-color:var(--border-strong) !important; color:#fff !important; }
.live-dot { display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--red); margin-right:6px; box-shadow:var(--glow-red); animation:pulse 1.4s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:1; transform:scale(1);} 50%{opacity:.45; transform:scale(1.35);} }

/* ---- Generic panel ---- */
.panel {
  background:var(--panel); border:1px solid var(--border); border-radius:14px; padding:16px 18px;
  backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px);
  box-shadow:0 8px 24px -12px rgba(0,0,0,.5);
}
.small-title { color:#9fb0c2; text-transform:uppercase; letter-spacing:.08em; font-size:.7rem; font-weight:700; display:flex; align-items:center; gap:6px; margin-bottom:8px; }

/* ---- Hero strip ---- */
.priority-pill {
  border-radius:11px; text-align:center; padding:12px 16px; font-size:1.35rem; font-weight:800; min-width:64px;
  display:flex; align-items:center; justify-content:center;
  background:linear-gradient(155deg, rgba(251,77,92,.85), rgba(180,30,45,.85)); box-shadow:var(--glow-red);
  border:1px solid rgba(255,255,255,.15);
}
.hero-title { font-size:1.28rem; font-weight:700; letter-spacing:-.01em; margin-bottom:2px; }
.hero-meta { color:var(--muted); font-size:.83rem; }
.badge-mode {
  display:inline-flex; align-items:center; gap:6px; padding:5px 11px; border-radius:20px; font-size:.7rem; font-weight:700;
  letter-spacing:.04em; border:1px solid rgba(34,211,238,.4); color:#8fe9fb; background:rgba(34,211,238,.08);
}

/* ---- Incident cards ---- */
.incident-card {
  position:relative; border:1px solid var(--border); border-radius:12px; padding:13px 14px 12px; background:var(--panel);
  backdrop-filter:blur(10px); transition:all .18s ease; overflow:hidden; margin-bottom:8px;
}
.incident-card::before { content:""; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--edge,#3a4c5e); }
.incident-card:hover { border-color:var(--border-strong); transform:translateY(-2px); box-shadow:0 10px 26px -14px rgba(79,140,255,.5); }
.priority-p1 { color:var(--red); font-weight:800; text-shadow:0 0 10px rgba(251,77,92,.5); }
.priority-p2 { color:var(--amber); font-weight:800; }
.priority-p3 { color:var(--green); font-weight:800; }
.ic-title { font-weight:700; font-size:.93rem; margin:3px 0 3px; }
.ic-meta { color:var(--muted2); font-size:.74rem; }

/* ---- KPI cards ---- */
.kpi { border:1px solid var(--border); border-radius:13px; padding:14px 16px; background:linear-gradient(160deg, rgba(20,32,46,.75), rgba(9,16,24,.75));
  backdrop-filter:blur(10px); min-height:104px; position:relative; overflow:hidden; }
.kpi::after { content:""; position:absolute; right:-30px; top:-30px; width:90px; height:90px; border-radius:50%;
  background:radial-gradient(circle, var(--kglow,rgba(79,140,255,.25)) 0%, transparent 70%); }
.kpi-label { display:flex; align-items:center; gap:6px; color:#9fb0c2; text-transform:uppercase; font-size:.68rem; font-weight:700; letter-spacing:.07em; }
.kpi-value { font-size:1.55rem; font-weight:700; margin-top:6px; letter-spacing:-.01em; }
.kpi-delta { font-size:.76rem; color:var(--cyan); margin-top:3px; font-weight:600; }

/* ---- RCA callout ---- */
.rca { border:1px solid rgba(251,77,92,.35); border-left:4px solid var(--red); padding:13px 16px; border-radius:10px;
  background:linear-gradient(90deg, rgba(251,77,92,.1), rgba(15,20,28,.2)); }
.rca b { font-size:1.02rem; }

/* ---- Trace / reasoning ---- */
.trace { position:relative; border-left:2px solid #234a63; padding:2px 0 16px 18px; margin-left:9px; }
.trace:last-child { border-color:transparent; }
.trace-num {
  position:absolute; left:-11px; top:0; width:22px; height:22px; border-radius:50%; text-align:center; line-height:20px;
  font-size:11px; font-weight:800; background:linear-gradient(145deg,var(--cyan),var(--blue)); color:#04121c;
  box-shadow:0 0 10px rgba(34,211,238,.5); border:1px solid rgba(255,255,255,.3);
}
.trace b { font-size:.87rem; }
.muted { color:var(--muted); font-size:.86rem; }

/* ---- Tabs ---- */
.stTabs [data-baseweb="tab-list"] { gap:4px; border-bottom:1px solid var(--border); }
.stTabs [data-baseweb="tab"] { background:transparent; border:none; border-radius:8px 8px 0 0; padding:9px 16px; color:var(--muted); font-weight:600; }
.stTabs [aria-selected="true"] { background:rgba(79,140,255,.12) !important; color:#8fc4ff !important; box-shadow:inset 0 -2px 0 var(--blue); }

/* ---- Buttons ---- */
.stButton>button[kind="primary"] {
  background:linear-gradient(135deg, var(--blue), var(--violet)) !important; border:none !important;
  box-shadow:0 8px 22px -8px rgba(79,140,255,.6) !important; font-weight:700 !important; transition:transform .15s ease !important;
}
.stButton>button[kind="primary"]:hover { transform:translateY(-1px); }

hr, [data-testid="stDivider"] { border-color: var(--border) !important; }
</style>
""", unsafe_allow_html=True)

PRIORITY_EDGE = {"P1": "#fb4d5c", "P2": "#f4b042", "P3": "#3ddc97"}
NAV_ITEMS = [
    ("overview", "◈  Incident Overview", "target"),
    ("network", "◎  Network Map", "map"),
    ("impact", "⚡  Impact Analysis", "impact"),
    ("restoration", "↻  Restoration", "restore"),
]

# Session defaults
if "selected_incident" not in st.session_state:
    st.session_state.selected_incident = "INC-DEMO-001"
if "page" not in st.session_state:
    st.session_state.page = "overview"

# ──────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div class="brand-row"><div class="brand-mark">{icon('radar', 20)}</div>
    <div><div class="brand-title">Telco AI War Room</div></div></div>
    <div class="brand-sub">Autonomous Network Incident Investigator</div>
    """, unsafe_allow_html=True)
    st.divider()
    st.markdown(f'<div class="nav-section">{icon("grid",13)} Command Center</div>', unsafe_allow_html=True)
    if st.button("＋  New Incident", use_container_width=True, key="nav_new_incident"):
        st.session_state["page"] = "new_incident"; st.rerun()
    for key, label, ic in NAV_ITEMS:
        st.markdown(f'<div class="{"nav-active" if st.session_state.page == key else ""}">', unsafe_allow_html=True)
        if st.button(label, use_container_width=True, key=f"nav_{key}"):
            st.session_state["page"] = key
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    st.divider()
    st.markdown(f'<div class="nav-section">{icon("brain",13)} Agent Console</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="{"nav-active" if st.session_state.page == "reasoning" else ""}">', unsafe_allow_html=True)
    if st.button("◆  Agent Reasoning", use_container_width=True, key="nav_reasoning"):
        st.session_state["page"] = "reasoning"; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div style="margin:2px 0 8px 2px;"><span class="live-dot"></span><span style="font-size:.68rem;color:#7fb0ff;font-weight:700;letter-spacing:.05em;">LIVE</span></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="{"nav-active" if st.session_state.page == "evidence" else ""}">', unsafe_allow_html=True)
    if st.button("▤  Evidence Board", use_container_width=True, key="nav_evidence"):
        st.session_state["page"] = "evidence"; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    st.divider()
    st.markdown(f'<div class="nav-section">{icon("key",13)} Runtime</div>', unsafe_allow_html=True)
    api_key = st.text_input("OpenAI API key", type="password", help="Required for a new live agentic run.")
    st.caption("Planner model configured in agents.py")
    st.caption("DuckDB: telco_ops.duckdb")
    st.markdown(f'<div class="nav-view">{icon("compass",11)} View: <b>{st.session_state.page.replace("_"," ").title()}</b></div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────
# HERO / TOP INCIDENT STRIP
# ──────────────────────────────────────────────────────────────────────────
selected = get_incident(st.session_state.selected_incident) or INCIDENTS[0]
edge = PRIORITY_EDGE.get(selected["priority"], "#3a4c5e")

c0, c1, c2, c3 = st.columns([.45, 3.4, 1.1, .8])
with c0:
    st.markdown(f"<div class='priority-pill fade' style='background:linear-gradient(155deg, {edge}, #14202c); box-shadow:0 0 18px {edge}55;'>{selected['priority']}</div>", unsafe_allow_html=True)
with c1:
    st.markdown(f"""
    <div class="fade d1">
      <div class="hero-title">{icon('target',18)}&nbsp; {selected['incident_id']} &nbsp;·&nbsp; {selected['title']}</div>
      <div class="hero-meta">{icon('clock',13)} Started {selected['started']} &nbsp;·&nbsp; Duration {selected['duration']} &nbsp;·&nbsp; {selected['region']}</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="fade d2"><div class="small-title">{icon('bolt',13)} Investigation Mode</div>
    <span class="badge-mode">{icon('brain',13)} AGENTIC AI PLANNER</span></div>""", unsafe_allow_html=True)
with c3:
    if st.button("↺ Reset", use_container_width=True):
        for k in ["last_result", "elapsed"]:
            st.session_state.pop(k, None)
        st.rerun()

# ──────────────────────────────────────────────────────────────────────────
# INCIDENT SELECTOR ROW
# ──────────────────────────────────────────────────────────────────────────
if st.session_state.page != "new_incident":
    st.markdown(f"### {icon('board',20)} Active &amp; Recent Incidents", unsafe_allow_html=True)
    visible_incidents = INCIDENTS[:5]
    cols = st.columns(len(visible_incidents))
    for col, inc in zip(cols, visible_incidents):
        with col:
            pclass = "priority-" + str(inc.get("priority","P2")).lower()
            e = PRIORITY_EDGE.get(inc.get("priority"), "#3a4c5e")
            st.markdown(
                f"<div class='incident-card fade' style='--edge:{e};'>"
                f"<span class='{pclass}'>{inc.get('priority','P2')}</span> &nbsp; "
                f"<b class='mono' style='font-size:.82rem;'>{inc['incident_id']}</b>"
                f"<div class='ic-title'>{inc.get('title','Untitled')}</div>"
                f"<div class='ic-meta'>{icon('signal',12)} {int(inc.get('alarm_count',0) or 0)} alarms "
                f"&nbsp;·&nbsp; {int(inc.get('services',0) or 0)} services<br>"
                f"{icon('users',12)} {int(inc.get('customers',0) or 0):,} customers</div>"
                f"</div>", unsafe_allow_html=True
            )
            if st.button("Open incident →", key=f"open_{inc['incident_id']}", use_container_width=True):
                st.session_state.selected_incident = inc["incident_id"]
                st.session_state.page = "overview"
                prior = latest_run(inc["incident_id"])
                if prior and prior.get("result"):
                    st.session_state["last_result"] = prior["result"]
                    st.session_state["elapsed"] = prior.get("elapsed_seconds") or 0.0
                else:
                    st.session_state.pop("last_result", None)
                st.rerun()

selected = get_incident(st.session_state.selected_incident) or INCIDENTS[0]

# ──────────────────────────────────────────────────────────────────────────
# NEW INCIDENT
# ──────────────────────────────────────────────────────────────────────────
if st.session_state.page == "new_incident":
    st.markdown(f"### {icon('target',20)} Create New Incident", unsafe_allow_html=True)
    st.caption("Paste the NOC ticket exactly as an engineer would receive it. The incident is persisted in DuckDB and becomes available in the command center.")

    with st.form("new_incident_form", clear_on_submit=False):
        c1, c2, c3 = st.columns([2.3, .7, 1])
        with c1:
            title = st.text_input("Incident title", placeholder="e.g. Metro-B customer outage")
        with c2:
            priority = st.selectbox("Priority", ["P1","P2","P3"], index=0)
        with c3:
            region = st.text_input("Region / domain", value="UNKNOWN")

        category = st.text_input("Category", placeholder="Optional: Transport, RAN, Core/IP, Optical...")
        incident_id_input = st.text_input("Incident ID (optional)", placeholder="Leave blank to auto-generate")
        incident_text = st.text_area(
            "Incident / NOC ticket",
            height=260,
            placeholder=(
                "Paste the incident here.\n\n"
                "Example:\n"
                "Multiple mobile sites and enterprise services in Metro-B became unreachable within seconds. "
                "Alarm storm across access routers and cell sites. Three P1 services degraded. "
                "Identify the likely originating fault, blast radius and safe restoration path."
            ),
        )
        submitted = st.form_submit_button("Create incident and open war room", type="primary", use_container_width=True)

    if submitted:
        if not incident_text.strip():
            st.error("Incident text is required.")
        else:
            created = create_incident(
                incident_text=incident_text,
                title=title or incident_text.strip().splitlines()[0][:80],
                priority=priority,
                region=region,
                category=category or "Unknown",
                incident_id=incident_id_input.strip() or None,
            )
            st.session_state.selected_incident = created["incident_id"]
            st.session_state.page = "overview"
            st.session_state.pop("last_result", None)
            st.session_state.pop("elapsed", None)
            st.success(f"Created {created['incident_id']}")
            st.rerun()
    st.stop()

# ──────────────────────────────────────────────────────────────────────────
# RUN CONTROLS
# ──────────────────────────────────────────────────────────────────────────
run_col, info_col = st.columns([1, 3])
with run_col:
    if selected.get("source") == "manual" or selected["incident_id"] == "INC-DEMO-001":
        run = st.button("▶  Run AI Investigation", type="primary", use_container_width=True)
    else:
        run = False
        if st.button("▤  Load scenario dashboard", use_container_width=True):
            st.session_state["last_result"] = demo_result_for(selected)
            st.session_state["elapsed"] = 0.0
            st.rerun()
with info_col:
    if not (selected.get("source") == "manual" or selected["incident_id"] == "INC-DEMO-001"):
        st.caption(f"{icon('board',12)} This incident is a synthetic UI preview. INC-DEMO-001 is the current evidence-backed runnable scenario.", unsafe_allow_html=True)

if run:
    if not api_key.strip():
        st.warning("No API key supplied. Running the deterministic baseline. Enter a key to let the Incident Commander choose tools dynamically.")
    started = time.perf_counter()
    with st.status("🛰️ AI incident command active...", expanded=True) as status:
        
        run_mode = "agentic" if api_key.strip() else "deterministic"
        run_id = start_run(selected["incident_id"], run_mode)
        result = run_investigation(selected.get("incident_text") or selected.get("summary",""), api_key=api_key)

        for e in result.get("trace", []):
            ic = "🧠" if e.get("actor") == "Incident Commander" else "🔎"
            st.write(f"{ic} **{e.get('actor')}** — {e.get('reason')}")
        status.update(label="✅ Investigation complete", state="complete")
    st.session_state["last_result"] = result
    st.session_state["elapsed"] = time.perf_counter() - started
    complete_run(run_id, result, st.session_state["elapsed"])
    update_incident_from_result(selected["incident_id"], result, st.session_state["elapsed"])

result = st.session_state.get("last_result")
if not result:
    st.markdown(
        f"<div class='panel fade' style='display:flex;align-items:center;gap:12px;'>"
        f"{icon('radar',22)} <span>Open an incident and run/load its investigation to enter the war room.</span></div>",
        unsafe_allow_html=True,
    )
    st.stop()

report = result["final_report"]; tr = result.get("tool_results", {})
topo = tr.get("localize_topology", {}); impact = tr.get("compute_impact", {}); restoration = tr.get("plan_restoration", {})
candidate = topo.get("best_candidate") or {}
failed_link = candidate.get("link_id")
if not failed_link and selected["live"]:
    failed_link = "L-006"
affected = impact.get("affected_access_routers", []) + impact.get("affected_cell_sites", [])
restoration_links = str(restoration.get("links", "")).split("|") if restoration.get("links") else []

# ──────────────────────────────────────────────────────────────────────────
# KPI CARDS
# ──────────────────────────────────────────────────────────────────────────
def kpi_card(label, value, delta, ic_name, glow):
    return f"""
    <div class="kpi fade" style="--kglow:{glow};">
      <div class="kpi-label">{icon(ic_name,14)} {label}</div>
      <div class="kpi-value">{value}</div>
      <div class="kpi-delta">{delta}</div>
    </div>"""

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(kpi_card("Probable Root Cause", failed_link or selected["category"], f"{report['confidence']} confidence", "target", "rgba(251,77,92,.3)"), unsafe_allow_html=True)
with k2:
    st.markdown(kpi_card("Impacted Services", impact.get("impacted_service_count", selected["services"]), f"{len(impact.get('p1_services', [])) or '—'} P1", "impact", "rgba(244,176,66,.3)"), unsafe_allow_html=True)
with k3:
    st.markdown(kpi_card("Estimated Customers", f"{impact.get('estimated_customers', selected['customers']):,}", selected["region"], "users", "rgba(139,92,246,.3)"), unsafe_allow_html=True)
with k4:
    tval = f"{st.session_state.get('elapsed', 0):.2f}s" if (selected.get("source") == "manual" or selected["incident_id"] == "INC-DEMO-001") else selected["duration"]
    st.markdown(kpi_card("Investigation Time", tval, "AI-assisted", "clock", "rgba(34,211,238,.3)"), unsafe_allow_html=True)

st.write("")

page = st.session_state.get("page", "overview")

def retheme(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#dce6ee", family="Inter, sans-serif"),
        margin=dict(l=6, r=6, t=6, b=6),
        hoverlabel=dict(bgcolor="#0f1c29", bordercolor="#274058", font=dict(color="#eef4fb")),
    )
    return fig

def impact_pie(height=230):
    p1 = max(1, len(impact.get("p1_services", []))) if (selected.get("source") == "manual" or selected["incident_id"] == "INC-DEMO-001") else 3
    total = max(1, impact.get("impacted_service_count", selected["services"]))
    vals = [p1, max(0, min(2, total - p1)), max(0, total - p1 - 2)]
    fig = go.Figure(go.Pie(
        values=vals, labels=["P1", "P2", "P3"], hole=.65,
        marker=dict(colors=["#fb4d5c", "#f4b042", "#3ddc97"], line=dict(color="#0b151f", width=2)),
        textfont=dict(color="#eef4fb", size=12),
    ))
    fig.add_annotation(text=f"<b>{total}</b><br><span style='font-size:10px;color:#8ea0b5;'>services</span>", showarrow=False, font=dict(size=15, color="#eef4fb"))
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=5, b=5), paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#dce6ee"), showlegend=True, legend=dict(orientation="h", y=-.12))
    return fig

def render_reasoning_trace(height=570):
    st.markdown(f"### {icon('brain',18)} Agent Reasoning Trace", unsafe_allow_html=True)
    trace = result.get("trace", [])
    with st.container(height=height, border=True):
        for i, e in enumerate(trace, 1):
            st.markdown(
                f"<div class='trace fade'><span class='trace-num'>{i}</span><b>{e.get('actor')}</b>"
                f"<br><span class='muted'>{e.get('reason')}</span></div>", unsafe_allow_html=True
            )
        if not trace:
            st.caption("No reasoning trace available.")
    st.markdown(f"**{icon('check',14)} Decision**", unsafe_allow_html=True)
    st.success(f"{report['root_cause']}\n\n{report.get('operator_action','')}")

def render_network_map(height_note=True):
    st.markdown(f"### {icon('map',20)} Network Topology Map", unsafe_allow_html=True)
    with st.container(border=True):
        st.plotly_chart(retheme(topology_figure(failed_link, affected, restoration_links)), use_container_width=True)
    if height_note:
        st.caption(f"{icon('check',12)} Green = normal path &nbsp;·&nbsp; {icon('bolt',12)} Red = suspected failure/affected nodes &nbsp;·&nbsp; {icon('restore',12)} Blue = selected restoration candidate", unsafe_allow_html=True)

def render_impact():
    c1, c2 = st.columns([.8, 1.8])
    with c1:
        st.markdown(f"#### {icon('impact',16)} Impact Breakdown", unsafe_allow_html=True)
        st.plotly_chart(impact_pie(height=280), use_container_width=True)
    with c2:
        st.markdown(f"#### {icon('signal',16)} Top Impacted Services", unsafe_allow_html=True)
        rows = impact.get("impacted_services", [])
        if rows:
            show = pd.DataFrame(rows)
            colsel = [c for c in ["service_id", "service_name", "priority", "estimated_customers"] if c in show.columns]
            st.dataframe(show[colsel], hide_index=True, use_container_width=True, height=280)
        else:
            st.info("Detailed service impact is not attached to this synthetic preview.")
    st.markdown(f"#### {icon('layers',16)} Blast Radius", unsafe_allow_html=True)
    st.write(report.get("blast_radius"))
    if impact.get("affected_access_routers"):
        st.write("**Affected access routers:**", ", ".join(impact["affected_access_routers"]))
    if impact.get("affected_cell_sites"):
        st.write("**Affected cell sites:**", ", ".join(impact["affected_cell_sites"]))

def render_restoration():
    st.markdown(f"### {icon('restore',20)} Restoration Plan", unsafe_allow_html=True)
    st.info(report.get("restoration", "Restoration analysis pending."))
    alts = restoration.get("alternatives", [])
    if alts:
        st.dataframe(pd.DataFrame(alts), hide_index=True, use_container_width=True, height=300)
    st.markdown(f"#### {icon('bolt',16)} Operator Action", unsafe_allow_html=True)
    st.warning(report.get("operator_action"))
    st.markdown(f"#### {icon('check',16)} Required Checks Before Action", unsafe_allow_html=True)
    for x in report.get("next_checks", []):
        st.markdown(f"{icon('chevron',12)} {x}", unsafe_allow_html=True)

def render_evidence():
    st.markdown(f"### {icon('board',20)} Evidence Board", unsafe_allow_html=True)
    ev = pd.DataFrame(result.get("evidence", []))
    if not ev.empty:
        st.dataframe(ev, hide_index=True, use_container_width=True, height=360)
    else:
        st.caption("No evidence ledger attached to this synthetic preview.")
    st.markdown(f"#### {icon('chevron',16)} Ruled Out / Cautions", unsafe_allow_html=True)
    for x in report.get("ruled_out", []):
        st.markdown(f"{icon('chevron',12)} {x}", unsafe_allow_html=True)

if page == "overview":
    main, right = st.columns([2.75, 1.0])
    with main:
        st.markdown('<div class="panel fade">', unsafe_allow_html=True)
        st.markdown(f"<div class='small-title'>{icon('target',13)} Probable Root Cause</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='rca'><b>{report['root_cause']}</b><br><span class='muted'>Confidence: {selected['confidence']:.2f} · {report['confidence']}</span></div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.write("")
        render_network_map()
        st.write("")
        b1, b2, b3 = st.columns([.85, 1.2, 1.4])
        with b1:
            st.markdown(f"#### {icon('impact',16)} Impact Breakdown", unsafe_allow_html=True)
            st.plotly_chart(impact_pie(height=230), use_container_width=True)
        with b2:
            st.markdown(f"#### {icon('signal',16)} Top Impacted Services", unsafe_allow_html=True)
            rows = impact.get("impacted_services", [])
            if rows:
                show = pd.DataFrame(rows)
                colsel = [c for c in ["service_id", "service_name", "priority", "estimated_customers"] if c in show.columns]
                st.dataframe(show[colsel].head(6), hide_index=True, use_container_width=True, height=245)
            else:
                st.caption("Synthetic scenario preview — detailed service table is available for the live incident.")
        with b3:
            st.markdown(f"#### {icon('restore',16)} Restoration Options", unsafe_allow_html=True)
            alts = restoration.get("alternatives", [])
            if alts:
                st.dataframe(pd.DataFrame(alts), hide_index=True, use_container_width=True, height=245)
            else:
                st.info(report.get("restoration", "Restoration analysis pending."))
    with right:
        render_reasoning_trace(height=620)

elif page == "network":
    st.markdown('<div class="panel fade">', unsafe_allow_html=True)
    st.markdown(f"<div class='small-title'>{icon('compass',13)} Topology &amp; Dependency Analysis</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='rca'><b>{report['root_cause']}</b></div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.write("")
    render_network_map()
    st.info("Use this view during bridge calls to visually distinguish the failed dependency, downstream blast radius, and candidate restoration path.")

elif page == "impact":
    render_impact()

elif page == "restoration":
    render_restoration()

elif page == "reasoning":
    c1, c2 = st.columns([1.45, 1])
    with c1:
        render_reasoning_trace(height=640)
    with c2:
        st.markdown(f"### {icon('target',18)} Current Assessment", unsafe_allow_html=True)
        st.markdown(f"<div class='rca'><b>{report['root_cause']}</b><br><span class='muted'>{report['confidence']} confidence</span></div>", unsafe_allow_html=True)
        st.markdown(f"#### {icon('layers',16)} Causal Chain", unsafe_allow_html=True)
        for i, x in enumerate(report.get("causal_chain", []), 1):
            st.write(f"**{i}.** {x}")
        st.markdown(f"#### {icon('check',16)} Next Checks", unsafe_allow_html=True)
        for x in report.get("next_checks", []):
            st.markdown(f"{icon('chevron',12)} {x}", unsafe_allow_html=True)

elif page == "evidence":
    render_evidence()

st.divider()
tabs = st.tabs(["📋 Quick Evidence", "💥 Blast Radius", "🛠️ Restoration Detail", "🧾 Raw Audit"])
with tabs[0]:
    ev = pd.DataFrame(result.get("evidence", []))
    if not ev.empty:
        st.dataframe(ev, hide_index=True, use_container_width=True)
    else:
        st.caption("No evidence ledger attached to this synthetic preview.")
    for x in report.get("ruled_out", []):
        st.markdown(f"{icon('chevron',12)} {x}", unsafe_allow_html=True)
with tabs[1]:
    st.write(report.get("blast_radius"))
    if impact.get("affected_access_routers"):
        st.write("**Access routers:**", ", ".join(impact["affected_access_routers"]))
    if impact.get("affected_cell_sites"):
        st.write("**Cell sites:**", ", ".join(impact["affected_cell_sites"]))
with tabs[2]:
    st.write(report.get("restoration"))
    st.warning(report.get("operator_action"))
with tabs[3]:
    st.json(result)
    st.download_button("⬇ Download investigation JSON", json.dumps(result, indent=2, default=str), file_name=f"{selected['incident_id']}_investigation.json", mime="application/json")
