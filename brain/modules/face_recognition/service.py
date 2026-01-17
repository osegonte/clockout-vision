"""
Face Recognition Service - Lightweight face identification
Uses face_recognition library for encoding and matching
"""
import logging
import numpy as np
import face_recognition
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from brain.models.person import Person

logger = logging.getLogger(__name__)


class FaceRecognitionService:
    """
    Lightweight face recognition for worker identification.
    
    Strategy:
    - Generate 128D face encoding (512 bytes)
    - Store in database
    - Compare new faces against known faces
    - Fast matching using euclidean distance
    """
    
    def __init__(self, db: Session, tolerance: float = 0.6):
        """
        Initialize face recognition service.
        
        Args:
            db: Database session
            tolerance: Match threshold (lower = stricter, default 0.6)
        """
        self.db = db
        self.tolerance = tolerance
        self._known_faces_cache = None
    
    def enroll_person(self, name: str, image_array: np.ndarray, notes: str = None) -> Tuple[bool, str]:
        """
        Enroll a new person by extracting their face encoding.
        
        Args:
            name: Person's name (must be unique)
            image_array: RGB image as numpy array
            notes: Optional notes about the person
            
        Returns:
            (success, message) tuple
        """
        try:
            # Check if person already exists
            existing = self.db.query(Person).filter(Person.name == name).first()
            if existing:
                return False, f"Person '{name}' already enrolled"
            
            # Detect faces in image
            face_locations = face_recognition.face_locations(image_array)
            
            if len(face_locations) == 0:
                return False, "No face detected in image"
            
            if len(face_locations) > 1:
                return False, f"Multiple faces detected ({len(face_locations)}). Please use image with single face"
            
            # Generate face encoding
            face_encodings = face_recognition.face_encodings(image_array, face_locations)
            
            if len(face_encodings) == 0:
                return False, "Could not generate face encoding"
            
            encoding = face_encodings[0]
            
            # Convert to bytes for storage
            encoding_bytes = encoding.tobytes()
            
            # Create person record
            person = Person(
                name=name,
                face_encoding=encoding_bytes,
                notes=notes,
                is_active=True
            )
            
            self.db.add(person)
            self.db.commit()
            
            logger.info(f"✅ Enrolled person: {name} (ID: {person.id})")
            
            # Invalidate cache
            self._known_faces_cache = None
            
            return True, f"Successfully enrolled {name}"
            
        except Exception as e:
            logger.error(f"Failed to enroll person: {e}", exc_info=True)
            self.db.rollback()
            return False, f"Enrollment failed: {str(e)}"
    
    def identify_person(self, image_array: np.ndarray) -> Optional[Person]:
        """
        Identify a person from an image.
        
        Args:
            image_array: RGB image as numpy array
            
        Returns:
            Person object if identified, None if unknown
        """
        try:
            # Detect faces
            face_locations = face_recognition.face_locations(image_array)
            
            if len(face_locations) == 0:
                logger.debug("No face detected")
                return None
            
            # Use first face if multiple detected
            if len(face_locations) > 1:
                logger.warning(f"Multiple faces detected ({len(face_locations)}), using first one")
            
            # Generate encoding for detected face
            face_encodings = face_recognition.face_encodings(image_array, [face_locations[0]])
            
            if len(face_encodings) == 0:
                logger.debug("Could not generate encoding")
                return None
            
            unknown_encoding = face_encodings[0]
            
            # Load known faces (with caching)
            known_faces = self._get_known_faces()
            
            if not known_faces:
                logger.debug("No enrolled persons in database")
                return None
            
            # Compare against all known faces
            for person_id, known_encoding in known_faces:
                distance = np.linalg.norm(unknown_encoding - known_encoding)
                
                if distance <= self.tolerance:
                    # Match found!
                    person = self.db.query(Person).filter(Person.id == person_id).first()
                    if person and person.is_active:
                        logger.info(f"✅ Identified: {person.name} (distance: {distance:.3f})")
                        return person
            
            logger.debug(f"Face detected but no match found (checked {len(known_faces)} known faces)")
            return None
            
        except Exception as e:
            logger.error(f"Face identification error: {e}", exc_info=True)
            return None
    
    def _get_known_faces(self) -> list:
        """
        Get all known face encodings from database (with caching).
        
        Returns:
            List of (person_id, encoding_array) tuples
        """
        # Use cache if available
        if self._known_faces_cache is not None:
            return self._known_faces_cache
        
        known_faces = []
        
        persons = self.db.query(Person)\
            .filter(Person.is_active == True)\
            .filter(Person.face_encoding.isnot(None))\
            .all()
        
        for person in persons:
            # Convert bytes back to numpy array
            encoding = np.frombuffer(person.face_encoding, dtype=np.float64)
            known_faces.append((person.id, encoding))
        
        # Cache for future calls
        self._known_faces_cache = known_faces
        
        logger.debug(f"Loaded {len(known_faces)} known faces")
        return known_faces
    
    def invalidate_cache(self):
        """Invalidate the known faces cache (call after enrolling new person)"""
        self._known_faces_cache = None
    
    def get_enrolled_persons(self) -> list:
        """Get list of all enrolled persons"""
        return self.db.query(Person)\
            .filter(Person.is_active == True)\
            .all()
    
    def delete_person(self, person_id: int) -> Tuple[bool, str]:
        """
        Delete a person (soft delete - sets is_active=False).
        
        Args:
            person_id: ID of person to delete
            
        Returns:
            (success, message) tuple
        """
        try:
            person = self.db.query(Person).filter(Person.id == person_id).first()
            
            if not person:
                return False, f"Person with ID {person_id} not found"
            
            person.is_active = False
            self.db.commit()
            
            # Invalidate cache
            self._known_faces_cache = None
            
            logger.info(f"Deactivated person: {person.name} (ID: {person_id})")
            return True, f"Deactivated {person.name}"
            
        except Exception as e:
            logger.error(f"Failed to delete person: {e}", exc_info=True)
            self.db.rollback()
            return False, f"Delete failed: {str(e)}"
