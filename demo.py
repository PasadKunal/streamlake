"""
StreamLake Demo Dashboard
Single-page Streamlit app for demoing the full project.

Start with:
    ./start.sh          (starts everything)
    streamlit run demo.py --server.port 8501
"""
import os
import random
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ── Config ────────────────────────────────────────────────
API_URL = os.getenv("API_URL", "http://localhost:8000")

STORAGE_OPTIONS = {
    "AWS_ENDPOINT_URL":          "http://localhost:9002",
    "AWS_ACCESS_KEY_ID":         "minioadmin",
    "AWS_SECRET_ACCESS_KEY":     "minioadmin",
    "AWS_REGION":                "us-east-1",
    "AWS_ALLOW_HTTP":            "true",
    "AWS_S3_ALLOW_UNSAFE_RENAME":"true",
}

st.set_page_config(
    page_title="StreamLake",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Header ────────────────────────────────────────────────
st.markdown("# 🌊 StreamLake")
st.markdown(
    "Real-Time Data Lakehouse · ML Feature Store · Churn Prediction API  \n"
    "**Stack:** Kafka · Delta Lake · Feast · XGBoost · MLflow · FastAPI · Prometheus"
)
st.divider()

tab1, tab2, tab3 = st.tabs([
    "📊  Pipeline Overview",
    "🔮  Churn Prediction",
    "📡  Drift Monitor",
])


# ─────────────────────────────────────────────────────────
# TAB 1 — Pipeline Overview
# ─────────────────────────────────────────────────────────
with tab1:

    # Top metrics row
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        try:
            from deltalake import DeltaTable
            dt  = DeltaTable("s3://streamlake-bronze/events", storage_options=STORAGE_OPTIONS)
            cnt = len(dt.to_pandas())
            c1.metric("🥉 Bronze Events", f"{cnt:,}", f"Delta v{dt.version()}")
        except Exception:
            c1.metric("🥉 Bronze Events", "—", "run the producer")

    with c2:
        try:
            from deltalake import DeltaTable
            dt  = DeltaTable("s3://streamlake-silver/events", storage_options=STORAGE_OPTIONS)
            sdf = dt.to_pandas()
            c2.metric("🥈 Silver Events", f"{len(sdf):,}", f"Delta v{dt.version()}")
        except Exception:
            c2.metric("🥈 Silver Events", "—", "run bronze_to_silver")

    with c3:
        try:
            fdf = pd.read_parquet("feature_store/data/user_features.parquet")
            c3.metric("🗄️ Users in Feature Store", f"{len(fdf):,}", "Redis + Delta")
        except Exception:
            c3.metric("🗄️ Feature Store", "—", "run feature_pipeline")

    with c4:
        try:
            import mlflow
            mlflow.set_tracking_uri("mlruns")
            client   = mlflow.MlflowClient()
            versions = client.get_latest_versions("streamlake-churn-model")
            if versions:
                run = client.get_run(versions[-1].run_id)
                auc = run.data.metrics.get("auc", 0)
                c4.metric("🤖 Model AUC", f"{auc:.3f}", f"v{versions[-1].version} · XGBoost")
        except Exception:
            c4.metric("🤖 Model AUC", "—", "run ml.train")

    st.divider()

    # Two-column charts
    left, right = st.columns(2)

    with left:
        st.subheader("Event Type Distribution (Silver)")
        try:
            from deltalake import DeltaTable
            df = DeltaTable("s3://streamlake-silver/events", storage_options=STORAGE_OPTIONS).to_pandas()
            counts = df["event_type"].value_counts().reset_index()
            counts.columns = ["Event Type", "Count"]
            fig = px.bar(counts, x="Event Type", y="Count", color="Event Type",
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_layout(showlegend=False, height=320, margin=dict(t=10))
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.info("No Silver data yet.")

    with right:
        st.subheader("Device & Country Split (Silver)")
        try:
            from deltalake import DeltaTable
            df = DeltaTable("s3://streamlake-silver/events", storage_options=STORAGE_OPTIONS).to_pandas()
            dev = df["device_type"].value_counts().reset_index()
            dev.columns = ["Device", "Count"]
            fig = px.pie(dev, names="Device", values="Count",
                         color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(height=320, margin=dict(t=10))
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.info("No Silver data yet.")

    st.divider()
    st.subheader("Architecture")
    st.code("""
  Kafka (Redpanda)
       │
       ▼
  Bronze Delta (MinIO)  ◄── raw, immutable events
       │
       ▼
  Silver Delta (MinIO)  ◄── deduped, validated, watermarked
       │
       ├──► Gold Delta  ◄── DAU / revenue / funnel aggregations
       │
       └──► Feature Store (Feast)
                 ├── Redis       ◄── online serving  (<10ms)
                 └── Delta Lake  ◄── offline training (point-in-time join)
                          │
                          ▼
                    XGBoost model  ──► FastAPI /predict
                    MLflow registry     (SHAP + A/B split)
""", language="text")


# ─────────────────────────────────────────────────────────
# TAB 2 — Churn Prediction
# ─────────────────────────────────────────────────────────
with tab2:
    st.subheader("Real-Time Churn Prediction")
    st.caption("Features fetched from Redis · Model loaded from MLflow · SHAP explanation included")

    col_input, col_btn = st.columns([3, 1])

    with col_input:
        user_id = st.text_input(
            "User ID",
            value="USER-006775",
            placeholder="e.g. USER-006775",
            label_visibility="collapsed",
        )

    with col_btn:
        if st.button("🎲 Random user"):
            try:
                fdf     = pd.read_parquet("feature_store/data/user_features.parquet")
                user_id = random.choice(fdf["user_id"].tolist())
                st.rerun()
            except Exception:
                st.warning("Feature store not ready.")

    predict_btn = st.button("🔮 Predict churn risk", type="primary", use_container_width=True)

    if predict_btn:
        try:
            resp = requests.post(
                f"{API_URL}/predict",
                json={"user_id": user_id},
                timeout=10,
            )

            if resp.status_code == 200:
                data = resp.json()
                prob = data["churn_probability"]

                st.divider()

                # Big metrics row
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Churn Probability", f"{prob:.1%}")
                m2.metric("Prediction",  "🔴 High Risk" if prob >= 0.5 else "🟢 Low Risk")
                m3.metric("Model",        f"v{data['model_version']}")
                m4.metric("A/B Group",    data["ab_group"].title())

                # Probability gauge
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=prob * 100,
                    number={"suffix": "%"},
                    gauge={
                        "axis":  {"range": [0, 100]},
                        "bar":   {"color": "#e74c3c" if prob >= 0.5 else "#2ecc71"},
                        "steps": [
                            {"range": [0,  30],  "color": "#2d4a2d"},
                            {"range": [30, 60],  "color": "#4a4a2d"},
                            {"range": [60, 100], "color": "#4a2d2d"},
                        ],
                        "threshold": {"line": {"color": "white", "width": 2}, "value": 50},
                    },
                    title={"text": "Churn Risk Score"},
                ))
                fig.update_layout(height=260, margin=dict(t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)

                # SHAP explanation
                st.subheader("Why this score? (SHAP)")
                shap_rows = data["top_features"]
                shap_df   = pd.DataFrame(shap_rows)
                colors = [
                    "#e74c3c" if r["direction"] == "increases_churn" else "#2ecc71"
                    for _, r in shap_df.iterrows()
                ]
                fig2 = go.Figure(go.Bar(
                    x=shap_df["shap_value"],
                    y=shap_df["feature"],
                    orientation="h",
                    marker_color=colors,
                    text=[f"{v:+.3f}" for v in shap_df["shap_value"]],
                    textposition="outside",
                ))
                fig2.update_layout(
                    height=220,
                    margin=dict(t=10, b=10),
                    xaxis_title="SHAP value (positive = more churn)",
                    yaxis={"autorange": "reversed"},
                )
                st.plotly_chart(fig2, use_container_width=True)

                # Features used
                with st.expander("📋 Feature values from Redis"):
                    feat_df = pd.DataFrame([data["features_used"]]).T.reset_index()
                    feat_df.columns = ["Feature", "Value"]
                    st.dataframe(feat_df, use_container_width=True, hide_index=True)

            elif resp.status_code == 404:
                st.warning(f"User `{user_id}` not found in feature store. Try a different ID.")
            else:
                st.error(f"API error {resp.status_code}: {resp.json().get('detail', 'unknown')}")

        except requests.exceptions.ConnectionError:
            st.error(
                "**API not running.**  \n"
                "Start it in a terminal:  \n"
                "```\nuvicorn serving.app:app --port 8000\n```"
            )
        except Exception as e:
            st.error(f"Unexpected error: {e}")


# ─────────────────────────────────────────────────────────
# TAB 3 — Drift Monitor
# ─────────────────────────────────────────────────────────
with tab3:
    st.subheader("Feature Drift Monitor — Population Stability Index (PSI)")
    st.caption("Compares current feature distributions against the training baseline saved during model training.")

    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.markdown("""
| PSI | Status | Action |
|-----|--------|--------|
| < 0.10 | 🟢 Stable | None |
| 0.10–0.25 | 🟡 Moderate | Monitor |
| > 0.25 | 🔴 Significant | **Retrain** |
        """)

    try:
        from serving.drift_monitor import compute_drift_report
        report = compute_drift_report()

        with col_b:
            if report["drift_alert"]:
                st.error("🔴 DRIFT ALERT — Retraining recommended")
            else:
                st.success("🟢 All features stable — no retraining needed")
            st.caption(
                f"Baseline: {report['baseline_computed_at'][:19]}  ·  "
                f"n={report['baseline_n_samples']:,} training samples  ·  "
                f"n={report['current_n_samples']:,} current samples"
            )

        st.divider()

        rows = []
        for feat, info in report["features"].items():
            rows.append({
                "Feature":        feat,
                "PSI":            info["psi"],
                "Status":         info["status"],
                "Baseline Mean":  info["baseline_mean"],
                "Current Mean":   info["current_mean"],
                "Δ Mean":         round(info["current_mean"] - info["baseline_mean"], 4),
            })
        df = pd.DataFrame(rows).sort_values("PSI", ascending=False)

        # PSI bar chart
        icon_map   = {"stable": "🟢", "moderate": "🟡", "retrain": "🔴"}
        color_map  = {"stable": "#2ecc71", "moderate": "#f1c40f", "retrain": "#e74c3c"}
        df["icon"] = df["Status"].map(icon_map)
        fig = px.bar(
            df, x="PSI", y="Feature", orientation="h",
            color="Status",
            color_discrete_map=color_map,
            text="PSI",
        )
        fig.update_traces(texttemplate="%{text:.5f}", textposition="outside")
        fig.add_vline(x=0.10, line_dash="dash", line_color="yellow",  annotation_text="monitor (0.10)")
        fig.add_vline(x=0.25, line_dash="dash", line_color="red",    annotation_text="retrain (0.25)")
        fig.update_layout(height=380, margin=dict(t=10), yaxis={"autorange": "reversed"})
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            df[["Feature", "PSI", "Status", "Baseline Mean", "Current Mean", "Δ Mean"]],
            use_container_width=True,
            hide_index=True,
        )

    except FileNotFoundError as e:
        st.warning(str(e))
    except Exception as e:
        st.error(f"Error computing drift: {e}")
