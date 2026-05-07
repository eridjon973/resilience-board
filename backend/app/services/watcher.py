import time

from app.runtime.state import (
    recent_deleted_pods,
    recent_added_pods,
    incidents,
    db_lock,
)

from app.services.time import now_iso
from app.services.pods import get_workload_key
from app.services.persistence import save_incident_db


CORRELATION_WINDOW_SECONDS = 30


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
                save_incident_db(incident, db_lock)

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
                save_incident_db(incident, db_lock)

                return incident

    return None
