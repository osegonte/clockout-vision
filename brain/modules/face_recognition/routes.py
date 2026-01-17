"""
Face Recognition API Routes
"""
import logging
import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException
from sqlalchemy.orm import Session

from brain.core.database import get_db
from brain.modules.face_recognition.service import FaceRecognitionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/face", tags=["face_recognition"])


@router.post("/enroll")
async def enroll_person(
    name: str = Form(...),
    photo: UploadFile = File(...),
    notes: str = Form(None),
    db: Session = Depends(get_db)
):
    """
    Enroll a new person with their face photo.
    
    Args:
        name: Person's name (must be unique)
        photo: Face photo (JPEG/PNG)
        notes: Optional notes about the person
    """
    try:
        # Read image file
        contents = await photo.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        # Convert BGR to RGB (OpenCV uses BGR)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Enroll person
        face_service = FaceRecognitionService(db)
        success, message = face_service.enroll_person(name, image_rgb, notes)
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return {
            "success": True,
            "message": message,
            "name": name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enrollment error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Enrollment failed: {str(e)}")


@router.get("/persons")
def list_persons(db: Session = Depends(get_db)):
    """Get list of all enrolled persons"""
    face_service = FaceRecognitionService(db)
    persons = face_service.get_enrolled_persons()
    
    return {
        "total": len(persons),
        "persons": [p.to_dict() for p in persons]
    }


@router.delete("/persons/{person_id}")
def delete_person(person_id: int, db: Session = Depends(get_db)):
    """Deactivate a person"""
    face_service = FaceRecognitionService(db)
    success, message = face_service.delete_person(person_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=message)
    
    return {
        "success": True,
        "message": message
    }


@router.post("/test-camera")
async def test_camera_recognition(
    photo: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Test face recognition on an uploaded photo.
    Returns identified person or "unknown".
    """
    try:
        # Read image
        contents = await photo.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        # Convert to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Identify
        face_service = FaceRecognitionService(db)
        person = face_service.identify_person(image_rgb)
        
        if person:
            return {
                "identified": True,
                "person": person.to_dict()
            }
        else:
            return {
                "identified": False,
                "message": "No match found or no face detected"
            }
        
    except Exception as e:
        logger.error(f"Test recognition error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
