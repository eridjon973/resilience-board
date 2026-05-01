from fastapi import FastAPI
from kubernetes import client, config

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Resilience Board API running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/pods")
def get_pods():
    config.load_kube_config()
    v1 = client.CoreV1Api()

    pods = v1.list_pod_for_all_namespaces()

    return [
        {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "status": pod.status.phase,
            "node": pod.spec.node_name,
        }
        for pod in pods.items
    ]

@app.post("/break-pod")
def break_pod():
    config.load_kube_config()
    v1 = client.CoreV1Api()

    pods = v1.list_namespaced_pod(namespace="default")

    if not pods.items:
        return {"message": "No pods found"}

    pod_name = pods.items[0].metadata.name

    v1.delete_namespaced_pod(
        name=pod_name,
        namespace="default"
    )

    return {"deleted_pod": pod_name}
