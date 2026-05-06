import json
import os
import time
import threading
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from fastapi.responses import StreamingResponse, Response

from kubernetes import client, config, watch

from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from prometheus_client import generate_latest, Gauge, Counter, CONTENT_TYPE_LATEST

app = FastAPI()

CORRELATION_WINDOW_SECONDS = 30

recent_deleted_pods = []
recent_added_pods = []
incidents = []
chaos_history = []

watcher_status = {
    "running": False,
    "started_at": None,
    "last_event_time": None,
    "last_error": None,
    "restart_count": 0
}

db_lock = threading.Lock()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///resilience.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class WatcherStatusResponse(BaseModel):
    running: bool
    started_at: Optional[str]
    last_event_time: Optional[str]
    last_error: Optional[str]
    restart_count: int


class HealthPodsResponse(BaseModel):
    total: int
    running: int
    failed: int


class HealthScoreResponse(BaseModel):
    score: int
    status: str
    reasons: list[str]
    pods: HealthPodsResponse
    watcher: WatcherStatusResponse
    recent_incidents_checked: int
    recent_chaos_checked: int
    evaluated_at: str


class MetricsPodsResponse(BaseModel):
    total: int
    running: int
    failed: int
    pending: int


class CompactHealthScoreResponse(BaseModel):
    score: int
    status: str
    reasons: list[str]
    evaluated_at: str


class MetricsSummaryResponse(BaseModel):
    total_incidents: int
    total_chaos_experiments: int
    average_recovery_seconds: Optional[float]
    latest_health_score: CompactHealthScoreResponse
    watcher: WatcherStatusResponse
    pods: MetricsPodsResponse
    generated_at: str


class IncidentResponse(BaseModel):
    id: int
    incident: str
    workload: Optional[str]
    namespace: Optional[str]
    deleted: Optional[str]
    replacement: Optional[str]
    recovery_seconds: Optional[float]
    detected_at: Optional[str]
    correlation: Optional[str]


class TimelineEventResponse(BaseModel):
    type: str
    event: Optional[str]
    status: Optional[str] = None
    namespace: Optional[str] = None
    workload: Optional[str] = None
    target_pod: Optional[str] = None
    deleted: Optional[str] = None
    replacement: Optional[str] = None
    recovery_seconds: Optional[float] = None
    correlation: Optional[str] = None
    time: Optional[str]


class TimelineResponse(BaseModel):
    total_events: int
    events: list[TimelineEventResponse]
    generated_at: str


class IncidentRecord(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident = Column(String)
    workload = Column(String)
    namespace = Column(String)
    deleted = Column(String)
    replacement = Column(String)
    recovery_seconds = Column(Float)
    detected_at = Column(String)
    correlation = Column(String)


class ChaosRecord(Base):
    __tablename__ = "chaos"

    id = Column(Integer, primary_key=True, index=True)
    experiment = Column(String)
    status = Column(String)
    namespace = Column(String)
    workload = Column(String)
    target_pod = Column(String)
    time = Column(String)


Base.metadata.create_all(bind=engine)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_k8s():
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

    return client.CoreV1Api()


def get_workload_key(pod):
    labels = pod.metadata.labels or {}

    if "app" in labels:
        return labels["app"]

    if "run" in labels:
        return labels["run"]

    return "unknown-workload"


def clean_old_events():
    cutoff = time.time() - CORRELATION_WINDOW_SECONDS

    recent_deleted_pods[:] = [
        x for x in recent_deleted_pods
        if x["timestamp"] >= cutoff
    ]

    recent_added_pods[:] = [
        x for x in recent_added_pods
        if x["timestamp"] >= cutoff
    ]


def incident_already_exists(data):
    db = SessionLocal()

    try:
        existing = (
            db.query(IncidentRecord)
            .filter(
                IncidentRecord.incident == data["incident"],
                IncidentRecord.namespace == data["namespace"],
                IncidentRecord.workload == data["workload"],
                IncidentRecord.deleted == data["deleted"],
                IncidentRecord.replacement == data["replacement"]
            )
            .first()
        )

        return existing is not None
    finally:
        db.close()


def save_incident_db(data):
    with db_lock:
        if incident_already_exists(data):
            return

        db = SessionLocal()

        try:
            row = IncidentRecord(**data)
            db.add(row)
            db.commit()
        finally:
            db.close()


def save_chaos_db(data):
    with db_lock:
        db = SessionLocal()

        try:
            row = ChaosRecord(**data)
            db.add(row)
            db.commit()
        finally:
            db.close()


def get_recent_db_incidents(limit=10):
    db = SessionLocal()

    try:
        return (
            db.query(IncidentRecord)
            .order_by(IncidentRecord.id.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def get_recent_db_chaos(limit=10):
    db = SessionLocal()

    try:
        return (
            db.query(ChaosRecord)
            .order_by(ChaosRecord.id.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def detect_self_healing(event_type, pod):
    clean_old_events()

    pod_name = pod.metadata.name
    namespace = pod.metadata.namespace
    workload = get_workload_key(pod)
    timestamp = time.time()

    current = {
        "pod": pod_name,
        "namespace": namespace,
        "workload": workload,
        "timestamp": timestamp
    }

    if event_type == "DELETED":
        recent_deleted_pods.append(current)

        for added in recent_added_pods:
            if (
                added["workload"] == workload
                and added["namespace"] == namespace
                and added["pod"] != pod_name
            ):
                incident = {
                    "incident": "SELF_HEALING",
                    "workload": workload,
                    "namespace": namespace,
                    "deleted": pod_name,
                    "replacement": added["pod"],
                    "recovery_seconds": round(
                        abs(added["timestamp"] - timestamp), 3
                    ),
                    "detected_at": now_iso(),
                    "correlation": "OUT_OF_ORDER_SAFE"
                }

                incidents.append(incident)
                save_incident_db(incident)
                return incident

    if event_type == "ADDED":
        recent_added_pods.append(current)

        for deleted in recent_deleted_pods:
            if (
                deleted["workload"] == workload
                and deleted["namespace"] == namespace
                and deleted["pod"] != pod_name
            ):
                incident = {
                    "incident": "SELF_HEALING",
                    "workload": workload,
                    "namespace": namespace,
                    "deleted": deleted["pod"],
                    "replacement": pod_name,
                    "recovery_seconds": round(
                        abs(timestamp - deleted["timestamp"]), 3
                    ),
                    "detected_at": now_iso(),
                    "correlation": "OUT_OF_ORDER_SAFE"
                }

                incidents.append(incident)
                save_incident_db(incident)
                return incident

    return None


def background_pod_watcher():
    while True:
        try:
            watcher_status["running"] = True
            watcher_status["started_at"] = watcher_status["started_at"] or now_iso()
            watcher_status["last_error"] = None

            v1 = load_k8s()
            w = watch.Watch()

            for event in w.stream(
                v1.list_namespaced_pod,
                namespace="default"
            ):
                watcher_status["running"] = True
                watcher_status["last_event_time"] = now_iso()

                pod = event["object"]
                event_type = event["type"]

                incident = detect_self_healing(event_type, pod)

                if incident:
                    print(f"[BACKGROUND INCIDENT] {incident}")

        except Exception as e:
            watcher_status["running"] = False
            watcher_status["last_error"] = str(e)
            watcher_status["restart_count"] += 1

            print(f"[WATCHER ERROR] {e}")
            time.sleep(5)


@app.on_event("startup")
def start_background_watcher():
    thread = threading.Thread(
        target=background_pod_watcher,
        daemon=True
    )
    thread.start()


def kill_first_available_pod(namespace="default", workload=None):
    v1 = load_k8s()
    pods = v1.list_namespaced_pod(namespace=namespace)

    running = [
        pod for pod in pods.items
        if pod.status.phase == "Running"
    ]

    if workload:
        running = [
            pod for pod in running
            if get_workload_key(pod) == workload
        ]

    if not running:
        event = {
            "experiment": "KILL_POD",
            "status": "FAILED",
            "namespace": namespace,
            "workload": workload,
            "target_pod": None,
            "time": now_iso()
        }

        chaos_history.append(event)
        save_chaos_db(event)
        return event

    target = running[0]
    pod_name = target.metadata.name
    target_workload = get_workload_key(target)

    v1.delete_namespaced_pod(
        name=pod_name,
        namespace=namespace
    )

    event = {
        "experiment": "KILL_POD",
        "status": "TRIGGERED",
        "namespace": namespace,
        "workload": target_workload,
        "target_pod": pod_name,
        "time": now_iso()
    }

    chaos_history.append(event)
    save_chaos_db(event)

    return event


def calculate_health_score():
    v1 = load_k8s()
    pods = v1.list_pod_for_all_namespaces()

    total_pods = len(pods.items)
    running_pods = len([
        pod for pod in pods.items
        if pod.status.phase == "Running"
    ])
    failed_pods = len([
        pod for pod in pods.items
        if pod.status.phase in ["Failed", "Unknown"]
    ])

    score = 100
    reasons = []

    if total_pods == 0:
        return {
            "score": 0,
            "status": "CRITICAL",
            "reasons": ["No pods found in cluster"],
            "pods": {
                "total": 0,
                "running": 0,
                "failed": 0
            },
            "watcher": watcher_status,
            "recent_incidents_checked": 0,
            "recent_chaos_checked": 0,
            "evaluated_at": now_iso()
        }

    non_running = total_pods - running_pods

    if non_running > 0:
        penalty = non_running * 10
        score -= penalty
        reasons.append(f"{non_running} pod(s) are not running")

    if failed_pods > 0:
        penalty = failed_pods * 15
        score -= penalty
        reasons.append(f"{failed_pods} pod(s) are failed or unknown")

    if not watcher_status["running"]:
        score -= 25
        reasons.append("Background watcher is not running")

    recent_incidents = get_recent_db_incidents(limit=5)

    if recent_incidents:
        penalty = len(recent_incidents) * 3
        score -= penalty
        reasons.append(f"{len(recent_incidents)} recent incident(s) detected")

        slow_recoveries = [
            incident for incident in recent_incidents
            if incident.recovery_seconds and incident.recovery_seconds > 5
        ]

        if slow_recoveries:
            penalty = len(slow_recoveries) * 5
            score -= penalty
            reasons.append(
                f"{len(slow_recoveries)} slow recovery incident(s)"
            )

    recent_chaos = get_recent_db_chaos(limit=5)

    failed_chaos = [
        chaos for chaos in recent_chaos
        if chaos.status == "FAILED"
    ]

    if failed_chaos:
        penalty = len(failed_chaos) * 5
        score -= penalty
        reasons.append(f"{len(failed_chaos)} failed chaos experiment(s)")

    score = max(0, min(100, score))

    if score >= 90:
        status = "HEALTHY"
    elif score >= 70:
        status = "DEGRADED"
    elif score >= 40:
        status = "UNSTABLE"
    else:
        status = "CRITICAL"

    if not reasons:
        reasons.append("Cluster is healthy")

    return {
        "score": score,
        "status": status,
        "reasons": reasons,
        "pods": {
            "total": total_pods,
            "running": running_pods,
            "failed": failed_pods
        },
        "watcher": watcher_status,
        "recent_incidents_checked": len(recent_incidents),
        "recent_chaos_checked": len(recent_chaos),
        "evaluated_at": now_iso()
    }


def get_cluster_pod_metrics():
    v1 = load_k8s()
    pods = v1.list_pod_for_all_namespaces()

    total_pods = len(pods.items)
    running_pods = len([
        pod for pod in pods.items
        if pod.status.phase == "Running"
    ])
    failed_pods = len([
        pod for pod in pods.items
        if pod.status.phase in ["Failed", "Unknown"]
    ])
    pending_pods = len([
        pod for pod in pods.items
        if pod.status.phase == "Pending"
    ])

    return {
        "total": total_pods,
        "running": running_pods,
        "failed": failed_pods,
        "pending": pending_pods
    }


def incident_to_dict(record):
    return {
        "id": record.id,
        "incident": record.incident,
        "workload": record.workload,
        "namespace": record.namespace,
        "deleted": record.deleted,
        "replacement": record.replacement,
        "recovery_seconds": record.recovery_seconds,
        "detected_at": record.detected_at,
        "correlation": record.correlation
    }


def chaos_to_dict(record):
    return {
        "id": record.id,
        "experiment": record.experiment,
        "status": record.status,
        "namespace": record.namespace,
        "workload": record.workload,
        "target_pod": record.target_pod,
        "time": record.time
    }


@app.get("/health")
def health():
    return {
        "status": "healthy" if watcher_status["running"] else "degraded",
        "watcher": watcher_status
    }


@app.get("/ready")
def ready():
    if watcher_status["running"]:
        return {
            "ready": True,
            "reason": "API ready and background watcher running",
            "watcher": watcher_status
        }

    return {
        "ready": False,
        "reason": "Background watcher is not running",
        "watcher": watcher_status
    }


@app.get("/health/score", response_model=HealthScoreResponse)
def health_score():
    return calculate_health_score()


@app.get("/pods")
def get_pods():
    v1 = load_k8s()
    pods = v1.list_pod_for_all_namespaces()

    return [
        {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "status": pod.status.phase,
            "node": pod.spec.node_name,
            "workload": get_workload_key(pod)
        }
        for pod in pods.items
    ]


@app.post("/chaos/kill-pod")
def chaos_kill_pod():
    return kill_first_available_pod()


@app.get("/chaos/history")
def get_chaos_history():
    return chaos_history


@app.get("/incidents")
def get_incidents():
    return incidents


@app.get("/db/incidents", response_model=list[IncidentResponse])
def db_incidents():
    db = SessionLocal()

    try:
        rows = db.query(IncidentRecord).all()

        return [
            incident_to_dict(r)
            for r in rows
        ]
    finally:
        db.close()


@app.get("/db/chaos")
def db_chaos():
    db = SessionLocal()

    try:
        rows = db.query(ChaosRecord).all()

        return [
            chaos_to_dict(r)
            for r in rows
        ]
    finally:
        db.close()


@app.get("/timeline", response_model=TimelineResponse)
def timeline():
    db = SessionLocal()

    try:
        incident_rows = db.query(IncidentRecord).all()
        chaos_rows = db.query(ChaosRecord).all()

        events = []

        for row in chaos_rows:
            events.append({
                "type": "CHAOS",
                "event": row.experiment,
                "status": row.status,
                "namespace": row.namespace,
                "workload": row.workload,
                "target_pod": row.target_pod,
                "time": row.time
            })

        for row in incident_rows:
            events.append({
                "type": "INCIDENT",
                "event": row.incident,
                "namespace": row.namespace,
                "workload": row.workload,
                "deleted": row.deleted,
                "replacement": row.replacement,
                "recovery_seconds": row.recovery_seconds,
                "correlation": row.correlation,
                "time": row.detected_at
            })

        events.sort(
            key=lambda event: event["time"] or "",
            reverse=True
        )

        return {
            "total_events": len(events),
            "events": events,
            "generated_at": now_iso()
        }
    finally:
        db.close()

@app.get("/metrics")
def prometheus_metrics():
    db = SessionLocal()

    try:
        incident_count = db.query(IncidentRecord).count()
        chaos_count = db.query(ChaosRecord).count()
        health = calculate_health_score()

        output = ""

        output += "# HELP resilience_incidents_total Total detected resilience incidents\n"
        output += "# TYPE resilience_incidents_total counter\n"
        output += f"resilience_incidents_total {incident_count}\n"

        output += "# HELP resilience_chaos_events_total Total chaos experiments executed\n"
        output += "# TYPE resilience_chaos_events_total counter\n"
        output += f"resilience_chaos_events_total {chaos_count}\n"

        output += "# HELP resilience_health_score Current resilience health score\n"
        output += "# TYPE resilience_health_score gauge\n"
        output += f"resilience_health_score {health['score']}\n"

        output += "# HELP resilience_watcher_running Background watcher running status\n"
        output += "# TYPE resilience_watcher_running gauge\n"
        output += f"resilience_watcher_running {1 if watcher_status['running'] else 0}\n"

        output += "# HELP resilience_watcher_restart_count Background watcher restart count\n"
        output += "# TYPE resilience_watcher_restart_count counter\n"
        output += f"resilience_watcher_restart_count {watcher_status['restart_count']}\n"

        return Response(
            content=output,
            media_type=CONTENT_TYPE_LATEST
        )

    finally:
        db.close()


@app.get("/metrics/summary", response_model=MetricsSummaryResponse)
def metrics_summary():
    db = SessionLocal()

    try:
        incident_rows = db.query(IncidentRecord).all()
        chaos_rows = db.query(ChaosRecord).all()

        recovery_values = [
            row.recovery_seconds
            for row in incident_rows
            if row.recovery_seconds is not None
        ]

        average_recovery = (
            round(sum(recovery_values) / len(recovery_values), 3)
            if recovery_values
            else None
        )

        pod_metrics = get_cluster_pod_metrics()
        health = calculate_health_score()

        return {
            "total_incidents": len(incident_rows),
            "total_chaos_experiments": len(chaos_rows),
            "average_recovery_seconds": average_recovery,
            "latest_health_score": {
                "score": health["score"],
                "status": health["status"],
                "reasons": health["reasons"],
                "evaluated_at": health["evaluated_at"]
            },
            "watcher": watcher_status,
            "pods": {
                "total": pod_metrics["total"],
                "running": pod_metrics["running"],
                "failed": pod_metrics["failed"],
                "pending": pod_metrics["pending"]
            },
            "generated_at": now_iso()
        }
    finally:
        db.close()


@app.get("/metrics/incidents")
def metrics_incidents():
    db = SessionLocal()

    try:
        rows = db.query(IncidentRecord).all()

        by_type = {}
        by_workload = {}
        by_namespace = {}

        for row in rows:
            by_type[row.incident] = by_type.get(row.incident, 0) + 1
            by_workload[row.workload] = by_workload.get(row.workload, 0) + 1
            by_namespace[row.namespace] = by_namespace.get(row.namespace, 0) + 1

        recent = (
            db.query(IncidentRecord)
            .order_by(IncidentRecord.id.desc())
            .limit(10)
            .all()
        )

        return {
            "total_incidents": len(rows),
            "incidents_by_type": by_type,
            "incidents_by_workload": by_workload,
            "incidents_by_namespace": by_namespace,
            "most_recent_incidents": [
                incident_to_dict(row)
                for row in recent
            ],
            "generated_at": now_iso()
        }
    finally:
        db.close()


@app.get("/metrics/recovery-times")
def metrics_recovery_times():
    db = SessionLocal()

    try:
        rows = (
            db.query(IncidentRecord)
            .filter(IncidentRecord.recovery_seconds.isnot(None))
            .all()
        )

        recovery_values = [
            row.recovery_seconds
            for row in rows
        ]

        if recovery_values:
            average_recovery = round(
                sum(recovery_values) / len(recovery_values),
                3
            )
            fastest_recovery = min(recovery_values)
            slowest_recovery = max(recovery_values)
        else:
            average_recovery = None
            fastest_recovery = None
            slowest_recovery = None

        return {
            "records_checked": len(rows),
            "average_recovery_seconds": average_recovery,
            "fastest_recovery_seconds": fastest_recovery,
            "slowest_recovery_seconds": slowest_recovery,
            "recovery_records": [
                {
                    "id": row.id,
                    "incident": row.incident,
                    "workload": row.workload,
                    "namespace": row.namespace,
                    "deleted": row.deleted,
                    "replacement": row.replacement,
                    "recovery_seconds": row.recovery_seconds,
                    "detected_at": row.detected_at
                }
                for row in rows
            ],
            "generated_at": now_iso()
        }
    finally:
        db.close()


@app.get("/metrics/chaos")
def metrics_chaos():
    db = SessionLocal()

    try:
        rows = db.query(ChaosRecord).all()

        by_experiment = {}
        by_status = {}
        by_workload = {}

        for row in rows:
            by_experiment[row.experiment] = (
                by_experiment.get(row.experiment, 0) + 1
            )
            by_status[row.status] = by_status.get(row.status, 0) + 1

            workload_key = row.workload or "unknown-workload"
            by_workload[workload_key] = by_workload.get(workload_key, 0) + 1

        latest = (
            db.query(ChaosRecord)
            .order_by(ChaosRecord.id.desc())
            .limit(10)
            .all()
        )

        return {
            "total_chaos_experiments": len(rows),
            "triggered_experiments": by_status.get("TRIGGERED", 0),
            "failed_experiments": by_status.get("FAILED", 0),
            "experiments_by_type": by_experiment,
            "experiments_by_status": by_status,
            "experiments_by_workload": by_workload,
            "latest_chaos_events": [
                chaos_to_dict(row)
                for row in latest
            ],
            "generated_at": now_iso()
        }
    finally:
        db.close()


@app.get("/stream/events")
def stream_events():
    def event_generator():
        v1 = load_k8s()
        w = watch.Watch()

        for event in w.stream(
            v1.list_namespaced_pod,
            namespace="default"
        ):
            pod = event["object"]
            event_type = event["type"]

            incident = detect_self_healing(event_type, pod)

            if incident:
                yield f"data: {json.dumps(incident)}\n\n"

            payload = {
                "type": event_type,
                "pod": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "workload": get_workload_key(pod)
            }

            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
app.mount("/styles", StaticFiles(directory="static/styles"), name="styles")
app.mount("/src", StaticFiles(directory="static/src"), name="src")


@app.get("/")
def frontend():
    return FileResponse("static/index.html")
