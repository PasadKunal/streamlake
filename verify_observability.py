"""
Verification script for Phase 6 — Observability.
Checks: PSI drift detection, Prometheus metrics, Grafana, Locust setup.

Usage:
    source .venv/bin/activate
    python verify_observability.py
"""
import warnings
warnings.filterwarnings("ignore")

import json, os, time
from pathlib import Path

print("=" * 55)
print("  StreamLake — Observability Verification (Phase 6)")
print("=" * 55)

# ── 1. PSI Drift Report ───────────────────────────────────
print("\n── PSI Drift Detection ───────────────────────────────")
try:
    from serving.drift_monitor import compute_drift_report, psi_status
    report = compute_drift_report()
    print(f"  Baseline computed : {report['baseline_computed_at'][:19]}")
    print(f"  Baseline samples  : {report['baseline_n_samples']:,}")
    print(f"  Current samples   : {report['current_n_samples']:,}")
    print(f"  Drift alert       : {'🔴 YES — retrain triggered' if report['drift_alert'] else '🟢 NO — stable'}")
    print()
    print(f"  {'Feature':<30} {'PSI':>8}  {'Status'}")
    print(f"  {'─'*30} {'─'*8}  {'─'*10}")
    for feat, info in report["features"].items():
        icon = {"stable": "🟢", "moderate": "🟡", "retrain": "🔴"}.get(info["status"], "")
        print(f"  {feat:<30} {info['psi']:>8.5f}  {icon} {info['status']}")
except Exception as e:
    print(f"  ERROR: {e}")
    print("  Run: python -m ml.train  (generates serving/training_baseline.json)")

# ── 2. Prometheus endpoint ────────────────────────────────
print("\n── Prometheus Metrics Endpoint ───────────────────────")
try:
    import urllib.request
    resp = urllib.request.urlopen("http://localhost:8000/metrics", timeout=2)
    body = resp.read().decode()
    metric_names = [l.split(" ")[0] for l in body.splitlines()
                    if l.startswith("streamlake_")]
    print(f"  API /metrics reachable : ✓")
    print(f"  StreamLake metrics     : {len(metric_names)}")
    for m in sorted(set(metric_names))[:8]:
        print(f"    {m}")
except Exception:
    print("  API not running — start with:")
    print("  uvicorn serving.app:app --port 8000")

# ── 3. Prometheus server ──────────────────────────────────
print("\n── Prometheus Server ─────────────────────────────────")
try:
    import urllib.request
    resp = urllib.request.urlopen("http://localhost:9090/-/healthy", timeout=2)
    print(f"  Prometheus at :9090    : ✓ ({resp.status})")
except Exception:
    print("  Prometheus not reachable — run: docker compose up -d")

# ── 4. Grafana ────────────────────────────────────────────
print("\n── Grafana ───────────────────────────────────────────")
try:
    import urllib.request
    resp = urllib.request.urlopen("http://localhost:3000/api/health", timeout=2)
    data = json.loads(resp.read())
    print(f"  Grafana at :3000       : ✓ (db={data.get('database','ok')})")
    print(f"  Dashboard import       : http://localhost:3000 → + → Import")
    print(f"  Dashboard JSON         : infra/grafana/dashboards/streamlake_ml.json")
except Exception:
    print("  Grafana not reachable — run: docker compose up -d")

# ── 5. Locust ─────────────────────────────────────────────
print("\n── Locust Load Test ──────────────────────────────────")
locust_file = Path("locust/locustfile.py")
if locust_file.exists():
    print(f"  Locustfile             : ✓ {locust_file}")
    print(f"  Run headless (60s):")
    print(f"    locust -f locust/locustfile.py \\")
    print(f"           --headless -u 50 -r 5 -t 60s \\")
    print(f"           --host http://localhost:8000")
    print(f"  Run UI (open :8089):")
    print(f"    locust -f locust/locustfile.py --host http://localhost:8000")
else:
    print("  ERROR: locust/locustfile.py not found")

print("\n✓ Phase 6 observability verification complete\n")
