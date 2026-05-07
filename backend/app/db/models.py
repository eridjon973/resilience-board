from sqlalchemy import Column, Integer, String, Float
from app.db.session import Base

class IncidentRecord(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident = Column(String)
    workload = Column(String)
    namespace = Column(String)
    deleted = Column(String)
    replacement = Column(String)
    recovery_seconds = Column(Float)
    detected_at = Column(String)
    correlation = Column(String)


class ChaosRecord(Base):
    __tablename__ = "chaos"

    id = Column(Integer, primary_key=True, index=True)
    experiment = Column(String)
    status = Column(String)
    namespace = Column(String)
    workload = Column(String)
    target_pod = Column(String)
    time = Column(String)

