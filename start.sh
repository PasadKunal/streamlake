#!/bin/bash
# StreamLake — one-command demo startup
# Usage: ./start.sh

set -e
cd "$(dirname "$0")"

echo ""
echo "🌊  StreamLake Demo"
echo "════════════════════════════════════"

# 1. Docker services
echo "▶  Starting infrastructure (Docker)..."
docker compose up -d
echo "   ✓ MinIO · Redis · Redpanda · Postgres · Grafana · Prometheus"

# Wait for Redis to be healthy
echo "   Waiting for services..."
until docker exec streamlake-redis redis-cli ping 2>/dev/null | grep -q PONG; do
  sleep 1
done
echo "   ✓ All services healthy"

# 2. Python env
echo ""
echo "▶  Activating Python environment..."
source .venv/bin/activate

# 3. Start FastAPI in background
echo ""
echo "▶  Starting inference API on :8000..."
pkill -f "uvicorn serving.app" 2>/dev/null || true
uvicorn serving.app:app --port 8000 --log-level warning &
API_PID=$!
sleep 4

# Quick health check
if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
  echo "   ✓ API running (PID $API_PID)"
else
  echo "   ⚠ API may still be loading — check terminal for errors"
fi

# 4. Print service URLs
echo ""
echo "════════════════════════════════════"
echo "  🌐  Demo Dashboard  → http://localhost:8501"
echo "  🔧  FastAPI Docs    → http://localhost:8000/docs"
echo "  🪣  MinIO           → http://localhost:9001  (minioadmin / minioadmin)"
echo "  📨  Kafka UI        → http://localhost:8080"
echo "  📈  Grafana         → http://localhost:3000  (admin / admin)"
echo "  📊  Prometheus      → http://localhost:9090"
echo "════════════════════════════════════"
echo ""
echo "  Press Ctrl+C to stop everything"
echo ""

# 5. Open browser then start Streamlit (blocking)
sleep 1
open http://localhost:8501 2>/dev/null || true

streamlit run demo.py --server.port 8501 --server.headless true

# Cleanup on exit
echo ""
echo "Shutting down..."
kill $API_PID 2>/dev/null || true
docker compose down
echo "Done."
