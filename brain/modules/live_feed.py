"""
Live Camera Feed with Face Recognition
"""
import logging
import cv2
import numpy as np
from fastapi import APIRouter, Response, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session
import time

from brain.core.database import get_db
from brain.modules.face_recognition.service import FaceRecognitionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live", tags=["live_feed"])


@router.get("/", response_class=HTMLResponse)
async def live_feed_page():
    """
    HTML page with live camera feed showing face recognition
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ClockOut Vision - Live Feed</title>
        <style>
            body {
                margin: 0;
                padding: 20px;
                background: #1a1a1a;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                color: #fff;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            h1 {
                text-align: center;
                color: #4CAF50;
                margin-bottom: 10px;
            }
            .info {
                text-align: center;
                color: #888;
                margin-bottom: 20px;
            }
            .video-container {
                position: relative;
                width: 100%;
                max-width: 800px;
                margin: 0 auto;
                background: #000;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            }
            img {
                width: 100%;
                height: auto;
                display: block;
            }
            .status {
                text-align: center;
                margin-top: 20px;
                padding: 15px;
                background: #2a2a2a;
                border-radius: 5px;
            }
            .status-online {
                color: #4CAF50;
            }
            .status-offline {
                color: #f44336;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎥 ClockOut Vision - Live Feed</h1>
            <div class="info">Real-time face recognition monitoring</div>
            
            <div class="video-container">
                <img id="video-feed" src="/live/stream" alt="Loading camera feed...">
            </div>
            
            <div class="status">
                <span id="status" class="status-online">● LIVE</span>
                <span id="fps" style="margin-left: 20px; color: #888;">FPS: --</span>
            </div>
        </div>
        
        <script>
            const img = document.getElementById('video-feed');
            const status = document.getElementById('status');
            const fpsDisplay = document.getElementById('fps');
            
            let frameCount = 0;
            let lastTime = Date.now();
            
            // Update FPS counter
            img.onload = function() {
                frameCount++;
                const now = Date.now();
                if (now - lastTime >= 1000) {
                    const fps = Math.round(frameCount / ((now - lastTime) / 1000));
                    fpsDisplay.textContent = `FPS: ${fps}`;
                    frameCount = 0;
                    lastTime = now;
                }
                status.className = 'status-online';
                status.textContent = '● LIVE';
            };
            
            img.onerror = function() {
                status.className = 'status-offline';
                status.textContent = '● OFFLINE';
                // Retry after 2 seconds
                setTimeout(() => {
                    img.src = '/live/stream?' + new Date().getTime();
                }, 2000);
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


def generate_frames(db: Session):
    """
    Generate video frames with face recognition overlays
    """
    face_service = FaceRecognitionService(db)
    
    # Open webcam
    camera = cv2.VideoCapture(0)
    
    if not camera.isOpened():
        logger.error("Cannot open camera")
        return
    
    # Set resolution
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    logger.info("Live feed started")
    
    frame_skip = 2  # Process every Nth frame for performance
    frame_count = 0
    
    try:
        while True:
            success, frame = camera.read()
            if not success:
                logger.warning("Failed to read frame")
                break
            
            frame_count += 1
            
            # Only process face recognition every N frames
            if frame_count % frame_skip == 0:
                # Convert BGR to RGB for face_recognition
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Detect faces
                import face_recognition
                face_locations = face_recognition.face_locations(rgb_frame)
                
                # Draw boxes and try to identify
                for (top, right, bottom, left) in face_locations:
                    # Identify person
                    person = face_service.identify_person(rgb_frame)
                    
                    if person:
                        # Recognized - Green box
                        color = (0, 255, 0)
                        label = f"{person.name} - Recognized"
                    else:
                        # Unknown - Yellow box
                        color = (0, 255, 255)
                        label = "Unknown Person"
                    
                    # Draw rectangle
                    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                    
                    # Draw label background
                    cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
                    
                    # Draw label text
                    cv2.putText(frame, label, (left + 6, bottom - 10),
                               cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 0, 0), 1)
            
            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            
            # Convert to bytes
            frame_bytes = buffer.tobytes()
            
            # Yield frame in multipart format
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            # Small delay to control frame rate
            time.sleep(0.033)  # ~30 FPS
    
    except Exception as e:
        logger.error(f"Error in video stream: {e}", exc_info=True)
    finally:
        camera.release()
        logger.info("Live feed stopped")


@router.get("/stream")
async def video_stream(db: Session = Depends(get_db)):
    """
    Stream video frames with face recognition
    """
    return StreamingResponse(
        generate_frames(db),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )