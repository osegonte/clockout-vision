"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Database URL from environment
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://clockout:clockout_secure_pass_2026@postgres:5432/clockout'
)

# Create engine
engine = create_engine(DATABASE_URL, echo=False)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database - create tables"""
    from brain.models.events import Base
    from brain.models.attendance import AttendanceSession, AttendanceDailySummary
    from brain.models.person import Person
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")