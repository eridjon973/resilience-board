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
