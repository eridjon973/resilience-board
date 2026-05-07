from prometheus_client import CONTENT_TYPE_LATEST


def build_prometheus_metrics_output(
    incident_count: int,
    chaos_count: int,
    health_score: int,
    watcher_running: bool,
    watcher_restart_count: int,
) -> str:
    output = ""

    output += "# HELP resilience_incidents_total Total detected resilience incidents\n"
    output += "# TYPE resilience_incidents_total counter\n"
    output += f"resilience_incidents_total {incident_count}\n"

    output += "# HELP resilience_chaos_events_total Total chaos experiments executed\n"
    output += "# TYPE resilience_chaos_events_total counter\n"
    output += f"resilience_chaos_events_total {chaos_count}\n"

    output += "# HELP resilience_health_score Current resilience health score\n"
    output += "# TYPE resilience_health_score gauge\n"
    output += f"resilience_health_score {health_score}\n"

    output += "# HELP resilience_watcher_running Background watcher running status\n"
    output += "# TYPE resilience_watcher_running gauge\n"
    output += f"resilience_watcher_running {1 if watcher_running else 0}\n"

    output += "# HELP resilience_watcher_restart_count Background watcher restart count\n"
    output += "# TYPE resilience_watcher_restart_count counter\n"
    output += f"resilience_watcher_restart_count {watcher_restart_count}\n"

    return output
