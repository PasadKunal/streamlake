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
    layout="wide",
    initial_sidebar_state="expanded",
)

def _secret(key: str, default: str = "") -> str:
    """Read from Streamlit Cloud secrets first, then env vars, then default."""
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

API_URL = _secret("API_URL", "http://localhost:8000")

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
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#a0aec0", size=12),
    margin=dict(t=20, b=20, l=10, r=10),
)
PURPLE = "#8b5cf6"
TEAL   = "#00d4aa"
RED    = "#ef4444"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

.stApp { background: #080c18; font-family: 'Inter', sans-serif; }
#MainMenu, footer { visibility: hidden; }
.block-container { padding: 1.5rem 2rem 2rem; max-width: 1400px; }

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #8b5cf6; border-radius: 3px; }

.hero {
    background: linear-gradient(135deg, #0d0d1f 0%, #1a1035 50%, #0d1a35 100%);
    border: 1px solid rgba(139,92,246,0.25);
    border-radius: 16px;
    padding: 1.8rem 2rem;
    margin-bottom: 1.5rem;
}
.hero-title {
    font-size: 2rem; font-weight: 800; color: #fff;
    margin: 0 0 0.5rem; line-height: 1.2;
}
.hero-title span {
    background: linear-gradient(90deg, #8b5cf6, #06b6d4);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero-sub { font-size: 0.85rem; color: #64748b; line-height: 1.6; }
.hero-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 0.9rem; }
.tag {
    background: rgba(139,92,246,0.08); border: 1px solid rgba(139,92,246,0.2);
    color: #a78bfa; border-radius: 20px; padding: 3px 10px;
    font-size: 0.7rem; font-weight: 500;
}

.card {
    background: linear-gradient(160deg, #10162a 0%, #141d30 100%);
    border: 1px solid rgba(139,92,246,0.12);
    border-radius: 14px;
    padding: 1.3rem 1.4rem;
    transition: all 0.25s ease;
    height: 100%;
}
.card:hover {
    border-color: rgba(139,92,246,0.4);
    transform: translateY(-3px);
    box-shadow: 0 12px 30px rgba(139,92,246,0.08);
}
.card-val   { font-size: 1.8rem; font-weight: 800; color: #f1f5f9; line-height: 1; }
.card-label { font-size: 0.7rem; color: #475569; text-transform: uppercase;
              letter-spacing: 0.1em; margin-top: 0.3rem; }
.card-sub   { font-size: 0.78rem; margin-top: 0.4rem; font-weight: 500; }
.sub-green  { color: #00d4aa; }
.sub-purple { color: #8b5cf6; }
.sub-blue   { color: #38bdf8; }
.sub-orange { color: #fb923c; }
.sub-muted  { color: #ef4444; }

.section-hdr { display: flex; align-items: center; gap: 10px; margin: 1.5rem 0 1rem; }
.section-hdr span { font-size: 0.85rem; font-weight: 600; color: #e2e8f0; white-space: nowrap; }
.section-hdr::after { content: ''; flex: 1; height: 1px; background: rgba(139,92,246,0.12); }

.dot-green { width:8px; height:8px; border-radius:50%; background:#00d4aa;
             display:inline-block; box-shadow:0 0 6px #00d4aa; }
.dot-red   { width:8px; height:8px; border-radius:50%; background:#ef4444;
             display:inline-block; box-shadow:0 0 6px #ef4444; }
.svc-row   { display:flex; align-items:center; gap:8px; font-size:0.8rem;
             color:#94a3b8; padding:4px 0; }
.svc-name  { flex:1; }

.phase-row { display:flex; align-items:center; gap:8px; font-size:0.78rem;
             color:#64748b; padding:3px 0; }
.phase-num { font-weight:700; color:#8b5cf6; min-width:20px; }
.phase-check { color:#00d4aa; }

.pred-card {
    background: linear-gradient(160deg, #10162a 0%, #141d30 100%);
    border: 1px solid rgba(139,92,246,0.2);
    border-radius: 16px;
    padding: 1.8rem;
    text-align: center;
}
.prob-num  { font-size: 3.5rem; font-weight: 900; line-height: 1; margin-bottom: 0.2rem; }
.prob-high { color: #ef4444; text-shadow: 0 0 30px rgba(239,68,68,0.3); }
.prob-low  { color: #00d4aa; text-shadow: 0 0 30px rgba(0,212,170,0.3); }
.prob-lbl  { font-size: 0.7rem; color: #475569; text-transform: uppercase; letter-spacing: 0.12em; }
.pred-badge { display:inline-block; border-radius:8px; padding:5px 16px;
              font-size:0.82rem; font-weight:700; margin-top:0.8rem; }
.pred-high { background:rgba(239,68,68,0.1); color:#ef4444; border:1px solid rgba(239,68,68,0.3); }
.pred-low  { background:rgba(0,212,170,0.1); color:#00d4aa; border:1px solid rgba(0,212,170,0.3); }

.psi-stable   { background:rgba(0,212,170,0.08);  color:#00d4aa; border:1px solid rgba(0,212,170,0.25);
                border-radius:6px; padding:2px 10px; font-size:0.7rem; font-weight:600; }
.psi-moderate { background:rgba(251,191,36,0.08); color:#fbbf24; border:1px solid rgba(251,191,36,0.25);
                border-radius:6px; padding:2px 10px; font-size:0.7rem; font-weight:600; }
.psi-retrain  { background:rgba(239,68,68,0.08);  color:#ef4444; border:1px solid rgba(239,68,68,0.25);
                border-radius:6px; padding:2px 10px; font-size:0.7rem; font-weight:600; }

.stTabs [data-baseweb="tab-list"] {
    background:transparent; gap:6px;
    border-bottom: 1px solid rgba(139,92,246,0.12); padding-bottom:0;
}
.stTabs [data-baseweb="tab"] {
    background:rgba(139,92,246,0.04);
    border:1px solid rgba(139,92,246,0.1); border-bottom:none;
    border-radius:10px 10px 0 0;
    color:#64748b; padding:0.5rem 1.3rem;
    font-size:0.85rem; font-weight:500;
}
.stTabs [aria-selected="true"] {
    background:rgba(139,92,246,0.14) !important;
    color:#a78bfa !important;
    border-color:rgba(139,92,246,0.35) !important;
}

.stTextInput input {
    background:#0d1117; border:1px solid rgba(139,92,246,0.25);
    border-radius:10px; color:#f1f5f9; font-size:0.9rem; padding:0.6rem 1rem;
}
.stTextInput input:focus {
    border-color:#8b5cf6; box-shadow:0 0 0 3px rgba(139,92,246,0.12); outline:none;
}

.stButton > button {
    border-radius:10px; font-weight:500; font-size:0.85rem;
    border:1px solid rgba(139,92,246,0.25); color:#a78bfa;
    background:rgba(139,92,246,0.06); transition:all 0.2s;
}
.stButton > button:hover {
    border-color:rgba(139,92,246,0.5); background:rgba(139,92,246,0.12);
}
.stButton > button[kind="primary"] {
    background:linear-gradient(135deg,#7c3aed,#5b21b6);
    color:#fff; border:none; box-shadow:0 4px 15px rgba(124,58,237,0.3);
}
.stButton > button[kind="primary"]:hover {
    background:linear-gradient(135deg,#8b5cf6,#6d28d9); transform:translateY(-1px);
}

[data-testid="stSidebar"] {
    background: #080c18 !important;
    border-right: 1px solid rgba(139,92,246,0.1);
}
[data-testid="stSidebar"] .block-container { padding: 1.5rem 1rem; }

.divider { height:1px; background:rgba(139,92,246,0.1); margin:1.2rem 0; }

.sidebar-label {
    font-size:0.65rem; font-weight:700; color:#334155;
    text-transform:uppercase; letter-spacing:0.12em; margin-bottom:0.5rem;
}
</style>
""", unsafe_allow_html=True)


# -- helpers ------------------------------------------------------------------

@st.cache_data(ttl=30)
def load_delta(path: str) -> pd.DataFrame:
    from deltalake import DeltaTable
    return DeltaTable(path, storage_options=STORAGE_OPTIONS).to_pandas()

@st.cache_data(ttl=30)
def load_features() -> pd.DataFrame:
    return pd.read_parquet("feature_store/data/user_features.parquet")

def check_svc(url: str, timeout: float = 5.0) -> bool:
    try:
        requests.get(url, timeout=timeout)
        return True
    except Exception:
        return False

def dot(ok: bool) -> str:
    cls = "dot-green" if ok else "dot-red"
    return f'<span class="{cls}"></span>'


# -- sidebar ------------------------------------------------------------------

with st.sidebar:
    st.markdown("""
<div style="padding:0.5rem 0 1.2rem;">
  <div style="font-size:1.2rem;font-weight:800;color:#f1f5f9;letter-spacing:-0.01em;">StreamLake</div>
  <div style="font-size:0.72rem;color:#475569;margin-top:3px;">Data Lakehouse / ML Feature Store</div>
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
            f'style="color:#8b5cf6;font-size:0.65rem;text-decoration:none;">open</a></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-label">Build Phases</div>', unsafe_allow_html=True)
    phases = [
        ("Ingestion",     "Kafka to Bronze Delta"),
        ("Processing",    "Bronze to Silver"),
        ("Aggregation",   "Silver to Gold"),
        ("Feature Store", "Feast + Redis + Delta"),
        ("ML",            "XGBoost + FastAPI"),
        ("Observability", "PSI + Prometheus"),
    ]
    for i, (name, desc) in enumerate(phases, 1):
        st.markdown(
            f'<div class="phase-row">'
            f'<span class="phase-num">0{i}</span>'
            f'<span class="phase-check">&#10003;</span>'
            f'<div>'
            f'<div style="color:#94a3b8;font-size:0.78rem;">{name}</div>'
            f'<div style="color:#334155;font-size:0.68rem;">{desc}</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-label">Stack</div>', unsafe_allow_html=True)
    techs = ["Kafka", "Delta Lake", "PyFlink", "Feast", "Redis",
             "XGBoost", "MLflow", "FastAPI", "SHAP", "Prometheus", "DuckDB"]
    pills = "".join(
        f'<span style="display:inline-block;background:rgba(139,92,246,0.08);'
        f'border:1px solid rgba(139,92,246,0.2);color:#8b5cf6;border-radius:20px;'
        f'padding:2px 9px;font-size:0.67rem;margin:2px;">{t}</span>'
        for t in techs
    )
    st.markdown(pills, unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    st.markdown("""
<div style="font-size:0.65rem;font-weight:700;color:#334155;
text-transform:uppercase;letter-spacing:0.12em;margin-bottom:0.5rem;">Author</div>
<div style="font-size:0.88rem;font-weight:700;color:#e2e8f0;">Kunal Pasad</div>
<div style="font-size:0.72rem;color:#475569;margin-top:2px;">SPIT Mumbai</div>
<div style="margin-top:0.6rem;">
  <a href="https://github.com/PasadKunal/streamlake" target="_blank"
     style="font-size:0.72rem;color:#8b5cf6;text-decoration:none;">
    github.com/PasadKunal/streamlake
  </a>
</div>
""", unsafe_allow_html=True)


# -- hero ---------------------------------------------------------------------

st.markdown("""
<div class="hero">
  <div class="hero-title"><span>StreamLake</span></div>
  <div class="hero-sub">
    A real-time data lakehouse I built to learn stream processing, feature stores, and ML serving.
    Kafka to Delta Lake to Feast to XGBoost to FastAPI. 6 phases, 133 tests.
  </div>
  <div class="hero-tags">
    <span class="tag">Delta Lake (ACID)</span>
    <span class="tag">Event-Time Watermarks</span>
    <span class="tag">Redis Feature Store</span>
    <span class="tag">XGBoost + MLflow</span>
    <span class="tag">SHAP Explainability</span>
    <span class="tag">PSI Drift Detection</span>
    <span class="tag">A/B Testing</span>
  </div>
</div>
""", unsafe_allow_html=True)


# -- tabs ---------------------------------------------------------------------

tab1, tab2, tab3 = st.tabs(["Pipeline", "Predict", "Drift Monitor"])


# =============================================================================
# TAB 1 - PIPELINE
# =============================================================================
with tab1:

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        try:
            bronze = load_delta("s3://streamlake-bronze/events")
            c1.markdown(f"""<div class="card">
                <div class="card-label">Bronze Events</div>
                <div class="card-val">{len(bronze):,}</div>
                <div class="card-sub sub-orange">raw, immutable</div>
            </div>""", unsafe_allow_html=True)
        except Exception:
            c1.markdown('<div class="card"><div class="card-label">Bronze Events</div>'
                        '<div class="card-val">--</div>'
                        '<div class="card-sub sub-muted">run the producer</div></div>',
                        unsafe_allow_html=True)

    with c2:
        try:
            silver = load_delta("s3://streamlake-silver/events")
            late   = (silver["watermark_classification"] == "late").sum()
            c2.markdown(f"""<div class="card">
                <div class="card-label">Silver Events</div>
                <div class="card-val">{len(silver):,}</div>
                <div class="card-sub sub-green">{late} late, 0 quarantined</div>
            </div>""", unsafe_allow_html=True)
        except Exception:
            c2.markdown('<div class="card"><div class="card-label">Silver Events</div>'
                        '<div class="card-val">--</div>'
                        '<div class="card-sub sub-muted">run bronze_to_silver</div></div>',
                        unsafe_allow_html=True)

    with c3:
        try:
            fdf        = load_features()
            purchasers = (fdf["purchase_count_24h"] > 0).sum()
            c3.markdown(f"""<div class="card">
                <div class="card-label">Feature Store Users</div>
                <div class="card-val">{len(fdf):,}</div>
                <div class="card-sub sub-blue">{purchasers} purchased today</div>
            </div>""", unsafe_allow_html=True)
        except Exception:
            c3.markdown('<div class="card"><div class="card-label">Feature Store</div>'
                        '<div class="card-val">--</div>'
                        '<div class="card-sub sub-muted">run feature_pipeline</div></div>',
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
                c4.markdown(f"""<div class="card">
                    <div class="card-label">Model AUC</div>
                    <div class="card-val">{auc:.3f}</div>
                    <div class="card-sub sub-purple">XGBoost v{versions[-1].version}</div>
                </div>""", unsafe_allow_html=True)
        except Exception:
            c4.markdown('<div class="card"><div class="card-label">Model AUC</div>'
                        '<div class="card-val">--</div>'
                        '<div class="card-sub sub-muted">run ml.train</div></div>',
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
                color_continuous_scale=["#312e81", "#8b5cf6", "#c4b5fd"],
            )
            fig.update_layout(**CHART_LAYOUT, coloraxis_showscale=False, height=290)
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.info("No Silver data yet.")

    with right:
        try:
            silver = load_delta("s3://streamlake-silver/events")
            dev    = silver["device_type"].value_counts().reset_index()
            dev.columns = ["Device", "Count"]
            fig = px.pie(
                dev, names="Device", values="Count",
                color_discrete_sequence=["#8b5cf6", "#06b6d4", "#00d4aa", "#fbbf24"],
                hole=0.55,
            )
            fig.update_layout(
                **CHART_LAYOUT, showlegend=True, height=290,
                legend=dict(orientation="v", x=1, y=0.5),
            )
            fig.update_traces(textinfo="percent", textfont_color="#fff")
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.info("No Silver data yet.")

    st.markdown('<div class="section-hdr"><span>Data Flow</span></div>',
                unsafe_allow_html=True)
    st.code("""
  Python Producer  -->  Redpanda (Kafka)  -->  Schema Registry (Avro)
  ~1,400 events/s        4 partitions          backward compatible

        |
        v
  +-----------+   BRONZE  -  raw, immutable, partitioned by date
  |  MinIO S3 |   Delta Lake, idempotent consumer, at-least-once delivery
  |  (Delta)  |
  +-----+-----+
        |
        v  watermark / dedup / Great Expectations / quarantine router
  +-----------+   SILVER  -  validated, deduplicated
  |  MinIO S3 |   event-time watermarks, LRU dedup (1h TTL),
  |  (Delta)  |   6 GE validation rules, quarantine side-output
  +-----+-----+
        |
        +---------------------------+
        v                           v
  +-----------+  GOLD           +-------------+  FEATURE STORE
  | DuckDB    |  DAU            | Feast 0.39  |  9 rolling features:
  |           |  Revenue        | Redis       |  purchase 1h/24h/7d
  |           |  Funnel         | Delta       |  revenue 1h/24h/7d
  +-----------+  Aggregations   +------+------+  session_count_24h
                                       |
                                       v
                               XGBoost churn model
                               MLflow tracking + registry
                                       |
                                       v
                               FastAPI /predict
                               SHAP explanations
                               90/10 A/B split
                               Prometheus + PSI drift
""", language="text")


# =============================================================================
# TAB 2 - PREDICT
# =============================================================================
with tab2:
    st.markdown("""
<div style="color:#64748b;font-size:0.85rem;margin-bottom:1.2rem;">
Features are fetched live from Redis.
Model is loaded from the MLflow registry.
SHAP shows which features drove the score.
</div>
""", unsafe_allow_html=True)

    col_in, col_btn, col_rnd = st.columns([4, 2, 2])
    with col_in:
        user_id = st.text_input("User ID", value="USER-006775",
                                placeholder="e.g. USER-006775",
                                label_visibility="collapsed")
    with col_btn:
        go_btn = st.button("Predict", type="primary", use_container_width=True)
    with col_rnd:
        if st.button("Random user", use_container_width=True):
            try:
                fdf = load_features()
                st.session_state["rand_user"] = random.choice(fdf["user_id"].tolist())
                st.rerun()
            except Exception:
                st.warning("Feature store not ready.")

    if "rand_user" in st.session_state:
        user_id = st.session_state.pop("rand_user")
        go_btn  = True

    if go_btn:
        with st.spinner("Fetching features and running model (first request may take ~30s to wake API)..."):
            try:
                resp = requests.post(
                    f"{API_URL}/predict", json={"user_id": user_id}, timeout=60
                )
            except requests.exceptions.ConnectionError:
                st.error(f"Cannot connect to API at {API_URL}. Check that RENDER is running.")
                st.stop()
            except requests.exceptions.Timeout:
                st.error("API timed out after 60s. The Render free tier may be overloaded — try again.")
                st.stop()
        if resp.status_code == 404:
            st.warning(f"User `{user_id}` not in feature store.")
        elif resp.status_code != 200:
            st.error(f"API returned {resp.status_code}: {resp.json().get('detail', 'unknown')}")
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
  <div style="margin-top:1.2rem;display:flex;gap:12px;justify-content:center;">
    <div style="text-align:center;">
      <div style="font-size:0.65rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;">Model</div>
      <div style="font-size:0.82rem;color:#a78bfa;font-weight:600;">v{data['model_version']}</div>
    </div>
    <div style="text-align:center;">
      <div style="font-size:0.65rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;">A/B Group</div>
      <div style="font-size:0.82rem;color:#06b6d4;font-weight:600;">{data['ab_group'].title()}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

            with r2:
                st.markdown("**SHAP feature contributions**")
                st.caption("Positive value = pushes toward churn. Negative = away from churn.")
                shap_df = pd.DataFrame(data["top_features"])
                colors  = [
                    "#ef4444" if d == "increases_churn" else "#00d4aa"
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
                    textfont=dict(color="#a0aec0", size=11),
                ))
                fig.update_layout(
                    **CHART_LAYOUT, height=200,
                    xaxis_title="SHAP value",
                    yaxis={"autorange": "reversed", "tickfont": {"size": 11}},
                    xaxis={"zeroline": True, "zerolinecolor": "rgba(139,92,246,0.3)"},
                )
                st.plotly_chart(fig, use_container_width=True)

            with r3:
                st.markdown("**Feature values (from Redis)**")
                st.caption("9 rolling-window features computed over the last 1h, 24h, and 7d.")
                feat = data["features_used"]
                rows = [
                    {
                        "Feature": k,
                        "Value": f"{int(v):,}" if isinstance(v, (int, float)) else v,
                    }
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
                    "font": {"size": 48, "color": "#ef4444" if prob >= 0.5 else "#00d4aa"},
                },
                delta={
                    "reference": 50, "suffix": "% vs threshold",
                    "font": {"size": 14},
                    "decreasing": {"color": "#00d4aa"},
                    "increasing": {"color": "#ef4444"},
                },
                gauge={
                    "axis":  {"range": [0, 100], "tickcolor": "#475569", "tickwidth": 1},
                    "bar":   {"color": "#ef4444" if prob >= 0.5 else "#00d4aa", "thickness": 0.25},
                    "bgcolor": "rgba(0,0,0,0)",
                    "bordercolor": "rgba(139,92,246,0.2)",
                    "steps": [
                        {"range": [0, 30],   "color": "rgba(0,212,170,0.08)"},
                        {"range": [30, 60],  "color": "rgba(251,191,36,0.06)"},
                        {"range": [60, 100], "color": "rgba(239,68,68,0.08)"},
                    ],
                    "threshold": {"line": {"color": "#8b5cf6", "width": 2}, "value": 50},
                },
                title={"text": f"Risk score for {user_id}",
                       "font": {"color": "#64748b", "size": 13}},
            ))
            fig_g.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", color="#a0aec0"),
                height=250, margin=dict(t=40, b=0, l=30, r=30),
            )
            st.plotly_chart(fig_g, use_container_width=True)


# =============================================================================
# TAB 3 - DRIFT MONITOR
# =============================================================================
with tab3:
    st.markdown("""
<div style="color:#64748b;font-size:0.85rem;margin-bottom:1.2rem;">
Population Stability Index (PSI) measures how much each feature's distribution has shifted
since training. PSI below 0.10 is stable. Above 0.25 means the model should be retrained.
</div>
""", unsafe_allow_html=True)

    try:
        from serving.drift_monitor import compute_drift_report
        report = compute_drift_report()

        if report["drift_alert"]:
            st.error("Drift alert: one or more features have shifted significantly. Retraining recommended.")
        else:
            st.success("All features stable. PSI within safe thresholds.")

        st.markdown(f"""
<div style="display:flex;gap:2rem;font-size:0.8rem;color:#64748b;margin:0.8rem 0 1.2rem;">
  <span>Baseline: <strong style="color:#a78bfa">{report['baseline_computed_at'][:10]}</strong></span>
  <span>Training samples: <strong style="color:#a78bfa">{report['baseline_n_samples']:,}</strong></span>
  <span>Current samples: <strong style="color:#a78bfa">{report['current_n_samples']:,}</strong></span>
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

        color_map = {"stable": TEAL, "moderate": "#fbbf24", "retrain": RED}

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
                textfont=dict(color="#a0aec0", size=11),
            ))
        fig.add_vline(
            x=0.10, line_dash="dot", line_color="#fbbf24",
            annotation_text="monitor (0.10)",
            annotation_font_color="#fbbf24", annotation_font_size=11,
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
            legend=dict(orientation="h", x=0.5, xanchor="center", y=1.08),
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
        st.warning(f"Training baseline not found: {e}\n\nRun `python -m ml.train` to generate it.")
    except Exception as e:
        st.error(f"Error: {e}")
