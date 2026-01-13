"""
Simplified Attendance Module - FINAL FIXED VERSION
Uses Frigate zone detection for reliable attendance tracking
All bugs fixed and ready for production testing
"""
import logging
from datetime import datetime, date
from typing import Optional
from sqlalchemy.orm import Session

from brain.models.events import Event
from brain.models.attendance import AttendanceSession, AttendanceDailySummary, SessionStatus
from brain.core.redis_client import redis_client

logger = logging.getLogger(__name__)


class AttendanceModule:
    """
    Simplified attendance tracking using zone detection.
    
    Logic:
    - Person enters gate zone = Entry (create session)
    - Person exits gate zone after being tracked = Exit (close session)
    - Uses zone duration to avoid false triggers
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.redis = redis_client.get_client()
        
        # Configuration
        self.enabled = True
        self.gate_zone = "gate_entrance"
        self.gate_camera = "test_camera"
        self.min_zone_duration = 1.0  # Seconds in zone to count as entry/exit
        self.cooldown_seconds = 15     # Prevent double-counting
    
    def process_event(self, event: Event):
        """
        Process detection event for attendance tracking.
        
        Args:
            event: Detection event from Frigate
        """
        if not self.enabled:
            return
        
        # Only process person detections
        if event.object_type != 'person':
            return
        
        # Only process events from our gate camera
        if event.camera_id != self.gate_camera:
            return
        
        # Check if person is in gate zone
        zones = event.extra_data.get('zones', []) if event.extra_data else []
        
        if self.gate_zone in zones:
            self._handle_zone_entry(event)
        else:
            # Person detected but not in gate zone anymore
            self._handle_zone_exit(event)
    
    def _handle_zone_entry(self, event: Event):
        """Handle person entering gate zone"""
        
        # Check cooldown to prevent spam
        detection_key = f"detection_{event.frigate_event_id or event.id}"
        if self._is_in_cooldown(detection_key):
            logger.debug(f"Detection {detection_key} in cooldown, skipping")
            return
        
        # Track this detection in Redis with timestamp
        self._track_zone_presence(event)
        
        # Check if person has been in zone long enough
        zone_duration = self._get_zone_duration(event)
        
        if zone_duration >= self.min_zone_duration:
            # Check if we already counted this entry
            if not self._was_counted(event, 'entry'):
                self._record_entry(event)
                self._mark_counted(event, 'entry')
                self._set_cooldown(detection_key)
    
    def _handle_zone_exit(self, event: Event):
        """Handle person leaving gate zone"""
        
        # Check if this person had an active presence in the zone
        zone_duration = self._get_zone_duration(event)
        
        if zone_duration >= self.min_zone_duration:
            # Person was in zone long enough and now left
            if not self._was_counted(event, 'exit'):
                self._record_exit(event)
                self._mark_counted(event, 'exit')
        
        # Clean up tracking
        self._clear_zone_tracking(event)
    
    def _track_zone_presence(self, event: Event):
        """Track when person entered the zone"""
        detection_id = event.frigate_event_id or f"event_{event.id}"
        key = f"attendance:zone_entry:{self.gate_camera}:{detection_id}"
        
        # Store entry timestamp if not already stored
        if not self.redis.exists(key):
            self.redis.setex(
                key,
                30,  # Expire after 30 seconds
                event.timestamp.timestamp()
            )
    
    def _get_zone_duration(self, event: Event) -> float:
        """Get how long person has been in zone"""
        detection_id = event.frigate_event_id or f"event_{event.id}"
        key = f"attendance:zone_entry:{self.gate_camera}:{detection_id}"
        
        entry_time = self.redis.get(key)
        if not entry_time:
            return 0.0
        
        entry_timestamp = float(entry_time)
        current_timestamp = event.timestamp.timestamp()
        
        return current_timestamp - entry_timestamp
    
    def _clear_zone_tracking(self, event: Event):
        """Clear zone tracking data"""
        detection_id = event.frigate_event_id or f"event_{event.id}"
        key = f"attendance:zone_entry:{self.gate_camera}:{detection_id}"
        self.redis.delete(key)
    
    def _was_counted(self, event: Event, action: str) -> bool:
        """Check if this detection was already counted"""
        detection_id = event.frigate_event_id or f"event_{event.id}"
        key = f"attendance:counted:{action}:{detection_id}"
        return self.redis.exists(key) > 0
    
    def _mark_counted(self, event: Event, action: str):
        """Mark detection as counted"""
        detection_id = event.frigate_event_id or f"event_{event.id}"
        key = f"attendance:counted:{action}:{detection_id}"
        self.redis.setex(key, 60, '1')  # Remember for 60 seconds
    
    def _is_in_cooldown(self, detection_key: str) -> bool:
        """Check if detection is in cooldown"""
        key = f"attendance:cooldown:{detection_key}"
        return self.redis.exists(key) > 0
    
    def _set_cooldown(self, detection_key: str):
        """Set cooldown for detection"""
        key = f"attendance:cooldown:{detection_key}"
        self.redis.setex(key, self.cooldown_seconds, '1')
    
    def _record_entry(self, event: Event):
        """Record a worker entry"""
        logger.info(f"✅ Worker ENTERED through gate at {event.timestamp}")
        
        # Create new session
        session = AttendanceSession(
            entry_time=event.timestamp,
            entry_camera=event.camera_id,
            entry_event_id=event.id,
            status=SessionStatus.active
        )
        self.db.add(session)
        self.db.commit()
        
        # Increment onsite count
        new_count = redis_client.increment_onsite()
        logger.info(f"📊 Onsite count: {new_count}")
        
        # Update daily summary
        self._update_daily_summary('entry')
    
    def _record_exit(self, event: Event):
        """Record a worker exit"""
        logger.info(f"👋 Worker EXITED through gate at {event.timestamp}")
        
        # Find most recent active session
        session = self.db.query(AttendanceSession)\
            .filter(AttendanceSession.status == SessionStatus.active)\
            .order_by(AttendanceSession.entry_time.desc())\
            .first()
        
        if session:
            # Complete the session
            session.exit_time = event.timestamp
            session.exit_camera = event.camera_id
            session.exit_event_id = event.id
            session.status = SessionStatus.completed
            session.calculate_duration()
            self.db.commit()
            
            logger.info(f"✅ Session completed: {session.duration_minutes} minutes")
        else:
            logger.warning("⚠️  Exit detected but no active session found")
        
        # Decrement onsite count
        new_count = redis_client.decrement_onsite()
        logger.info(f"📊 Onsite count: {new_count}")
        
        # Update daily summary
        self._update_daily_summary('exit')
    
    def _update_daily_summary(self, action: str):
        """Update daily summary statistics - FIXED VERSION"""
        today = date.today()
        today_dt = datetime.combine(today, datetime.min.time())
        
        # Get or create today's summary
        summary = self.db.query(AttendanceDailySummary)\
            .filter(AttendanceDailySummary.date == today_dt)\
            .first()
        
        if not summary:
            summary = AttendanceDailySummary(
                date=today_dt,
                total_entries=0,
                total_exits=0,
                current_onsite=0,
                peak_onsite=0  # FIX: Initialize to 0, not NULL
            )
            self.db.add(summary)
        
        # Update counts
        if action == 'entry':
            summary.total_entries += 1
        elif action == 'exit':
            summary.total_exits += 1
        
        # Update current onsite from Redis
        summary.current_onsite = redis_client.get_onsite_count()
        
        # Track peak - FIX: Handle NULL case
        if summary.peak_onsite is None:
            summary.peak_onsite = 0
        
        if summary.current_onsite > summary.peak_onsite:
            summary.peak_onsite = summary.current_onsite
            summary.peak_time = datetime.utcnow()
        
        self.db.commit()
    
    def get_current_onsite(self) -> int:
        """Get current number of people onsite"""
        return redis_client.get_onsite_count()
    
    def get_active_sessions(self) -> list:
        """Get all currently active sessions"""
        return self.db.query(AttendanceSession)\
            .filter(AttendanceSession.status == SessionStatus.active)\
            .order_by(AttendanceSession.entry_time.desc())\
            .all()
    
    def get_today_summary(self) -> Optional[AttendanceDailySummary]:
        """Get today's attendance summary"""
        today = date.today()
        today_dt = datetime.combine(today, datetime.min.time())
        
        return self.db.query(AttendanceDailySummary)\
            .filter(AttendanceDailySummary.date == today_dt)\
            .first()