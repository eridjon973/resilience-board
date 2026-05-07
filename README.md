# Resilience Board

Resilience Board is a Kubernetes chaos engineering and self-healing observability platform.

It runs a FastAPI service that watches Kubernetes pod lifecycle events, triggers controlled pod failures, detects automatic recovery, persists resilience incidents, computes a cluster health score, exposes Prometheus-compatible metrics, and serves a lightweight operational dashboard.

This project is designed as a backend/platform engineering system, not a CRUD application.

---

# What It Demonstrates

- Kubernetes API integration from Python
- In-cluster authentication through ServiceAccount and RBAC
- Background pod watcher for lifecycle events
- Controlled chaos experiment: delete one safe running pod
- Kubernetes self-healing detection through replacement pod correlation
- Recovery-time measurement
- SQLite persistence for incidents and chaos experiments
- Health scoring based on cluster state, watcher state, recent incidents, and chaos history
- Prometheus-compatible metrics endpoint
- Dockerized FastAPI backend
- Kubernetes manifests for namespace, RBAC, deployment, and service
- GitHub Actions CI with automated tests and Docker image build validation
- Lightweight static dashboard served by the backend

---

# Current Status

Implemented and verified:

- FastAPI backend
- Kubernetes watcher
- chaos pod deletion endpoint
- incident persistence
- chaos experiment persistence
- health score endpoint
- timeline endpoint
- database inspection endpoints
- Prometheus metrics endpoint
- Docker build
- kind-based Kubernetes deployment
- GitHub Actions CI
- 23 automated tests

Planned but not yet implemented:

- AWS deployment
- Terraform infrastructure
- production database backend
- authentication
- alerting integration

---

# Architecture Overview

```text
User / Dashboard / API Client
        |
        v
FastAPI Backend
        |
        |-- API routes
        |-- health scoring
        |-- metrics rendering
        |-- chaos execution
        |-- timeline aggregation
        |
        v
Kubernetes Client
        |
        |-- list pods
        |-- watch pod events
        |-- delete selected pod
        |
        v
Kubernetes Cluster
        |
        |-- Deployment recreates deleted pods
        |-- Watcher detects deletion and replacement
        |
        v
Persistence Layer
        |
        |-- incidents
        |-- chaos experiments
        |
        v
SQLite
```

---

# Repository Structure

```text
resilience-board/
├── .github/
│   └── workflows/
│       └── ci.yml
├── README.md
├── pytest.ini
├── backend/
│   ├── main.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── schemas.py
│   │   ├── metrics.py
│   │   ├── db/
│   │   │   ├── models.py
│   │   │   └── session.py
│   │   ├── kubernetes/
│   │   │   └── client.py
│   │   ├── runtime/
│   │   │   └── state.py
│   │   └── services/
│   │       ├── health.py
│   │       ├── persistence.py
│   │       ├── pods.py
│   │       ├── time.py
│   │       └── watcher.py
│   ├── frontend/
│   ├── static/
│   ├── k8s/
│   │   ├── namespace.yaml
│   │   ├── rbac.yaml
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   └── tests/
│       └── test_resilience.py
```

---

# Core Backend Components

## `backend/main.py`

FastAPI application entry point.

Responsibilities:

- registers API routes
- starts the background watcher on application startup
- serves static dashboard files
- exposes health, metrics, timeline, pod, database, and chaos endpoints

---

## `backend/app/services/watcher.py`

Background Kubernetes watcher.

Responsibilities:

- watches pod lifecycle events
- detects deleted pods
- detects added replacement pods
- correlates self-healing behavior
- records recovery time
- persists incidents
- updates watcher runtime state

---

## `backend/app/services/health.py`

Health scoring service.

Responsibilities:

- loads Kubernetes client
- counts pod states
- evaluates watcher state
- includes recent incidents and chaos activity
- degrades safely when Kubernetes API/configuration is unavailable

---

## `backend/app/services/persistence.py`

Persistence service.

Responsibilities:

- saves incidents
- saves chaos experiments
- prevents duplicate incident insertion
- reads persisted database records
- converts ORM records into API-safe dictionaries

---

## `backend/app/services/pods.py`

Pod workload helper.

Responsibilities:

- maps Kubernetes pod labels to workload names
- supports correlation by workload identity

---

## `backend/app/metrics.py`

Prometheus metrics renderer.

Responsibilities:

- exposes counters and gauges as text
- includes incident count, chaos count, health score, pod counts, watcher state, and recovery metrics

---

## `backend/app/runtime/state.py`

Runtime shared state.

Responsibilities:

- tracks recent deleted pods
- tracks recent added pods
- stores in-memory incidents and chaos history
- stores watcher status
- provides shared lock for runtime state access

---

# API Surface

## Health and Readiness

```http
GET /health
GET /ready
GET /health/score
```

## Kubernetes Pod View

```http
GET /pods
```

## Chaos Execution

```http
POST /chaos/kill-pod
```

## Timeline

```http
GET /timeline
```

## Persistence Inspection

```http
GET /db/incidents
GET /db/chaos
```

## Metrics

```http
GET /metrics
GET /metrics/summary
```

---

# Running Tests

```bash
env -u PYTHONPATH pytest -q
```

Current verified result:

```text
23 passed
```

---

# Docker

Build:

```bash
docker build -t resilience-board-api:local backend
```

Run:

```bash
docker run --rm -p 8000:8000 resilience-board-api:local
```

---

# kind Deployment

```bash
docker build -t resilience-board-api:latest backend

kind load docker-image resilience-board-api:latest --name resilience-board

kubectl apply -f backend/k8s/namespace.yaml
kubectl apply -f backend/k8s/rbac.yaml
kubectl apply -f backend/k8s/deployment.yaml
kubectl apply -f backend/k8s/service.yaml
```

---

# CI

GitHub Actions currently performs:

1. repository checkout
2. Python 3.12 setup
3. dependency installation
4. pytest execution
5. Docker image build validation

Workflow:

```text
.github/workflows/ci.yml
```

---

# Dashboard

The project includes a lightweight operational dashboard using:

- vanilla HTML
- CSS
- JavaScript

---

# Engineering Notes

- watcher is concurrency-sensitive
- runtime SQLite databases are ignored by Git
- health scoring degrades safely when Kubernetes is unavailable
- tests must not depend on a real Kubernetes cluster
- Kubernetes interactions are mocked in CI

---

# Roadmap

- AWS deployment
- Terraform infrastructure
- cloud database option
- authentication
- alerting integration
- Prometheus/Grafana deployment path
- release tagging
- architecture diagrams
- dashboard screenshots and demo evidence
