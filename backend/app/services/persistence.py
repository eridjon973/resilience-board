from app.db.models import ChaosRecord, IncidentRecord
from app.db.session import SessionLocal


def incident_already_exists(data):
    db = SessionLocal()

    try:
        existing = (
            db.query(IncidentRecord)
            .filter(
                IncidentRecord.incident == data["incident"],
                IncidentRecord.namespace == data["namespace"],
                IncidentRecord.workload == data["workload"],
                IncidentRecord.deleted == data["deleted"],
                IncidentRecord.replacement == data["replacement"],
            )
            .first()
        )

        return existing is not None
    finally:
        db.close()


def save_incident_db(data, db_lock=None):
    if db_lock is None:
        return _save_incident_db_unlocked(data)

    with db_lock:
        return _save_incident_db_unlocked(data)


def _save_incident_db_unlocked(data):
    if incident_already_exists(data):
        return

    db = SessionLocal()

    try:
        row = IncidentRecord(**data)
        db.add(row)
        db.commit()
    finally:
        db.close()


def save_chaos_db(data, db_lock=None):
    if db_lock is None:
        return _save_chaos_db_unlocked(data)

    with db_lock:
        return _save_chaos_db_unlocked(data)


def _save_chaos_db_unlocked(data):
    db = SessionLocal()

    try:
        row = ChaosRecord(**data)
        db.add(row)
        db.commit()
    finally:
        db.close()


def get_recent_db_incidents(limit=10):
    db = SessionLocal()

    try:
        return (
            db.query(IncidentRecord)
            .order_by(IncidentRecord.id.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def get_recent_db_chaos(limit=10):
    db = SessionLocal()

    try:
        return (
            db.query(ChaosRecord)
            .order_by(ChaosRecord.id.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def incident_to_dict(record):
    return {
        "id": record.id,
        "incident": record.incident,
        "workload": record.workload,
        "namespace": record.namespace,
        "deleted": record.deleted,
        "replacement": record.replacement,
        "recovery_seconds": record.recovery_seconds,
        "detected_at": record.detected_at,
        "correlation": record.correlation,
    }


def chaos_to_dict(record):
    return {
        "id": record.id,
        "experiment": record.experiment,
        "status": record.status,
        "namespace": record.namespace,
        "workload": record.workload,
        "target_pod": record.target_pod,
        "time": record.time,
    }
