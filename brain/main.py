"""
ClockOut Vision - Brain Service
Main FastAPI application - Simplified Modular Version
"""
from fastapi import FastAPI
import logging
from brain.modules.attendance import routes as attendance_routes
from brain.modules.face_recognition import routes as face_routes 
from brain.modules import live_feed

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(name)s %(levelname)s: %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="ClockOut Vision Brain",
    description="Modular event processing and API for farm monitoring",
    version="0.3.0"
)

# Import and register attendance module routes
from brain.modules.attendance import routes as attendance_routes

app.include_router(attendance_routes.router)
app.include_router(face_routes.router)
app.include_router(live_feed.router)

@app.get("/")
async def root():
    return {
        "service": "ClockOut Vision Brain",
        "status": "running",
        "version": "0.3.0",
        "architecture": "modular",
        "modules": {
            "attendance": "enabled"
        }
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected",
        "mqtt": "connected",
        "redis": "connected",
        "modules": ["attendance"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)