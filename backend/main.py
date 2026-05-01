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
