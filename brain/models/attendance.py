"""
Attendance models for tracking worker entry/exit
"""
from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey
from datetime import datetime
import enum

from brain.models.events import Base


class SessionStatus(enum.Enum):
    """Status of an attendance session"""
    active = "active"           # Person is currently onsite
    completed = "completed"     # Person has exited
    abandoned = "abandoned"     # Session timeout (assumed exit)


class AttendanceSession(Base):
    """Individual worker attendance sessions"""
    __tablename__ = 'attendance_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Entry information
    entry_time = Column(DateTime, nullable=False, index=True)
    entry_camera = Column(String(100), nullable=False)
    entry_event_id = Column(Integer, ForeignKey('events.id'))
    
    # Exit information (null while active)
    exit_time = Column(DateTime, nullable=True)
    exit_camera = Column(String(100), nullable=True)
    exit_event_id = Column(Integer, ForeignKey('events.id'), nullable=True)
    
    # Duration tracking
    duration_minutes = Column(Integer, nullable=True)  # Calculated on exit
    
    # Status
    status = Column(Enum(SessionStatus), nullable=False, default=SessionStatus.active)
    
    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<AttendanceSession(id={self.id}, status={self.status.value}, entry={self.entry_time})>"
    
    def calculate_duration(self):
        """Calculate duration in minutes"""
        if self.exit_time and self.entry_time:
            delta = self.exit_time - self.entry_time
            self.duration_minutes = int(delta.total_seconds() / 60)
        return self.duration_minutes


class AttendanceDailySummary(Base):
    """Daily attendance summary statistics"""
    __tablename__ = 'attendance_daily_summary'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False, unique=True, index=True)  # Date only (no time)
    
    # Counts
    total_entries = Column(Integer, default=0)
    total_exits = Column(Integer, default=0)
    current_onsite = Column(Integer, default=0)
    
    # Time tracking
    total_person_minutes = Column(Integer, default=0)  # Sum of all session durations
    
    # Peak tracking
    peak_onsite = Column(Integer, default=0)
    peak_time = Column(DateTime, nullable=True)
    
    # Metadata
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<AttendanceDailySummary(date={self.date.date()}, entries={self.total_entries}, exits={self.total_exits})>"
    
    @property
    def average_hours_per_person(self):
        """Calculate average hours worked per person"""
        if self.total_entries == 0:
            return 0
        return round((self.total_person_minutes / 60) / self.total_entries, 2)