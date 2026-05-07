from typing import Optional
from pydantic import BaseModel

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
