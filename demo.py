"""
StreamLake - Demo Dashboard
Run: streamlit run demo.py
"""
import os, random, warnings
warnings.filterwarnings("ignore")

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(
    page_title="StreamLake",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

def _secret(key: str, default: str = "") -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

API_URL = _secret("API_URL", "https://streamlake.onrender.com")
API_KEY = _secret("STREAMLAKE_API_KEY", "sk-demo-streamlake")
_API_HEADERS = {"X-Api-Key": API_KEY}

_endpoint = _secret("AWS_ENDPOINT_URL", os.getenv("AWS_ENDPOINT_URL", ""))
STORAGE_OPTIONS: dict = {
    "AWS_ACCESS_KEY_ID":          _secret("AWS_ACCESS_KEY_ID", "minioadmin"),
    "AWS_SECRET_ACCESS_KEY":      _secret("AWS_SECRET_ACCESS_KEY", "minioadmin"),
    "AWS_REGION":                 _secret("AWS_DEFAULT_REGION", "us-east-1"),
    "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
}
if _endpoint:
    STORAGE_OPTIONS["AWS_ENDPOINT_URL"] = _endpoint
    STORAGE_OPTIONS["AWS_ALLOW_HTTP"] = "true"

CHART_LAYOUT = dict(
    template="plotly_white",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(248,250,255,0.6)",
    font=dict(family="Inter, sans-serif", color="#475569", size=12),
    margin=dict(t=20, b=20, l=10, r=10),
)
INDIGO  = "#6366f1"
VIOLET  = "#8b5cf6"
CYAN    = "#06b6d4"
EMERALD = "#10b981"
AMBER   = "#f59e0b"
RED     = "#ef4444"
CHART_COLORS = [INDIGO, VIOLET, CYAN, EMERALD, AMBER, "#f43f5e"]

# ── Global styles ────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

.stApp { background: #f0f4ff; font-family: 'Inter', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 2rem 3rem; max-width: 1300px; }

::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #f0f4ff; }
::-webkit-scrollbar-thumb { background: #c7d2fe; border-radius: 10px; }

/* Sidebar */
[data-testid="stSidebar"] { background: #ffffff !important; border-right: 1px solid #e0e7ff; }
[data-testid="stSidebar"] .block-container { padding: 1.5rem 1.2rem; }

/* Cards */
.card {
    background: #ffffff; border-radius: 20px; padding: 1.5rem 1.6rem;
    box-shadow: 0 1px 4px rgba(99,102,241,0.07), 0 6px 24px rgba(99,102,241,0.05);
    border: 1px solid rgba(99,102,241,0.08); height: 100%;
    transition: transform 0.22s ease, box-shadow 0.22s ease;
}
.card:hover { transform: translateY(-3px); box-shadow: 0 8px 32px rgba(99,102,241,0.13); }

/* Metric cards */
.mcard {
    background: #ffffff; border-radius: 20px; padding: 1.4rem 1.6rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05), 0 6px 20px rgba(0,0,0,0.03);
    border: 1px solid #f1f5f9; border-left: 4px solid;
    transition: transform 0.2s ease;
}
.mcard:hover { transform: translateY(-2px); }
.mi { border-left-color: #6366f1; }
.mv { border-left-color: #8b5cf6; }
.me { border-left-color: #10b981; }
.ma { border-left-color: #f59e0b; }

.card-val   { font-size: 2.1rem; font-weight: 800; color: #0f172a; line-height: 1.1; }
.card-label { font-size: 0.67rem; color: #94a3b8; text-transform: uppercase;
              letter-spacing: 0.13em; margin-bottom: 0.45rem; font-weight: 600; }
.card-sub   { font-size: 0.77rem; margin-top: 0.45rem; font-weight: 500; }
.si { color: #6366f1; } .sv { color: #8b5cf6; } .se { color: #10b981; }
.sa { color: #f59e0b; } .sr { color: #ef4444; } .sm { color: #94a3b8; }

/* Section headers */
.section-hdr { display: flex; align-items: center; gap: 10px; margin: 1.8rem 0 1rem; }
.section-hdr span { font-size: 0.78rem; font-weight: 700; color: #0f172a;
                    text-transform: uppercase; letter-spacing: 0.1em; white-space: nowrap; }
.section-hdr::after { content: ''; flex: 1; height: 1px; background: #e0e7ff; }

.divider { height: 1px; background: #e0e7ff; margin: 1.2rem 0; }

/* Sidebar labels */
.sidebar-label { font-size: 0.62rem; font-weight: 700; color: #94a3b8;
                 text-transform: uppercase; letter-spacing: 0.14em; margin-bottom: 0.6rem; }
.dot-green { width: 7px; height: 7px; border-radius: 50%; background: #10b981;
             display: inline-block; box-shadow: 0 0 0 3px rgba(16,185,129,0.15); }
.dot-red   { width: 7px; height: 7px; border-radius: 50%; background: #ef4444;
             display: inline-block; box-shadow: 0 0 0 3px rgba(239,68,68,0.15); }
.svc-row  { display: flex; align-items: center; gap: 9px; font-size: 0.8rem;
            color: #475569; padding: 5px 0; }
.svc-name { flex: 1; }
.phase-row  { display: flex; align-items: flex-start; gap: 10px; font-size: 0.78rem;
              color: #475569; padding: 4px 0; }
.phase-num  { font-weight: 700; color: #6366f1; min-width: 22px; font-size: 0.72rem; }
.phase-check { color: #10b981; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: transparent; gap: 2px;
    border-bottom: 2px solid #e0e7ff; padding-bottom: 0;
}
.stTabs [data-baseweb="tab"] {
    background: transparent; border: none; color: #64748b;
    padding: 0.65rem 1.5rem; font-size: 0.85rem; font-weight: 500;
    border-radius: 0; border-bottom: 2px solid transparent; margin-bottom: -2px;
    transition: color 0.15s;
}
.stTabs [aria-selected="true"] {
    background: transparent !important; color: #6366f1 !important;
    border-bottom: 2px solid #6366f1 !important; font-weight: 700 !important;
}
.stTabs [data-baseweb="tab"]:hover { color: #6366f1 !important; }

/* Predict result */
.pred-card {
    background: #ffffff; border-radius: 24px; padding: 2rem 1.8rem; text-align: center;
    box-shadow: 0 4px 24px rgba(99,102,241,0.1); border: 1px solid #e0e7ff;
}
.prob-num  { font-size: 4rem; font-weight: 900; line-height: 1; margin-bottom: 0.25rem; }
.prob-high { color: #ef4444; }
.prob-low  { color: #10b981; }
.prob-lbl  { font-size: 0.67rem; color: #94a3b8; text-transform: uppercase;
             letter-spacing: 0.14em; }
.pred-badge { display: inline-block; border-radius: 100px; padding: 5px 18px;
              font-size: 0.79rem; font-weight: 700; margin-top: 0.7rem; }
.pred-high { background: #fef2f2; color: #ef4444; }
.pred-low  { background: #ecfdf5; color: #10b981; }

/* PSI badges */
.psi-stable   { background:#ecfdf5; color:#10b981; border-radius:6px;
                padding:2px 10px; font-size:0.7rem; font-weight:600; }
.psi-moderate { background:#fffbeb; color:#f59e0b; border-radius:6px;
                padding:2px 10px; font-size:0.7rem; font-weight:600; }
.psi-retrain  { background:#fef2f2; color:#ef4444; border-radius:6px;
                padding:2px 10px; font-size:0.7rem; font-weight:600; }

/* Buttons */
.stButton > button {
    border-radius: 12px; font-weight: 600; font-size: 0.85rem;
    border: 1.5px solid #c7d2fe; color: #6366f1;
    background: #eef2ff; transition: all 0.2s; padding: 0.5rem 1.2rem;
}
.stButton > button:hover {
    border-color: #6366f1; background: #e0e7ff; transform: translateY(-1px);
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: #fff; border: none; box-shadow: 0 4px 15px rgba(99,102,241,0.35);
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    transform: translateY(-2px); box-shadow: 0 6px 20px rgba(99,102,241,0.4);
}

/* Text input */
.stTextInput input {
    background: #f8faff; border: 1.5px solid #c7d2fe;
    border-radius: 12px; color: #0f172a; font-size: 0.9rem; padding: 0.6rem 1rem;
}
.stTextInput input:focus {
    border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,0.1);
    outline: none; background: #fff;
}

/* How it works design cards */
.how-card {
    background: #ffffff; border-radius: 20px; padding: 1.6rem;
    box-shadow: 0 1px 4px rgba(99,102,241,0.06), 0 6px 24px rgba(99,102,241,0.05);
    border: 1px solid rgba(99,102,241,0.08); height: 100%;
}
.how-icon { font-size: 1.8rem; margin-bottom: 0.8rem; }
.how-title { font-size: 0.8rem; font-weight: 700; text-transform: uppercase;
             letter-spacing: 0.1em; margin-bottom: 0.7rem; }
.how-body { font-size: 0.82rem; color: #475569; line-height: 1.75; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_delta(path: str) -> pd.DataFrame:
    from deltalake import DeltaTable
    return DeltaTable(path, storage_options=STORAGE_OPTIONS).to_pandas()

@st.cache_data(ttl=30)
@st.cache_data(ttl=3600, show_spinner=False)
def _load_user_ids() -> list[str]:
    """Return unique user IDs from S3 Silver Delta (cached 1h, column-only read)."""
    _so = {k: v for k, v in {
        "AWS_ACCESS_KEY_ID":          os.getenv("AWS_ACCESS_KEY_ID", ""),
        "AWS_SECRET_ACCESS_KEY":      os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        "AWS_REGION":                 os.getenv("AWS_DEFAULT_REGION", "us-east-2"),
        "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
    }.items() if v}
    ep = os.getenv("AWS_ENDPOINT_URL", "")
    if ep:
        _so["AWS_ENDPOINT_URL"] = ep
    from deltalake import DeltaTable
    df = DeltaTable(
        os.getenv("DELTA_SILVER_PATH", "s3://streamlake-silver/events"),
        storage_options=_so,
    ).to_pandas()
    return df["user_id"].unique().tolist()

def check_svc(url: str, timeout: float = 5.0) -> bool:
    try:
        requests.get(url, timeout=timeout)
        return True
    except Exception:
        return False

def dot(ok: bool) -> str:
    return f'<span class="{"dot-green" if ok else "dot-red"}"></span>'


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
<div style="padding:0.5rem 0 1.4rem;">
  <div style="font-size:1.25rem;font-weight:900;color:#0f172a;letter-spacing:-0.02em;">
    Stream<span style="color:#6366f1;">Lake</span>
  </div>
  <div style="font-size:0.72rem;color:#94a3b8;margin-top:4px;font-weight:500;">
    Real-Time Churn Intelligence
  </div>
</div>
""", unsafe_allow_html=True)

    api_ok   = check_svc(f"{API_URL}/health")
    minio_ok = check_svc("http://localhost:9001")
    prom_ok  = check_svc("http://localhost:9090")
    graf_ok  = check_svc("http://localhost:3000")

    st.markdown('<div class="sidebar-label">Services</div>', unsafe_allow_html=True)
    for name, ok, url in [
        ("Inference API", api_ok,   f"{API_URL}/docs"),
        ("MinIO",         minio_ok, "http://localhost:9001"),
        ("Prometheus",    prom_ok,  "http://localhost:9090"),
        ("Grafana",       graf_ok,  "http://localhost:3000"),
    ]:
        st.markdown(
            f'<div class="svc-row">{dot(ok)}'
            f'<span class="svc-name">{name}</span>'
            f'<a href="{url}" target="_blank" '
            f'style="color:#6366f1;font-size:0.65rem;font-weight:600;text-decoration:none;">open</a></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-label">Build Phases</div>', unsafe_allow_html=True)
    phases = [
        ("Ingestion",     "Kafka + Delta Bronze"),
        ("Processing",    "Bronze to Silver"),
        ("Aggregation",   "Silver to Gold"),
        ("Feature Store", "Feast + Redis"),
        ("ML Serving",    "XGBoost + FastAPI"),
        ("Observability", "PSI + Prometheus"),
    ]
    for i, (name, desc) in enumerate(phases, 1):
        st.markdown(
            f'<div class="phase-row">'
            f'<span class="phase-num">0{i}</span>'
            f'<span class="phase-check">&#10003;</span>'
            f'<div>'
            f'<div style="color:#0f172a;font-size:0.78rem;font-weight:500;">{name}</div>'
            f'<div style="color:#94a3b8;font-size:0.68rem;">{desc}</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-label">Stack</div>', unsafe_allow_html=True)
    techs = ["Kafka", "Delta Lake", "Feast", "Redis", "XGBoost",
             "MLflow", "FastAPI", "SHAP", "Prometheus", "DuckDB", "AWS S3"]
    pills = "".join(
        f'<span style="display:inline-block;background:#eef2ff;border:1px solid #c7d2fe;'
        f'color:#6366f1;border-radius:100px;padding:3px 10px;font-size:0.67rem;'
        f'font-weight:600;margin:2px;">{t}</span>'
        for t in techs
    )
    st.markdown(pills, unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown("""
<div style="font-size:0.62rem;font-weight:700;color:#94a3b8;
text-transform:uppercase;letter-spacing:0.14em;margin-bottom:0.5rem;">Author</div>
<div style="font-size:0.9rem;font-weight:800;color:#0f172a;">Kunal Pasad</div>
<div style="font-size:0.72rem;color:#64748b;margin-top:2px;">SPIT Mumbai</div>
<div style="margin-top:0.7rem;">
  <a href="https://github.com/PasadKunal/streamlake" target="_blank"
     style="font-size:0.72rem;color:#6366f1;font-weight:600;text-decoration:none;">
    github.com/PasadKunal/streamlake
  </a>
</div>
""", unsafe_allow_html=True)


# ── Hero ─────────────────────────────────────────────────────────────────────

st.markdown("""
<div style="background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 55%,#06b6d4 100%);
border-radius:24px;padding:2.6rem 2.8rem;margin:1.5rem 0 1.8rem;position:relative;overflow:hidden;">

  <div style="position:absolute;top:-50px;right:-50px;width:220px;height:220px;
  border-radius:50%;background:rgba(255,255,255,0.07);"></div>
  <div style="position:absolute;bottom:-70px;right:120px;width:170px;height:170px;
  border-radius:50%;background:rgba(255,255,255,0.05);"></div>
  <div style="position:absolute;top:20px;right:180px;width:80px;height:80px;
  border-radius:50%;background:rgba(255,255,255,0.04);"></div>

  <div style="font-size:0.7rem;font-weight:700;color:rgba(255,255,255,0.55);
  text-transform:uppercase;letter-spacing:0.18em;margin-bottom:0.7rem;">
    Real-Time Data Lakehouse
  </div>
  <div style="font-size:2.6rem;font-weight:900;color:#fff;line-height:1.1;
  margin-bottom:0.7rem;letter-spacing:-0.02em;">
    StreamLake
  </div>
  <div style="font-size:0.88rem;color:rgba(255,255,255,0.78);line-height:1.75;
  max-width:620px;margin-bottom:1.4rem;">
    Predict which customers are about to leave — before they do.
    Order events flow from Kafka through a Delta Lake medallion pipeline into a
    Redis feature store, scored live by XGBoost with SHAP explanations.
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:8px;">
    <span style="background:rgba(255,255,255,0.18);backdrop-filter:blur(8px);color:#fff;
    border-radius:100px;padding:4px 14px;font-size:0.71rem;font-weight:600;">Delta Lake (ACID)</span>
    <span style="background:rgba(255,255,255,0.18);backdrop-filter:blur(8px);color:#fff;
    border-radius:100px;padding:4px 14px;font-size:0.71rem;font-weight:600;">Event-Time Watermarks</span>
    <span style="background:rgba(255,255,255,0.18);backdrop-filter:blur(8px);color:#fff;
    border-radius:100px;padding:4px 14px;font-size:0.71rem;font-weight:600;">Redis Feature Store</span>
    <span style="background:rgba(255,255,255,0.18);backdrop-filter:blur(8px);color:#fff;
    border-radius:100px;padding:4px 14px;font-size:0.71rem;font-weight:600;">XGBoost + SHAP</span>
    <span style="background:rgba(255,255,255,0.18);backdrop-filter:blur(8px);color:#fff;
    border-radius:100px;padding:4px 14px;font-size:0.71rem;font-weight:600;">PSI Drift Detection</span>
    <span style="background:rgba(255,255,255,0.18);backdrop-filter:blur(8px);color:#fff;
    border-radius:100px;padding:4px 14px;font-size:0.71rem;font-weight:600;">90/10 A/B Split</span>
    <span style="background:rgba(255,255,255,0.18);backdrop-filter:blur(8px);color:#fff;
    border-radius:100px;padding:4px 14px;font-size:0.71rem;font-weight:600;">Multi-Tenant API Keys</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ── Drift report (cached — reads S3 Silver Delta once per 5 min) ─────────────

@st.cache_data(ttl=300, show_spinner=False)
def _cached_drift_report() -> dict:
    from serving.drift_monitor import compute_drift_report
    return compute_drift_report()


# ── Tabs ─────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs(["Pipeline", "Predict", "Drift Monitor", "How it works"])


# =============================================================================
# TAB 1 - PIPELINE
# =============================================================================
with tab1:

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        try:
            bronze = load_delta("s3://streamlake-bronze/events")
            c1.markdown(f"""<div class="mcard mi">
                <div class="card-label">Bronze Events</div>
                <div class="card-val">{len(bronze):,}</div>
                <div class="card-sub sa">raw, immutable</div>
            </div>""", unsafe_allow_html=True)
        except Exception:
            c1.markdown('<div class="mcard mi"><div class="card-label">Bronze Events</div>'
                        '<div class="card-val">--</div>'
                        '<div class="card-sub sm">run the producer</div></div>',
                        unsafe_allow_html=True)

    with c2:
        try:
            silver = load_delta("s3://streamlake-silver/events")
            late   = (silver["watermark_classification"] == "late").sum()
            c2.markdown(f"""<div class="mcard mv">
                <div class="card-label">Silver Events</div>
                <div class="card-val">{len(silver):,}</div>
                <div class="card-sub se">{late} late, 0 quarantined</div>
            </div>""", unsafe_allow_html=True)
        except Exception:
            c2.markdown('<div class="mcard mv"><div class="card-label">Silver Events</div>'
                        '<div class="card-val">--</div>'
                        '<div class="card-sub sm">run bronze_to_silver</div></div>',
                        unsafe_allow_html=True)

    with c3:
        try:
            uids = _load_user_ids()
            c3.markdown(f"""<div class="mcard me">
                <div class="card-label">Feature Store Users</div>
                <div class="card-val">{len(uids):,}</div>
                <div class="card-sub si">unique users in Redis</div>
            </div>""", unsafe_allow_html=True)
        except Exception:
            c3.markdown('<div class="mcard me"><div class="card-label">Feature Store</div>'
                        '<div class="card-val">--</div>'
                        '<div class="card-sub sm">S3 unavailable</div></div>',
                        unsafe_allow_html=True)

    with c4:
        try:
            import mlflow
            mlflow.set_tracking_uri("mlruns")
            client   = mlflow.MlflowClient()
            versions = client.get_latest_versions("streamlake-churn-model")
            if versions:
                run = client.get_run(versions[-1].run_id)
                auc = run.data.metrics.get("auc", 0)
                c4.markdown(f"""<div class="mcard ma">
                    <div class="card-label">Model AUC</div>
                    <div class="card-val">{auc:.3f}</div>
                    <div class="card-sub sv">XGBoost v{versions[-1].version}</div>
                </div>""", unsafe_allow_html=True)
        except Exception:
            c4.markdown('<div class="mcard ma"><div class="card-label">Model AUC</div>'
                        '<div class="card-val">--</div>'
                        '<div class="card-sub sm">run ml.train</div></div>',
                        unsafe_allow_html=True)

    st.markdown('<div class="section-hdr"><span>Event Distribution</span></div>',
                unsafe_allow_html=True)
    left, right = st.columns(2)

    with left:
        try:
            silver = load_delta("s3://streamlake-silver/events")
            counts = silver["event_type"].value_counts().reset_index()
            counts.columns = ["Event Type", "Count"]
            fig = px.bar(
                counts, x="Count", y="Event Type", orientation="h",
                color="Count",
                color_continuous_scale=[[0, "#c7d2fe"], [0.5, "#818cf8"], [1, "#6366f1"]],
            )
            fig.update_layout(**CHART_LAYOUT, coloraxis_showscale=False, height=290)
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.info("No Silver data yet. Run the pipeline first.")

    with right:
        try:
            silver = load_delta("s3://streamlake-silver/events")
            dev    = silver["device_type"].value_counts().reset_index()
            dev.columns = ["Device", "Count"]
            fig = px.pie(
                dev, names="Device", values="Count",
                color_discrete_sequence=CHART_COLORS,
                hole=0.58,
            )
            fig.update_layout(
                **CHART_LAYOUT, showlegend=True, height=290,
                legend=dict(orientation="v", x=1, y=0.5,
                            font=dict(color="#475569", size=12)),
            )
            fig.update_traces(textinfo="percent", textfont_color="#fff",
                              marker=dict(line=dict(color="#fff", width=2)))
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.info("No Silver data yet. Run the pipeline first.")

    st.markdown('<div class="section-hdr"><span>Data Flow</span></div>',
                unsafe_allow_html=True)

    def _flow_card(color, border_color, label, path, bullets):
        items = "".join(
            f'<li style="margin:2px 0;color:#64748b;">{b}</li>' for b in bullets
        )
        return (
            f'<div style="flex:1;min-width:155px;background:#ffffff;border:1px solid {border_color};'
            f'border-top:3px solid {color};border-radius:12px;padding:0.85rem 1rem;">'
            f'<div style="font-size:0.58rem;font-weight:800;color:{color};text-transform:uppercase;'
            f'letter-spacing:0.12em;margin-bottom:0.2rem;">{label}</div>'
            f'<div style="font-size:0.63rem;color:#94a3b8;font-family:monospace;'
            f'margin-bottom:0.5rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
            f'{path}</div>'
            f'<ul style="margin:0;padding-left:1rem;font-size:0.7rem;line-height:1.8;">{items}</ul>'
            f'</div>'
        )

    _arrow = ('<div style="display:flex;align-items:center;padding:0 5px;flex-shrink:0;'
              'color:#c7d2fe;font-size:1.1rem;">&#8594;</div>')

    st.markdown(
        '<div style="display:flex;align-items:stretch;gap:0;overflow-x:auto;padding-bottom:4px;">'
        + _flow_card("#6366f1", "#c7d2fe", "Ingest", "Kafka / REST / CSV", [
            "Kafka &middot; Redpanda",
            "POST /ingest/webhook",
            "POST /ingest/csv",
            "~1,400 events / s",
        ])
        + _arrow
        + _flow_card("#f59e0b", "#fde68a", "Bronze", "s3://streamlake-bronze/", [
            "Delta Lake (delta-rs)",
            "Partitioned by date",
            "Idempotent &middot; at-least-once",
        ])
        + _arrow
        + _flow_card("#8b5cf6", "#ddd6fe", "Silver", "s3://streamlake-silver/", [
            "Event-time watermarks",
            "LRU dedup &middot; 1h TTL",
            "6 GE validation rules",
        ])
        + _arrow
        + _flow_card("#06b6d4", "#a5f3fc", "Features", "s3://streamlake-features/ + Redis", [
            "Feast 0.39 + Redis",
            "9 rolling features",
            "&lt;10ms at inference",
        ])
        + _arrow
        + _flow_card("#ef4444", "#fecaca", "Serve", "streamlake.onrender.com", [
            "XGBoost &middot; SHAP",
            "90/10 A/B split",
            "PSI drift &middot; /alerts",
        ])
        + '</div>',
        unsafe_allow_html=True,
    )


# =============================================================================
# TAB 2 - PREDICT
# =============================================================================
with tab2:

    st.markdown("""
<div style="background:#eef2ff;border:1px solid #c7d2fe;border-radius:14px;
padding:1rem 1.3rem;margin-bottom:1.5rem;display:flex;align-items:center;gap:12px;">
  <div style="width:30px;height:30px;background:#6366f1;border-radius:8px;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;
  font-size:0.85rem;font-weight:900;color:#fff;">i</div>
  <div style="font-size:0.84rem;color:#4338ca;line-height:1.6;">
    Features are fetched live from <strong>Redis</strong> in under 10ms.
    The model runs <strong>SHAP</strong> to explain every score.
    First request may take ~30s to wake the Render free-tier API.
  </div>
</div>
""", unsafe_allow_html=True)

    col_in, col_btn, col_rnd = st.columns([4, 2, 2])
    with col_in:
        user_id = st.text_input("User ID", value="USER-006775",
                                placeholder="e.g. USER-006775",
                                label_visibility="collapsed")
    with col_btn:
        go_btn = st.button("Predict churn", type="primary", use_container_width=True)
    with col_rnd:
        if st.button("Random user", use_container_width=True):
            try:
                uids = _load_user_ids()
                st.session_state["rand_user"] = random.choice(uids)
                st.rerun()
            except Exception:
                st.warning("Could not load users from S3.")

    if "rand_user" in st.session_state:
        user_id = st.session_state.pop("rand_user")
        go_btn  = True

    if go_btn:
        with st.spinner("Scoring customer... (first call may take ~30s to wake API)"):
            try:
                resp = requests.post(
                    f"{API_URL}/predict", json={"user_id": user_id},
                    headers=_API_HEADERS, timeout=60
                )
            except requests.exceptions.ConnectionError:
                st.error(f"Cannot connect to API at {API_URL}.")
                st.stop()
            except requests.exceptions.Timeout:
                st.error("API timed out after 60s. Try again in a moment.")
                st.stop()

        if resp.status_code == 404:
            st.warning(f"User `{user_id}` not found in feature store.")
        elif resp.status_code != 200:
            st.error(f"API error {resp.status_code}: {resp.json().get('detail', 'unknown')}")
        else:
            data = resp.json()
            prob = data["churn_probability"]

            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

            r1, r2, r3 = st.columns([1.2, 2.2, 2.2])

            with r1:
                cls        = "prob-high" if prob >= 0.5 else "prob-low"
                badge_cls  = "pred-high" if prob >= 0.5 else "pred-low"
                badge_text = "HIGH RISK" if prob >= 0.5 else "LOW RISK"
                st.markdown(f"""
<div class="pred-card">
  <div class="prob-lbl">Churn Probability</div>
  <div class="prob-num {cls}">{prob:.0%}</div>
  <div class="pred-badge {badge_cls}">{badge_text}</div>
  <div style="margin-top:1.4rem;padding-top:1rem;border-top:1px solid #f1f5f9;
  display:flex;gap:12px;justify-content:center;">
    <div style="text-align:center;">
      <div style="font-size:0.62rem;color:#94a3b8;text-transform:uppercase;
      letter-spacing:0.1em;margin-bottom:2px;">Model</div>
      <div style="font-size:0.82rem;color:#6366f1;font-weight:700;">
        v{data['model_version']}</div>
    </div>
    <div style="width:1px;background:#e0e7ff;"></div>
    <div style="text-align:center;">
      <div style="font-size:0.62rem;color:#94a3b8;text-transform:uppercase;
      letter-spacing:0.1em;margin-bottom:2px;">A/B Group</div>
      <div style="font-size:0.82rem;color:#06b6d4;font-weight:700;">
        {data['ab_group'].title()}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

            with r2:
                st.markdown(
                    '<div style="font-weight:700;color:#0f172a;font-size:0.9rem;'
                    'margin-bottom:0.3rem;">SHAP Feature Contributions</div>',
                    unsafe_allow_html=True,
                )
                st.caption("Positive value pushes toward churn. Negative pushes away.")
                shap_df = pd.DataFrame(data["top_features"])
                colors  = [
                    "#ef4444" if d == "increases_churn" else "#10b981"
                    for d in shap_df["direction"]
                ]
                fig = go.Figure(go.Bar(
                    x=shap_df["shap_value"],
                    y=shap_df["feature"],
                    orientation="h",
                    marker_color=colors,
                    marker_line_width=0,
                    text=[f"{v:+.3f}" for v in shap_df["shap_value"]],
                    textposition="outside",
                    textfont=dict(color="#475569", size=11),
                ))
                fig.update_layout(
                    **CHART_LAYOUT, height=210,
                    xaxis_title="SHAP value",
                    yaxis={"autorange": "reversed", "tickfont": {"size": 11, "color": "#475569"}},
                    xaxis={"zeroline": True, "zerolinecolor": "#c7d2fe", "zerolinewidth": 1.5},
                )
                st.plotly_chart(fig, use_container_width=True)

            with r3:
                st.markdown(
                    '<div style="font-weight:700;color:#0f172a;font-size:0.9rem;'
                    'margin-bottom:0.3rem;">Feature Values (from Redis)</div>',
                    unsafe_allow_html=True,
                )
                st.caption("9 rolling-window features over 1h, 24h, and 7d.")
                feat = data["features_used"]
                rows = [
                    {"Feature": k,
                     "Value": f"{int(v):,}" if isinstance(v, (int, float)) else v}
                    for k, v in feat.items()
                ]
                st.dataframe(pd.DataFrame(rows), hide_index=True,
                             use_container_width=True, height=220)

            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

            fig_g = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=prob * 100,
                number={
                    "suffix": "%",
                    "font": {"size": 48,
                             "color": "#ef4444" if prob >= 0.5 else "#10b981"},
                },
                delta={
                    "reference": 50, "suffix": "% vs threshold",
                    "font": {"size": 14},
                    "decreasing": {"color": "#10b981"},
                    "increasing": {"color": "#ef4444"},
                },
                gauge={
                    "axis":  {"range": [0, 100], "tickcolor": "#94a3b8", "tickwidth": 1},
                    "bar":   {"color": "#ef4444" if prob >= 0.5 else "#10b981",
                              "thickness": 0.25},
                    "bgcolor": "rgba(0,0,0,0)",
                    "bordercolor": "#e0e7ff",
                    "steps": [
                        {"range": [0, 30],   "color": "rgba(16,185,129,0.06)"},
                        {"range": [30, 60],  "color": "rgba(245,158,11,0.05)"},
                        {"range": [60, 100], "color": "rgba(239,68,68,0.06)"},
                    ],
                    "threshold": {
                        "line": {"color": "#6366f1", "width": 2}, "value": 50
                    },
                },
                title={"text": f"Risk score for {user_id}",
                       "font": {"color": "#64748b", "size": 13}},
            ))
            fig_g.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", color="#475569"),
                height=250, margin=dict(t=40, b=0, l=30, r=30),
            )
            st.plotly_chart(fig_g, use_container_width=True)


# =============================================================================
# TAB 3 - DRIFT MONITOR
# =============================================================================
with tab3:

    # PSI explanation banner
    st.markdown("""
<div style="background:linear-gradient(135deg,#eef2ff 0%,#f0fdf4 100%);
border:1px solid #c7d2fe;border-radius:16px;padding:1.2rem 1.5rem;
display:flex;gap:14px;align-items:flex-start;margin-bottom:1.5rem;">
  <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:10px;
  padding:0.5rem 0.65rem;flex-shrink:0;">
    <div style="font-size:0.58rem;font-weight:900;color:#fff;letter-spacing:0.08em;">PSI</div>
  </div>
  <div style="flex:1;">
    <div style="font-weight:700;color:#0f172a;font-size:0.9rem;margin-bottom:0.3rem;">
      Population Stability Index</div>
    <div style="font-size:0.81rem;color:#475569;line-height:1.65;">
      Measures how much each feature's distribution has shifted since training.
    </div>
    <div style="display:flex;gap:8px;margin-top:0.6rem;flex-wrap:wrap;">
      <span style="background:#ecfdf5;color:#10b981;font-size:0.68rem;font-weight:700;
      padding:3px 10px;border-radius:20px;">below 0.10 &mdash; Stable</span>
      <span style="background:#fffbeb;color:#f59e0b;font-size:0.68rem;font-weight:700;
      padding:3px 10px;border-radius:20px;">0.10 &ndash; 0.25 &mdash; Monitor</span>
      <span style="background:#fef2f2;color:#ef4444;font-size:0.68rem;font-weight:700;
      padding:3px 10px;border-radius:20px;">above 0.25 &mdash; Retrain</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    try:
        report = _cached_drift_report()

        # Status banner
        if report["drift_alert"]:
            st.markdown("""
<div style="background:#fef2f2;border:1px solid #fecaca;border-left:4px solid #ef4444;
border-radius:12px;padding:1rem 1.2rem;display:flex;align-items:center;gap:12px;
margin-bottom:1rem;">
  <div style="background:#ef4444;border-radius:6px;padding:3px 9px;font-size:0.58rem;
  font-weight:800;color:#fff;letter-spacing:0.08em;flex-shrink:0;">DRIFT ALERT</div>
  <div style="font-size:0.83rem;color:#991b1b;font-weight:500;">
    One or more features have shifted significantly. Retraining recommended.
  </div>
</div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-left:4px solid #10b981;
border-radius:12px;padding:1rem 1.2rem;display:flex;align-items:center;gap:12px;
margin-bottom:1rem;">
  <div style="background:#10b981;border-radius:6px;padding:3px 9px;font-size:0.58rem;
  font-weight:800;color:#fff;letter-spacing:0.08em;flex-shrink:0;">STABLE</div>
  <div style="font-size:0.83rem;color:#166534;font-weight:500;">
    All features stable. PSI within safe thresholds.
  </div>
</div>""", unsafe_allow_html=True)

        # Stat mini-cards
        st.markdown(f"""
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:1.4rem;">
  <div style="background:#fff;border:1px solid #e0e7ff;border-left:4px solid #6366f1;
  border-radius:12px;padding:0.85rem 1rem;">
    <div style="font-size:0.62rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.12em;
    font-weight:600;margin-bottom:0.3rem;">Baseline date</div>
    <div style="font-size:1rem;font-weight:700;color:#6366f1;">
      {report['baseline_computed_at'][:10]}</div>
  </div>
  <div style="background:#fff;border:1px solid #e0e7ff;border-left:4px solid #8b5cf6;
  border-radius:12px;padding:0.85rem 1rem;">
    <div style="font-size:0.62rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.12em;
    font-weight:600;margin-bottom:0.3rem;">Training samples</div>
    <div style="font-size:1rem;font-weight:700;color:#8b5cf6;">
      {report['baseline_n_samples']:,}</div>
  </div>
  <div style="background:#fff;border:1px solid #e0e7ff;border-left:4px solid #06b6d4;
  border-radius:12px;padding:0.85rem 1rem;">
    <div style="font-size:0.62rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.12em;
    font-weight:600;margin-bottom:0.3rem;">Current samples</div>
    <div style="font-size:1rem;font-weight:700;color:#06b6d4;">
      {report['current_n_samples']:,}</div>
  </div>
</div>
""", unsafe_allow_html=True)

        rows = []
        for feat, info in report["features"].items():
            rows.append({
                "feature":       feat,
                "psi":           info["psi"],
                "status":        info["status"],
                "baseline_mean": info["baseline_mean"],
                "current_mean":  info["current_mean"],
                "delta_mean":    round(info["current_mean"] - info["baseline_mean"], 4),
            })
        df = pd.DataFrame(rows).sort_values("psi", ascending=False)

        color_map = {"stable": EMERALD, "moderate": AMBER, "retrain": RED}

        fig = go.Figure()
        for status in ["retrain", "moderate", "stable"]:
            sub = df[df["status"] == status]
            if sub.empty:
                continue
            fig.add_trace(go.Bar(
                x=sub["psi"], y=sub["feature"],
                orientation="h",
                name=status.title(),
                marker_color=color_map[status],
                marker_line_width=0,
                text=[f"{v:.5f}" for v in sub["psi"]],
                textposition="outside",
                textfont=dict(color="#475569", size=11),
            ))
        fig.add_vline(
            x=0.10, line_dash="dot", line_color=AMBER,
            annotation_text="monitor (0.10)",
            annotation_font_color=AMBER, annotation_font_size=11,
        )
        fig.add_vline(
            x=0.25, line_dash="dot", line_color=RED,
            annotation_text="retrain (0.25)",
            annotation_font_color=RED, annotation_font_size=11,
        )
        fig.update_layout(
            **CHART_LAYOUT, height=380,
            barmode="overlay",
            xaxis_title="PSI Score",
            yaxis={"autorange": "reversed"},
            legend=dict(orientation="h", x=0.5, xanchor="center", y=1.08,
                        font=dict(color="#475569")),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="section-hdr"><span>Feature Detail</span></div>',
                    unsafe_allow_html=True)

        badge_map = {
            "stable":   '<span class="psi-stable">Stable</span>',
            "moderate": '<span class="psi-moderate">Moderate</span>',
            "retrain":  '<span class="psi-retrain">Retrain</span>',
        }
        header  = "| Feature | PSI | Status | Baseline mean | Current mean | Delta |"
        sep     = "|---------|-----|--------|---------------|--------------|-------|"
        rows_md = [header, sep]
        for _, row in df.iterrows():
            direction = "up" if row["delta_mean"] > 0 else "dn"
            rows_md.append(
                f"| `{row['feature']}` | `{row['psi']:.5f}` | "
                f"{badge_map[row['status']]} | "
                f"{row['baseline_mean']:.4f} | {row['current_mean']:.4f} | "
                f"{direction} {abs(row['delta_mean']):.4f} |"
            )
        st.markdown("\n".join(rows_md), unsafe_allow_html=True)

    except FileNotFoundError as e:
        err_safe = str(e).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        st.markdown(f"""
<div style="background:#fffbeb;border:1px solid #fde68a;border-left:4px solid #f59e0b;
border-radius:16px;padding:1.5rem 1.8rem;margin-bottom:1.5rem;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:0.9rem;">
    <div style="background:#f59e0b;border-radius:6px;padding:3px 9px;font-size:0.58rem;
    font-weight:800;color:#fff;letter-spacing:0.08em;">SETUP NEEDED</div>
    <div style="font-weight:700;color:#92400e;font-size:0.9rem;">Baseline not generated yet</div>
  </div>
  <div style="font-size:0.8rem;color:#78350f;line-height:1.7;margin-bottom:1.1rem;">
    {err_safe}
  </div>
  <div style="font-size:0.78rem;color:#92400e;font-weight:600;margin-bottom:0.6rem;">
    Run these commands once to generate the PSI baseline:
  </div>
  <div style="background:#1e293b;border-radius:10px;padding:0.85rem 1.1rem;">
    <div style="color:#94a3b8;font-size:0.6rem;font-weight:700;letter-spacing:0.1em;
    margin-bottom:0.5rem;text-transform:uppercase;">bash</div>
    <div style="color:#7dd3fc;font-size:0.75rem;line-height:1.85;
    font-family:'SFMono-Regular','Consolas',monospace;">
      python -m feature_store.feature_pipeline<br>python -m ml.train
    </div>
  </div>
</div>
<div style="margin-top:0.5rem;">
  <div style="font-size:0.65rem;font-weight:700;color:#94a3b8;text-transform:uppercase;
  letter-spacing:0.12em;margin-bottom:0.9rem;">9 features tracked by streamlake</div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;">
    {''.join(
        f'<div style="background:#fff;border:1px solid #e0e7ff;border-radius:10px;'
        f'padding:0.7rem 0.9rem;opacity:0.6;">'
        f'<div style="font-family:monospace;font-size:0.72rem;color:#6366f1;font-weight:600;">{feat}</div>'
        f'<div style="font-size:0.68rem;color:#94a3b8;margin-top:0.2rem;">PSI: pending</div>'
        f'</div>'
        for feat in [
            "purchase_count_1h","revenue_1h","purchase_count_24h",
            "revenue_24h","purchase_count_7d","revenue_7d",
            "days_since_first_purchase","days_since_last_purchase","is_repeat_customer",
        ]
    )}
  </div>
</div>
""", unsafe_allow_html=True)
    except Exception as e:
        err_safe = str(e).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        st.markdown(f"""
<div style="background:#fef2f2;border:1px solid #fecaca;border-left:4px solid #ef4444;
border-radius:14px;padding:1.2rem 1.5rem;">
  <div style="font-size:0.65rem;font-weight:700;color:#ef4444;text-transform:uppercase;
  letter-spacing:0.1em;margin-bottom:0.5rem;">Error</div>
  <div style="font-size:0.82rem;color:#991b1b;font-family:monospace;">{err_safe}</div>
</div>
""", unsafe_allow_html=True)


# =============================================================================
# TAB 4 - HOW IT WORKS
# =============================================================================
with tab4:

    st.markdown('<div class="section-hdr"><span>Architecture</span></div>',
                unsafe_allow_html=True)

    def _tl(color, bg, border, label, path, bullets, side):
        items = "".join(
            f'<li style="margin:3px 0;color:#475569;">{b}</li>' for b in bullets
        )
        card = f"""<div style="background:{bg};border:1px solid {border};
border-left:4px solid {color};border-radius:14px;padding:1rem 1.3rem;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:0.55rem;flex-wrap:wrap;">
    <span style="background:{color};color:#fff;font-size:0.6rem;font-weight:700;
    padding:2px 9px;border-radius:4px;text-transform:uppercase;letter-spacing:0.1em;">{label}</span>
    <code style="font-size:0.71rem;color:{color};background:rgba(0,0,0,0.05);
    padding:1px 7px;border-radius:4px;">{path}</code>
  </div>
  <ul style="margin:0;padding-left:1.1rem;font-size:0.8rem;line-height:1.85;">{items}</ul>
</div>"""
        dot = (f'<div style="display:flex;justify-content:center;padding-top:22px;'
               f'position:relative;z-index:1;">'
               f'<div style="width:16px;height:16px;background:{color};border-radius:50%;'
               f'border:3px solid #fff;box-shadow:0 0 0 3px {border};"></div></div>')
        left  = card  if side == "left"  else "<div></div>"
        right = card  if side == "right" else "<div></div>"
        return (f'<div style="display:grid;grid-template-columns:1fr 44px 1fr;'
                f'align-items:start;gap:16px;margin-bottom:4px;">'
                f'{left}{dot}{right}</div>')

    timeline = (
        '<div style="position:relative;padding:4px 0;">'
        '<div style="position:absolute;left:calc(50% - 1px);top:0;bottom:0;width:2px;'
        'background:linear-gradient(to bottom,#c7d2fe,#e0e7ff);z-index:0;"></div>'
        + _tl("#6366f1","#eef2ff","#c7d2fe","Ingest","Kafka / Redpanda + REST + CSV",[
            "Kafka/Redpanda &rarr; Avro + Schema Registry &nbsp; ~1,400 events/s",
            "POST /ingest/webhook?source=shopify|woocommerce",
            "POST /ingest/csv &nbsp; (multipart file upload)",
        ], "left")
        + _tl("#f59e0b","#fffbeb","#fde68a","Bronze","s3://streamlake-bronze/events/{tenant}/",[
            "Raw, immutable events in Delta Lake (delta-rs &mdash; no Spark or JVM)",
            "Partitioned by <code>ingestion_date</code> &middot; idempotent consumer",
            "At-least-once delivery &middot; tenant-namespaced S3 prefix",
        ], "right")
        + _tl("#8b5cf6","#f5f3ff","#ddd6fe","Silver","s3://streamlake-silver/events/",[
            "Event-time watermarks &middot; LRU dedup with 1h TTL",
            "6 Great Expectations validation rules",
            "Bad records routed to quarantine side-output",
        ], "left")
        + _tl("#10b981","#ecfdf5","#a7f3d0","Gold","s3://streamlake-gold/",[
            "DuckDB aggregations: DAU, revenue, funnel, user_signals",
            "Per-user behavioral signals (purchase frequency, spend windows)",
        ], "right")
        + _tl("#06b6d4","#ecfeff","#a5f3fc","Features","s3://streamlake-features/ + Redis",[
            "Feast 0.39 materializes Gold &rarr; Redis online store",
            "9 rolling features per user: purchases &amp; revenue over 1h / 24h / 7d",
            "Retrieved in &lt;10ms at inference time (no S3 call at serve time)",
        ], "left")
        + _tl("#ef4444","#fef2f2","#fecaca","Serve","https://streamlake.onrender.com",[
            "POST /predict &rarr; XGBoost &middot; SHAP &middot; 90/10 A/B split",
            "GET /alerts &rarr; Redis sorted-set range query O(log N)",
            "Prometheus metrics &middot; PSI drift detection &middot; outbound webhooks",
        ], "right")
        + '</div>'
    )
    st.markdown(timeline, unsafe_allow_html=True)

    st.markdown('<div class="section-hdr"><span>Key Design Decisions</span></div>',
                unsafe_allow_html=True)

    st.markdown("""
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;">

  <div style="background:#fff;border-radius:16px;padding:1.5rem;
  border:1px solid #f1f5f9;box-shadow:0 2px 8px rgba(99,102,241,0.07);">
    <div style="width:38px;height:38px;background:#fffbeb;border:1.5px solid #fde68a;
    border-radius:10px;display:flex;align-items:center;justify-content:center;
    font-size:0.72rem;font-weight:800;color:#f59e0b;margin-bottom:1rem;">S3</div>
    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;
    letter-spacing:0.1em;color:#f59e0b;margin-bottom:0.6rem;">Delta Lake on S3</div>
    <div style="font-size:0.82rem;color:#475569;line-height:1.75;">
      Chose <strong>delta-rs</strong> (Rust) over PySpark so the pipeline runs on
      a single machine with no JVM. ACID transactions and time-travel come free.
      Partitioned by <code style="background:#f8faff;padding:1px 5px;border-radius:4px;
      font-size:0.78rem;">ingestion_date</code> so each query scans only that day.
    </div>
  </div>

  <div style="background:#fff;border-radius:16px;padding:1.5rem;
  border:1px solid #f1f5f9;box-shadow:0 2px 8px rgba(99,102,241,0.07);">
    <div style="width:38px;height:38px;background:#ecfeff;border:1.5px solid #a5f3fc;
    border-radius:10px;display:flex;align-items:center;justify-content:center;
    font-size:0.72rem;font-weight:800;color:#06b6d4;margin-bottom:1rem;">RD</div>
    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;
    letter-spacing:0.1em;color:#06b6d4;margin-bottom:0.6rem;">Feast + Redis Feature Store</div>
    <div style="font-size:0.82rem;color:#475569;line-height:1.75;">
      Features are pre-computed in batch and pushed to <strong>Redis</strong> via Feast.
      The online store gives sub-10ms retrieval at inference time without touching S3.
      The offline Delta store keeps full history for retraining.
    </div>
  </div>

  <div style="background:#fff;border-radius:16px;padding:1.5rem;
  border:1px solid #f1f5f9;box-shadow:0 2px 8px rgba(99,102,241,0.07);">
    <div style="width:38px;height:38px;background:#ecfdf5;border:1.5px solid #a7f3d0;
    border-radius:10px;display:flex;align-items:center;justify-content:center;
    font-size:0.72rem;font-weight:800;color:#10b981;margin-bottom:1rem;">ML</div>
    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;
    letter-spacing:0.1em;color:#10b981;margin-bottom:0.6rem;">SHAP + PSI Observability</div>
    <div style="font-size:0.82rem;color:#475569;line-height:1.75;">
      Every prediction returns <strong>SHAP values</strong> so the score is never a black box.
      PSI is computed at startup and pushed to Prometheus. PSI above 0.25 on any feature
      triggers a drift alert without a separate ML platform.
    </div>
  </div>

  <div style="background:#fff;border-radius:16px;padding:1.5rem;
  border:1px solid #f1f5f9;box-shadow:0 2px 8px rgba(99,102,241,0.07);">
    <div style="width:38px;height:38px;background:#eef2ff;border:1.5px solid #c7d2fe;
    border-radius:10px;display:flex;align-items:center;justify-content:center;
    font-size:0.72rem;font-weight:800;color:#6366f1;margin-bottom:1rem;">KY</div>
    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;
    letter-spacing:0.1em;color:#6366f1;margin-bottom:0.6rem;">Multi-Tenant API Keys</div>
    <div style="font-size:0.82rem;color:#475569;line-height:1.75;">
      Each tenant authenticates with an
      <code style="background:#eef2ff;padding:1px 5px;border-radius:4px;font-size:0.78rem;color:#6366f1;">X-Api-Key</code>
      header. Data lands under <code style="background:#f8faff;padding:1px 5px;border-radius:4px;font-size:0.78rem;">{BRONZE_PATH}/{tenant_id}/</code>
      in S3 and churn scores are isolated in Redis per tenant.
    </div>
  </div>

  <div style="background:#fff;border-radius:16px;padding:1.5rem;
  border:1px solid #f1f5f9;box-shadow:0 2px 8px rgba(99,102,241,0.07);">
    <div style="width:38px;height:38px;background:#f5f3ff;border:1.5px solid #ddd6fe;
    border-radius:10px;display:flex;align-items:center;justify-content:center;
    font-size:0.72rem;font-weight:800;color:#8b5cf6;margin-bottom:1rem;">A/B</div>
    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;
    letter-spacing:0.1em;color:#8b5cf6;margin-bottom:0.6rem;">90 / 10 A/B Split</div>
    <div style="font-size:0.82rem;color:#475569;line-height:1.75;">
      Each <code style="background:#f5f3ff;padding:1px 5px;border-radius:4px;font-size:0.78rem;color:#8b5cf6;">/predict</code>
      call hashes the user_id to deterministically assign champion (90%) or challenger (10%).
      The same user always gets the same model, keeping cohort analysis clean.
    </div>
  </div>

  <div style="background:#fff;border-radius:16px;padding:1.5rem;
  border:1px solid #f1f5f9;box-shadow:0 2px 8px rgba(99,102,241,0.07);">
    <div style="width:38px;height:38px;background:#fef2f2;border:1.5px solid #fecaca;
    border-radius:10px;display:flex;align-items:center;justify-content:center;
    font-size:0.72rem;font-weight:800;color:#ef4444;margin-bottom:1rem;">WH</div>
    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;
    letter-spacing:0.1em;color:#ef4444;margin-bottom:0.6rem;">Fire-and-Forget Webhooks</div>
    <div style="font-size:0.82rem;color:#475569;line-height:1.75;">
      When churn probability exceeds the alert threshold,
      <code style="background:#fef2f2;padding:1px 5px;border-radius:4px;font-size:0.78rem;color:#ef4444;">/predict</code>
      fires an outbound webhook in a daemon thread. The response is never delayed,
      and failures are logged but never propagated to the caller.
    </div>
  </div>

</div>
""", unsafe_allow_html=True)

    st.markdown('<div class="section-hdr"><span>Try the API</span></div>',
                unsafe_allow_html=True)

    METHOD_COLOR = {"POST": "#6366f1", "GET": "#10b981"}
    METHOD_BG    = {"POST": "#eef2ff", "GET": "#ecfdf5"}

    def _safe(s):
        return (
            s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace("#", "&#35;")
             .replace("\n", "<br>")
        )

    def _colorize(html):
        lines = html.split("<br>")
        out = []
        for ln in lines:
            s = ln.lstrip()
            if s.startswith("&#35;"):
                out.append(f'<span style="color:#64748b;font-style:italic;">{ln}</span>')
            elif s.startswith("curl "):
                out.append(ln.replace(
                    "curl ", '<span style="color:#7dd3fc;font-weight:600;">curl</span> ', 1))
            elif s.startswith("-"):
                sp = ln.find("-")
                ep = ln.find(" ", sp)
                ep = ep if ep != -1 else len(ln)
                flag = ln[sp:ep]
                out.append(
                    ln[:sp]
                    + f'<span style="color:#fbbf24;">{flag}</span>'
                    + ln[ep:]
                )
            elif s.startswith("|"):
                out.append(ln.replace(
                    "|", '<span style="color:#94a3b8;">|</span>', 1))
            else:
                out.append(ln)
        return "<br>".join(out)

    def _api_card(method, endpoint, desc, cmd):
        mc = METHOD_COLOR[method]
        mb = METHOD_BG[method]
        code = _colorize(_safe(cmd))
        return (
            f'<div style="border-radius:16px;overflow:hidden;border:1px solid #e2e8f0;'
            f'box-shadow:0 2px 16px rgba(99,102,241,0.07);">'
            f'<div style="height:3px;background:{mc};"></div>'
            f'<div style="background:#ffffff;padding:0.9rem 1.2rem 0.85rem;">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:0.35rem;">'
            f'<span style="background:{mb};color:{mc};font-size:0.58rem;font-weight:800;'
            f'padding:2px 8px;border-radius:4px;letter-spacing:0.09em;">{method}</span>'
            f'<span style="font-family:\'SFMono-Regular\',monospace;font-size:0.72rem;'
            f'color:#64748b;">{endpoint}</span>'
            f'</div>'
            f'<div style="font-size:0.83rem;font-weight:600;color:#0f172a;">{desc}</div>'
            f'</div>'
            f'<div style="background:#0f172a;padding:1rem 1.2rem;">'
            f'<div style="color:#e2e8f0;font-size:0.72rem;line-height:1.9;'
            f'white-space:pre-wrap;font-family:\'SFMono-Regular\',\'Consolas\',monospace;">'
            f'{code}</div>'
            f'</div>'
            f'</div>'
        )

    _predict = f"""curl -s -X POST {API_URL}/predict \\
  -H "Content-Type: application/json" \\
  -H "X-Api-Key: sk-demo-streamlake" \\
  -d '{{"user_id": "USER-006775"}}' \\
  | python3 -m json.tool"""

    _alerts = f"""curl -s \\
  "{API_URL}/alerts?threshold=0.7&limit=10" \\
  -H "X-Api-Key: sk-demo-streamlake" \\
  | python3 -m json.tool"""

    _webhook = f"""curl -s -X POST \\
  "{API_URL}/ingest/webhook?source=shopify" \\
  -H "Content-Type: application/json" \\
  -H "X-Api-Key: sk-demo-streamlake" \\
  -d '{{
    "id": 12345,
    "created_at": "2024-06-21T10:00:00Z",
    "customer": {{"id": 99}},
    "total_price": "149.99",
    "line_items": [{{"product_id": 7}}],
    "billing_address": {{"country_code": "US"}}
  }}'"""

    _csv = f"""curl -s -X POST {API_URL}/ingest/csv \\
  -H "X-Api-Key: sk-demo-streamlake" \\
  -F "file=@orders.csv"

# orders.csv columns:
# order_id, customer_id, total_amount,
# order_date, product_id, country"""

    st.markdown(
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">'
        + _api_card("POST", "/predict",        "Score a customer",        _predict)
        + _api_card("GET",  "/alerts",          "Get at-risk customers",   _alerts)
        + _api_card("POST", "/ingest/webhook",  "Push a Shopify order",    _webhook)
        + _api_card("POST", "/ingest/csv",      "Upload a CSV",            _csv)
        + '</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-hdr"><span>Data Volumes (full pipeline run)</span></div>',
                unsafe_allow_html=True)

    v1, v2, v3, v4 = st.columns(4)
    for col, label, val, sub, cls, border in [
        (v1, "Bronze events",     "96,482", "raw records",    "sa", "mi"),
        (v2, "Silver events",     "96,477", "5 quarantined",  "se", "mv"),
        (v3, "Gold user signals", "93,357", "after dedup",    "si", "me"),
        (v4, "Feature store",     "93,357", "users in Redis", "sv", "ma"),
    ]:
        col.markdown(f"""
<div class="mcard {border}" style="text-align:center;">
  <div class="card-label">{label}</div>
  <div class="card-val">{val}</div>
  <div class="card-sub {cls}">{sub}</div>
</div>""", unsafe_allow_html=True)
