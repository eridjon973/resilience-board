from app.kubernetes.client import load_k8s
from app.runtime.state import watcher_status
from app.services.time import now_iso
from app.services.persistence import get_recent_db_incidents, get_recent_db_chaos


def calculate_health_score():
    try:
        v1 = load_k8s()
        pods = v1.list_pod_for_all_namespaces()
    except Exception as exc:
        return {
            "score": 0,
            "status": "CRITICAL",
            "reasons": [f"Kubernetes API unavailable: {exc}"],
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
            reasons.append(f"{len(slow_recoveries)} slow recovery incident(s)")

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
