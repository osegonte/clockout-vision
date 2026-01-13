"""
Attendance API endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import List

from brain.core.database import get_db
from brain.models.attendance import AttendanceSession, AttendanceDailySummary
from brain.services.attendance import AttendanceService
from pydantic import BaseModel

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


# Response models
class OnsiteResponse(BaseModel):
    current_onsite: int
    timestamp: datetime


class SessionResponse(BaseModel):
    id: int
    entry_time: datetime
    exit_time: datetime | None
    duration_minutes: int | None
    status: str
    
    class Config:
        from_attributes = True


class DailySummaryResponse(BaseModel):
    date: datetime
    total_entries: int
    total_exits: int
    current_onsite: int
    total_person_minutes: int
    peak_onsite: int
    peak_time: datetime | None
    average_hours_per_person: float
    
    class Config:
        from_attributes = True


# Endpoints
@router.get("/current", response_model=OnsiteResponse)
def get_current_onsite(db: Session = Depends(get_db)):
    """Get current number of people onsite"""
    service = AttendanceService(db)
    count = service.get_current_onsite()
    
    return {
        "current_onsite": count,
        "timestamp": datetime.utcnow()
    }


@router.get("/sessions/active", response_model=List[SessionResponse])
def get_active_sessions(db: Session = Depends(get_db)):
    """Get all currently active sessions"""
    service = AttendanceService(db)
    sessions = service.get_active_sessions()
    
    return sessions


@router.get("/sessions/today", response_model=List[SessionResponse])
def get_today_sessions(db: Session = Depends(get_db)):
    """Get all sessions from today"""
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    
    sessions = db.query(AttendanceSession)\
        .filter(AttendanceSession.entry_time >= today_start)\
        .order_by(AttendanceSession.entry_time.desc())\
        .all()
    
    return sessions


@router.get("/summary/today", response_model=DailySummaryResponse)
def get_today_summary(db: Session = Depends(get_db)):
    """Get today's attendance summary"""
    service = AttendanceService(db)
    summary = service.get_today_summary()
    
    if not summary:
        # Return empty summary
        return DailySummaryResponse(
            date=datetime.combine(date.today(), datetime.min.time()),
            total_entries=0,
            total_exits=0,
            current_onsite=0,
            total_person_minutes=0,
            peak_onsite=0,
            peak_time=None,
            average_hours_per_person=0.0
        )
    
    return summary


@router.get("/summary/history")
def get_summary_history(days: int = 7, db: Session = Depends(get_db)):
    """Get attendance summary for last N days"""
    summaries = db.query(AttendanceDailySummary)\
        .order_by(AttendanceDailySummary.date.desc())\
        .limit(days)\
        .all()
    
    return summaries