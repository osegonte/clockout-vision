"""
Event models for storing Frigate detections
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class RawEvent(Base):
    """Raw events from Frigate - immutable audit log"""
    __tablename__ = 'raw_events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    source = Column(String(50), nullable=False)  # 'frigate'
    camera_id = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)  # Full Frigate event JSON
    
    def __repr__(self):
        return f"<RawEvent(id={self.id}, camera={self.camera_id}, time={self.timestamp})>"


class Event(Base):
    """Normalized events for business logic"""
    __tablename__ = 'events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    camera_id = Column(String(100), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # 'detection', 'entry', 'exit', etc.
    object_type = Column(String(50), nullable=False)  # 'person', 'vehicle', etc.
    confidence = Column(Float, nullable=False)
    
    # Bounding box and region info
    bbox = Column(JSON)  # [x, y, w, h]
    area = Column(Integer)
    
    # References
    frigate_event_id = Column(String(100))  # Frigate's event ID
    snapshot_ref = Column(String(500))  # Path to snapshot
    clip_ref = Column(String(500))  # Path to clip
    
    # Metadata - renamed to avoid SQLAlchemy reserved word
    extra_data = Column(JSON)  # Additional data (zones, scores, etc.)
    
    def __repr__(self):
        return f"<Event(id={self.id}, type={self.event_type}, camera={self.camera_id})>"
