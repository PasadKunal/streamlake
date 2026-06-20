"""
Locust load test for the StreamLake churn prediction API.

Simulates realistic production traffic against the FastAPI inference endpoint.

Usage:
    # Headless — 50 concurrent users, 5 spawn/sec, run for 60s
    locust -f locust/locustfile.py \
           --headless -u 50 -r 5 -t 60s \
           --host http://localhost:8000

    # UI mode (open http://localhost:8089)
    locust -f locust/locustfile.py --host http://localhost:8000

Target SLOs:
    p50 latency  < 30ms
    p99 latency  < 100ms
    Error rate   < 0.1%
"""
import random
from locust import HttpUser, between, task

# Sample from users that were materialised into Redis in Phase 4
# Range matches USER-000000 … USER-009999 used by the producer
_USER_IDS = [f"USER-{i:06d}" for i in random.sample(range(1000, 9000), 500)]


class ChurnPredictionUser(HttpUser):
    """
    Simulates a downstream service calling the inference API.
    Task weights mirror realistic production traffic:
      - 80% predict  (core use case)
      - 15% health   (load balancer probes)
      -  5% features (debug / feature inspection)
    """
    wait_time = between(0.05, 0.3)  # 50ms – 300ms think time

    @task(16)
    def predict(self):
        user_id = random.choice(_USER_IDS)
        with self.client.post(
            "/predict",
            json={"user_id": user_id},
            name="/predict",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if "churn_probability" not in data:
                    resp.failure("Missing churn_probability in response")
            elif resp.status_code == 404:
                resp.success()  # Unknown user — expected for some IDs
            else:
                resp.failure(f"Unexpected status {resp.status_code}")

    @task(3)
    def health_check(self):
        self.client.get("/health", name="/health")

    @task(1)
    def get_features(self):
        user_id = random.choice(_USER_IDS)
        with self.client.get(
            f"/features/{user_id}",
            name="/features/{user_id}",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")
