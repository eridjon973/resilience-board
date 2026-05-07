import pytest

from fastapi.testclient import TestClient

from main import (
    app,
    detect_self_healing,
    get_workload_key,
    recent_deleted_pods,
    recent_added_pods,
    incidents,
    save_incident_db,
    SessionLocal,
    IncidentRecord,
    ChaosRecord,
)


client = TestClient(app)


# ======================================================
# TEST HELPERS
# ======================================================

class FakeMeta:
    def __init__(self, name, namespace, labels=None):
        self.name = name
        self.namespace = namespace
        self.labels = labels or {}


class FakePod:
    def __init__(self, name, namespace="default", labels=None):
        self.metadata = FakeMeta(name, namespace, labels)


def reset_state():
    recent_deleted_pods.clear()
    recent_added_pods.clear()
    incidents.clear()


def clear_db():
    db = SessionLocal()
    try:
        db.query(IncidentRecord).delete()
        db.query(ChaosRecord).delete()
        db.commit()
    finally:
        db.close()

# ======================================================
# UNIT: WORKLOAD KEY
# ======================================================

def test_get_workload_key_app():
    pod = FakePod("p1", labels={"app": "demo"})
    assert get_workload_key(pod) == "demo"


def test_get_workload_key_run():
    pod = FakePod("p1", labels={"run": "job"})
    assert get_workload_key(pod) == "job"


def test_get_workload_key_unknown():
    pod = FakePod("p1", labels={})
    assert get_workload_key(pod) == "unknown-workload"


# ======================================================
# CORE: SELF-HEALING DETECTION
# ======================================================

def test_deleted_then_added_creates_incident():
    reset_state()
    clear_db()

    deleted = FakePod("pod-old", labels={"app": "demo"})
    added = FakePod("pod-new", labels={"app": "demo"})

    first_result = detect_self_healing("DELETED", deleted)
    second_result = detect_self_healing("ADDED", added)

    assert first_result is None
    assert second_result is not None
    assert second_result["incident"] == "SELF_HEALING"
    assert second_result["workload"] == "demo"
    assert second_result["namespace"] == "default"
    assert second_result["deleted"] == "pod-old"
    assert second_result["replacement"] == "pod-new"
    assert second_result["deleted"] != second_result["replacement"]
    assert second_result["correlation"] == "OUT_OF_ORDER_SAFE"


def test_added_then_deleted_out_of_order_creates_incident():
    reset_state()
    clear_db()

    deleted = FakePod("pod-old", labels={"app": "demo"})
    added = FakePod("pod-new", labels={"app": "demo"})

    first_result = detect_self_healing("ADDED", added)
    second_result = detect_self_healing("DELETED", deleted)

    assert first_result is None
    assert second_result is not None
    assert second_result["incident"] == "SELF_HEALING"
    assert second_result["workload"] == "demo"
    assert second_result["namespace"] == "default"
    assert second_result["deleted"] == "pod-old"
    assert second_result["replacement"] == "pod-new"
    assert second_result["deleted"] != second_result["replacement"]
    assert second_result["correlation"] == "OUT_OF_ORDER_SAFE"


def test_same_pod_not_valid_replacement():
    reset_state()
    clear_db()

    pod = FakePod("same-pod", labels={"app": "demo"})

    first_result = detect_self_healing("DELETED", pod)
    second_result = detect_self_healing("ADDED", pod)

    assert first_result is None
    assert second_result is None
    assert len(incidents) == 0


def test_different_namespace_does_not_correlate():
    reset_state()
    clear_db()

    deleted = FakePod("pod-old", namespace="default", labels={"app": "demo"})
    added = FakePod("pod-new", namespace="other", labels={"app": "demo"})

    first_result = detect_self_healing("DELETED", deleted)
    second_result = detect_self_healing("ADDED", added)

    assert first_result is None
    assert second_result is None
    assert len(incidents) == 0


def test_different_workload_does_not_correlate():
    reset_state()
    clear_db()

    deleted = FakePod("pod-old", labels={"app": "api"})
    added = FakePod("pod-new", labels={"app": "worker"})

    first_result = detect_self_healing("DELETED", deleted)
    second_result = detect_self_healing("ADDED", added)

    assert first_result is None
    assert second_result is None
    assert len(incidents) == 0


# ======================================================
# DATABASE: INCIDENT PERSISTENCE + DUPLICATE PROTECTION
# ======================================================

def test_duplicate_incident_not_inserted():
    reset_state()
    clear_db()

    pod1 = FakePod("old", labels={"app": "demo"})
    pod2 = FakePod("new", labels={"app": "demo"})

    first_result = detect_self_healing("DELETED", pod1)
    second_result = detect_self_healing("ADDED", pod2)

    assert first_result is None
    assert second_result is not None

    save_incident_db(second_result)

    db = SessionLocal()
    try:
        count = db.query(IncidentRecord).count()
        assert count == 1
    finally:
        db.close()


def test_save_incident_db_writes_record():
    reset_state()
    clear_db()

    data = {
        "incident": "SELF_HEALING",
        "workload": "demo",
        "namespace": "default",
        "deleted": "old-pod",
        "replacement": "new-pod",
        "recovery_seconds": 1.25,
        "detected_at": "2026-01-01T00:00:00+00:00",
        "correlation": "OUT_OF_ORDER_SAFE",
    }

    save_incident_db(data)

    db = SessionLocal()
    try:
        rows = db.query(IncidentRecord).all()
        assert len(rows) == 1
        assert rows[0].incident == "SELF_HEALING"
        assert rows[0].workload == "demo"
        assert rows[0].deleted == "old-pod"
        assert rows[0].replacement == "new-pod"
    finally:
        db.close()


# ======================================================
# API: TIMELINE
# ======================================================

def test_timeline_ordering_newest_first():
    reset_state()
    clear_db()

    db = SessionLocal()
    try:
        db.add(
            IncidentRecord(
                incident="SELF_HEALING",
                workload="demo",
                namespace="default",
                deleted="a",
                replacement="b",
                recovery_seconds=1,
                detected_at="2026-01-01T00:00:00+00:00",
                correlation="OUT_OF_ORDER_SAFE",
            )
        )

        db.add(
            IncidentRecord(
                incident="SELF_HEALING",
                workload="demo",
                namespace="default",
                deleted="c",
                replacement="d",
                recovery_seconds=1,
                detected_at="2026-02-01T00:00:00+00:00",
                correlation="OUT_OF_ORDER_SAFE",
            )
        )

        db.commit()
    finally:
        db.close()

    res = client.get("/timeline")
    assert res.status_code == 200

    data = res.json()
    events = data["events"]

    assert data["total_events"] == 2
    assert events[0]["time"] == "2026-02-01T00:00:00+00:00"
    assert events[1]["time"] == "2026-01-01T00:00:00+00:00"


# ======================================================
# API: PROMETHEUS METRICS
# ======================================================

def test_metrics_contains_prometheus_series():
    res = client.get("/metrics")

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")

    text = res.text

    assert "resilience_incidents_total" in text
    assert "resilience_chaos_events_total" in text
    assert "resilience_health_score" in text
    assert "resilience_watcher_running" in text
    assert "resilience_watcher_restart_count" in text


# ======================================================
# API: HEALTH / READINESS
# ======================================================


def test_behavioral_self_healing_flow():
    reset_state()
    clear_db()

    deleted = FakePod("pod-old", labels={"app": "demo"})
    added = FakePod("pod-new", labels={"app": "demo"})

    first = detect_self_healing("DELETED", deleted)
    second = detect_self_healing("ADDED", added)

    assert first is None
    assert second is not None

    db = SessionLocal()

    try:
        rows = db.query(IncidentRecord).all()
        assert len(rows) == 1
        assert rows[0].incident == "SELF_HEALING"
        assert rows[0].deleted == "pod-old"
        assert rows[0].replacement == "pod-new"
    finally:
        db.close()

    timeline_res = client.get("/timeline")
    assert timeline_res.status_code == 200

    timeline_data = timeline_res.json()

    assert timeline_data["total_events"] >= 1

    incident_events = [
        e for e in timeline_data["events"]
        if e["type"] == "INCIDENT"
    ]

    assert len(incident_events) >= 1

    latest = incident_events[0]

    assert latest["deleted"] == "pod-old"
    assert latest["replacement"] == "pod-new"

    health_res = client.get("/health/score")
    assert health_res.status_code == 200

    health_data = health_res.json()

    assert health_data["score"] < 100
    assert any(
        "incident" in reason.lower()
        for reason in health_data["reasons"]
    )

def test_health_structure():
    res = client.get("/health")
    assert res.status_code == 200

    data = res.json()

    assert "status" in data
    assert "watcher" in data
    assert "running" in data["watcher"]
    assert "restart_count" in data["watcher"]


def test_ready_structure():
    res = client.get("/ready")
    assert res.status_code == 200

    data = res.json()

    assert "ready" in data
    assert "reason" in data
    assert "watcher" in data


def test_health_score_bounds():
    res = client.get("/health/score")
    assert res.status_code == 200

    data = res.json()

    assert "score" in data
    assert 0 <= data["score"] <= 100


# ======================================================
# API: RESTORED ROUTE CONTRACTS
# ======================================================

def test_pods_route_structure(monkeypatch):
    class FakeStatus:
        phase = "Running"

    class FakePodWithStatus(FakePod):
        def __init__(self, name, namespace="default", labels=None):
            super().__init__(name, namespace, labels)
            self.status = FakeStatus()

    class FakePodList:
        items = [
            FakePodWithStatus("pod-a", labels={"app": "demo"})
        ]

    class FakeK8s:
        def list_pod_for_all_namespaces(self):
            return FakePodList()

    monkeypatch.setattr("main.load_k8s", lambda: FakeK8s())

    res = client.get("/pods")

    assert res.status_code == 200

    data = res.json()

    assert data["total"] == 1
    assert data["pods"][0]["name"] == "pod-a"
    assert data["pods"][0]["namespace"] == "default"
    assert data["pods"][0]["status"] == "Running"
    assert data["pods"][0]["workload"] == "demo"


def test_metrics_summary_structure():
    clear_db()

    res = client.get("/metrics/summary")

    assert res.status_code == 200

    data = res.json()

    assert "total_incidents" in data
    assert "total_chaos_experiments" in data
    assert "average_recovery_seconds" in data
    assert "latest_health_score" in data
    assert "watcher" in data
    assert "pods" in data
    assert "generated_at" in data


def test_db_incidents_route_structure():
    clear_db()

    res = client.get("/db/incidents")

    assert res.status_code == 200
    assert res.json() == []


def test_db_chaos_route_structure():
    clear_db()

    res = client.get("/db/chaos")

    assert res.status_code == 200
    assert res.json() == []


def test_chaos_kill_pod_route(monkeypatch):
    expected = {
        "experiment": "KILL_POD",
        "status": "FAILED",
        "namespace": "default",
        "workload": None,
        "target_pod": None,
        "time": "2026-01-01T00:00:00+00:00",
    }

    monkeypatch.setattr("main.kill_first_available_pod", lambda: expected)

    res = client.post("/chaos/kill-pod")

    assert res.status_code == 200
    assert res.json() == expected


def test_metrics_does_not_crash_when_health_unavailable(monkeypatch):
    monkeypatch.setattr(
        "main.calculate_health_score",
        lambda: {
            "score": 0,
            "status": "CRITICAL",
            "reasons": ["Kubernetes API unavailable"],
            "pods": {"total": 0, "running": 0, "failed": 0},
            "watcher": {
                "running": False,
                "started_at": None,
                "last_event_time": None,
                "last_error": "Kubernetes API unavailable",
                "restart_count": 0,
            },
            "recent_incidents_checked": 0,
            "recent_chaos_checked": 0,
            "evaluated_at": "2026-01-01T00:00:00+00:00",
        },
    )

    res = client.get("/metrics")

    assert res.status_code == 200
    assert "resilience_health_score" in res.text


def test_health_score_degrades_when_kubernetes_unavailable(monkeypatch):
    from app.services import health as health_service

    monkeypatch.setattr(
        health_service,
        "load_k8s",
        lambda: (_ for _ in ()).throw(RuntimeError("Kubernetes unavailable")),
    )

    data = health_service.calculate_health_score()

    assert data["score"] == 0
    assert data["status"] == "CRITICAL"
    assert "Kubernetes API unavailable" in data["reasons"][0]
