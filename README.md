# Resilience Board

## Live Deployment

Public API:

* http://3.75.253.170/docs
* http://3.75.253.170/health
* http://3.75.253.170/metrics

Cloud Infrastructure:

* AWS EC2
* Amazon ECR
* Docker
* Elastic IP
* IAM role-based image pulls

## API Documentation

### OpenAPI Endpoints

![OpenAPI Endpoints](docs/images/openapi-endpoints.png)

### OpenAPI Schemas

![OpenAPI Schemas](docs/images/openapi-schemas.png)

---
# Overview

Resilience Board is a Kubernetes chaos engineering and self-healing observability platform.

It runs a FastAPI service that watches Kubernetes pod lifecycle events, triggers controlled pod failures, detects automatic recovery, persists resilience incidents, computes a cluster health score, exposes Prometheus-compatible metrics, and provides operational telemetry APIs.

This project was built as a backend/platform engineering system, not a CRUD application.

---

# Why This Project Exists

Most portfolio projects demonstrate CRUD functionality.

Resilience Board was designed to demonstrate real backend and infrastructure engineering concepts:

* Kubernetes integration
* chaos engineering
* observability
* self-healing detection
* cloud deployment
* containerization
* operational telemetry
* CI/CD workflows
* production-style infrastructure

---

# Technology Stack

## Backend

* Python
* FastAPI
* SQLAlchemy
* Uvicorn

## Infrastructure

* Docker
* Kubernetes
* kind
* AWS EC2
* Amazon ECR
* IAM
* Elastic IP

## Observability

* Prometheus-compatible metrics
* health scoring
* runtime telemetry

## Persistence

* SQLite

## Testing / CI

* pytest
* GitHub Actions

---

# What It Demonstrates

* Kubernetes API integration from Python
* In-cluster authentication through ServiceAccount and RBAC
* Background Kubernetes pod watcher
* Controlled chaos experiment execution
* Autonomous self-healing detection
* Recovery-time measurement
* Persistence of resilience incidents and chaos experiments
* Cluster health scoring
* Prometheus-compatible metrics rendering
* Dockerized backend deployment
* Kubernetes manifests for deployment and RBAC
* Public AWS cloud deployment
* Amazon ECR image registry workflow
* IAM role-based image pulling
* GitHub Actions CI pipeline
* Production-style deployment workflow

---

# Current Status

Implemented and verified:

* FastAPI backend
* Kubernetes watcher
* pod deletion detection
* self-healing correlation
* resilience incident persistence
* chaos experiment persistence
* health scoring system
* Prometheus metrics endpoint
* timeline endpoint
* Dockerized runtime
* kind Kubernetes deployment
* AWS EC2 deployment
* Amazon ECR integration
* Elastic IP public exposure
* IAM role-based container pulls
* GitHub Actions CI
* 23 automated tests

Current live deployment:

* Public FastAPI documentation endpoint
* Public metrics endpoint
* Public health endpoint
* Persistent EC2 container runtime

---

# Production Deployment

Resilience Board is publicly deployed on AWS infrastructure.

Current deployment architecture:

```text
GitHub
   |
   v
GitHub Actions CI
   |
   v
Docker Image Build
   |
   v
Amazon ECR
   |
   v
AWS EC2 Instance
   |
   |-- Docker Runtime
   |-- FastAPI Backend
   |-- Public API
   |-- Metrics Endpoint
   |
   v
Kubernetes Cluster
   |
   |-- Pod lifecycle monitoring
   |-- Self-healing detection
   |
   v
SQLite Persistence
```

Infrastructure currently includes:

* Ubuntu 24.04 EC2 instance
* Docker container runtime
* Amazon ECR image registry
* Elastic IP static public endpoint
* IAM role-based ECR authentication

---

# Architecture Overview

```text
User / API Client
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

## backend/main.py

FastAPI application entry point.

Responsibilities:

* registers API routes
* starts the Kubernetes watcher
* exposes health endpoints
* exposes metrics endpoints
* exposes persistence inspection endpoints
* exposes chaos execution endpoints

---

## backend/app/services/watcher.py

Concurrent Kubernetes watcher.

Responsibilities:

* watches Kubernetes pod lifecycle events
* detects deleted pods
* detects replacement pods
* correlates self-healing events
* records recovery timing
* persists resilience incidents
* updates runtime watcher state

---

## backend/app/services/health.py

Health scoring service.

Responsibilities:

* loads Kubernetes client
* evaluates cluster state
* evaluates watcher state
* computes resilience health score
* safely degrades when Kubernetes is unavailable

---

## backend/app/services/persistence.py

Persistence layer service.

Responsibilities:

* stores incidents
* stores chaos experiments
* prevents duplicate insertions
* converts ORM records into API-safe structures

---

## backend/app/services/pods.py

Pod workload helper.

Responsibilities:

* maps Kubernetes pod labels to workload names
* supports workload-level recovery correlation

---

## backend/app/runtime/state.py

Shared runtime state.

Responsibilities:

* tracks deleted pods
* tracks replacement pods
* stores watcher status
* stores runtime incidents
* provides concurrency-safe shared state

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

# Kubernetes Deployment

```bash
docker build -t resilience-board-api:latest backend

kind load docker-image resilience-board-api:latest --name resilience-board

kubectl apply -f backend/k8s/namespace.yaml
kubectl apply -f backend/k8s/rbac.yaml
kubectl apply -f backend/k8s/deployment.yaml
kubectl apply -f backend/k8s/service.yaml
```

---

# AWS Deployment

Public deployment currently runs on:

* AWS EC2
* Docker
* Amazon ECR
* Elastic IP
* IAM instance profile authentication

Container image registry:

```text
227270320785.dkr.ecr.eu-central-1.amazonaws.com/resilience-board-api:latest
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

# Engineering Challenges Solved

Key engineering problems solved during development:

* Safe degradation when Kubernetes configuration is unavailable
* Recovery from accidental FastAPI route deletion during refactoring
* CI stabilization without real Kubernetes access
* Self-healing correlation for replacement pods
* Separation of orchestration and business logic into services
* ECR authentication through IAM roles instead of static credentials
* Runtime-safe watcher state handling
* Public cloud deployment verification

---

# Dashboard

The project includes an operational dashboard built using:

* HTML
* CSS
* JavaScript

Recommended next improvement:

* add dashboard screenshots directly into the README

---

# Engineering Notes

* watcher is concurrency-sensitive
* tests do not require a real Kubernetes cluster
* Kubernetes interactions are mocked during CI
* runtime SQLite databases are ignored by Git
* health scoring safely degrades outside Kubernetes
* container runtime survives EC2 reboot through restart policies

---

# Future Infrastructure Improvements

* Terraform infrastructure provisioning
* PostgreSQL/RDS migration
* HTTPS and reverse proxy
* domain name
* Prometheus + Grafana stack
* Kubernetes cloud cluster deployment
* release tagging
* deployment automation
* dashboard screenshots and architecture diagrams
