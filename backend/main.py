from app.services.health import calculate_health_score
import json
import os
import time
import threading
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel
from app.schemas import WatcherStatusResponse, HealthPodsResponse, HealthScoreResponse, MetricsPodsResponse, CompactHealthScoreResponse, MetricsSummaryResponse, IncidentResponse, TimelineEventResponse, TimelineResponse
from typing import Optional
from fastapi.responses import StreamingResponse, Response

from kubernetes import watch
from app.kubernetes.client import load_k8s

from app.db.session import engine, SessionLocal, Base
from app.db.models import IncidentRecord, ChaosRecord
from app.services.time import now_iso
from app.services.pods import get_workload_key
from app.services.persistence import incident_already_exists, save_incident_db, save_chaos_db, get_recent_db_incidents, get_recent_db_chaos, incident_to_dict, chaos_to_dict
from app.runtime.state import recent_deleted_pods, recent_added_pods, incidents, chaos_history, watcher_status, db_lock
from app.services.watcher import clean_old_events, detect_self_healing, background_pod_watcher

from app.metrics import CONTENT_TYPE_LATEST, build_prometheus_metrics_output

Base.metadata.create_all(bind=engine)

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.mount("/styles", StaticFiles(directory=os.path.join(STATIC_DIR, "styles")), name="styles")
app.mount("/src", StaticFiles(directory=os.path.join(STATIC_DIR, "src")), name="src")

CORRELATION_WINDOW_SECONDS = 30





@app.on_event("startup")
def start_background_watcher():
    thread = threading.Thread(
        target=background_pod_watcher,
        daemon=True
    )
    thread.start()


def kill_first_available_pod(namespace="default", workload=None):
    try:
        v1 = load_k8s()
        pods = v1.list_namespaced_pod(namespace=namespace)
    except Exception as exc:
        event = {
            "experiment": "KILL_POD",
            "status": "FAILED",
            "namespace": namespace,
            "workload": workload,
            "target_pod": None,
            "time": now_iso()
        }

        chaos_history.append(event)
        save_chaos_db(event, db_lock)
        return event

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
        save_chaos_db(event, db_lock)
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
    save_chaos_db(event, db_lock)

    return event




@app.get("/")
def dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


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

        events.sort(key=lambda e: e["time"] or "", reverse=True)

        return {
            "total_events": len(events),
            "events": events,
            "generated_at": now_iso()
        }
    finally:
        db.close()


@app.get("/metrics")
def metrics():
    db = SessionLocal()
    try:
        incident_count = db.query(IncidentRecord).count()
        chaos_count = db.query(ChaosRecord).count()
        health = calculate_health_score()

        output = build_prometheus_metrics_output(
            incident_count=incident_count,
            chaos_count=chaos_count,
            health_score=health["score"],
            watcher_running=watcher_status["running"],
            watcher_restart_count=watcher_status["restart_count"],
        )

        return Response(content=output, media_type=CONTENT_TYPE_LATEST)
    finally:
        db.close()


@app.get("/pods")
def pods():
    v1 = load_k8s()
    pod_list = v1.list_pod_for_all_namespaces()

    items = []

    for pod in pod_list.items:
        items.append({
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "status": pod.status.phase,
            "workload": get_workload_key(pod),
        })

    return {
        "total": len(items),
        "pods": items,
        "generated_at": now_iso(),
    }


@app.get("/metrics/summary", response_model=MetricsSummaryResponse)
def metrics_summary():
    db = SessionLocal()
    try:
        incident_rows = db.query(IncidentRecord).all()
        chaos_rows = db.query(ChaosRecord).all()
        health = calculate_health_score()

        recovery_values = [
            row.recovery_seconds
            for row in incident_rows
            if row.recovery_seconds is not None
        ]

        average_recovery = (
            sum(recovery_values) / len(recovery_values)
            if recovery_values
            else None
        )

        pod_health = health["pods"]

        return {
            "total_incidents": len(incident_rows),
            "total_chaos_experiments": len(chaos_rows),
            "average_recovery_seconds": average_recovery,
            "latest_health_score": {
                "score": health["score"],
                "status": health["status"],
                "reasons": health["reasons"],
                "evaluated_at": health["evaluated_at"],
            },
            "watcher": health["watcher"],
            "pods": {
                "total": pod_health["total"],
                "running": pod_health["running"],
                "failed": pod_health["failed"],
                "pending": pod_health.get("pending", 0),
            },
            "generated_at": now_iso(),
        }
    finally:
        db.close()


@app.get("/db/incidents", response_model=list[IncidentResponse])
def db_incidents():
    records = get_recent_db_incidents()
    return [incident_to_dict(record) for record in records]


@app.get("/db/chaos")
def db_chaos():
    records = get_recent_db_chaos()
    return [chaos_to_dict(record) for record in records]


@app.post("/chaos/kill-pod")
def chaos_kill_pod():
    return kill_first_available_pod()
