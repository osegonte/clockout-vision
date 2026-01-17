"""
Person Model - Store worker information and face encodings
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime
from brain.models.events import Base


class Person(Base):
    """
    Represents a worker/person in the system.
    Stores their face encoding for identification.
    """
    __tablename__ = 'persons'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    
    # Face encoding stored as binary (128 float32 values = 512 bytes)
    face_encoding = Column(LargeBinary, nullable=True)
    
    # Optional: store reference photo path
    photo_path = Column(String(255), nullable=True)
    
    # Metadata
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Notes/description
    notes = Column(String(500), nullable=True)
    
    # Relationships
    attendance_sessions = relationship("AttendanceSession", back_populates="person")
    
    def __repr__(self):
        return f"<Person(id={self.id}, name='{self.name}', active={self.is_active})>"
    
    def to_dict(self):
        """Convert to dictionary (exclude face encoding)"""
        return {
            'id': self.id,
            'name': self.name,
            'enrolled_at': self.enrolled_at.isoformat() if self.enrolled_at else None,
            'is_active': self.is_active,
            'has_face_encoding': self.face_encoding is not None,
            'notes': self.notes
        }
