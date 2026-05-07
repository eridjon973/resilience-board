def get_workload_key(pod):
    labels = pod.metadata.labels or {}

    if "app" in labels:
        return labels["app"]

    if "run" in labels:
        return labels["run"]

    return "unknown-workload"
