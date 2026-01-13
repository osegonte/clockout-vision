"""
MQTT Event Processor - Simplified Modular Version
Subscribes to Frigate events and routes to appropriate modules
"""
import json
import logging
from datetime import datetime
import paho.mqtt.client as mqtt
from sqlalchemy.orm import Session
from brain.models.events import RawEvent, Event
from brain.core.database import SessionLocal

logger = logging.getLogger(__name__)

class EventProcessor:
    def __init__(self, mqtt_host='mqtt', mqtt_port=1883):
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.client = mqtt.Client()
        
        # Set up MQTT callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
    def on_connect(self, client, userdata, flags, rc):
        """Called when connected to MQTT broker"""
        if rc == 0:
            logger.info("Connected to MQTT broker successfully")
            # Subscribe to Frigate events
            client.subscribe("frigate/events")
            logger.info("Subscribed to frigate/events")
        else:
            logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
    
    def on_message(self, client, userdata, msg):
        """Called when message received from MQTT"""
        try:
            # Parse JSON payload
            payload = json.loads(msg.payload.decode())
            
            # Extract event data
            event_type = payload.get('type')  # 'new', 'update', 'end'
            after = payload.get('after', {})
            
            camera_id = after.get('camera')
            label = after.get('label')
            
            if not camera_id or not label:
                return  # Skip incomplete events
            
            logger.info(f"Received event: {event_type} - {camera_id} detected {label}")
            
            # Store in database
            self.store_event(payload, camera_id, label, event_type)
            
        except json.JSONDecodeError:
            logger.error("Failed to decode MQTT message as JSON")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def store_event(self, payload, camera_id, label, event_type):
        """Store event in database and route to modules"""
        db = SessionLocal()
        try:
            # Store raw event
            raw_event = RawEvent(
                timestamp=datetime.utcnow(),
                source='frigate',
                camera_id=camera_id,
                payload=payload
            )
            db.add(raw_event)
            
            # Store normalized event (only for 'new' and 'update' events)
            if event_type in ['new', 'update']:
                after = payload.get('after', {})
                
                event = Event(
                    timestamp=datetime.fromtimestamp(after.get('frame_time', datetime.utcnow().timestamp())),
                    camera_id=camera_id,
                    event_type='detection',
                    object_type=label,
                    confidence=after.get('score', 0),
                    bbox=after.get('box'),
                    area=after.get('area'),
                    frigate_event_id=after.get('id'),
                    snapshot_ref=None,
                    extra_data={
                        'top_score': after.get('top_score'),
                        'zones': after.get('current_zones', []),
                        'stationary': after.get('stationary', False)
                    }
                )
                db.add(event)
            
            db.commit()
            logger.info(f"Stored event in database: {camera_id}/{label}")
            
            # MODULAR ROUTING: Process through attendance module
            if event_type in ['new', 'update'] and label == 'person':
                try:
                    # Get the event we just created
                    from brain.models.events import Event as EventModel
                    latest_event = db.query(EventModel)\
                        .filter(EventModel.camera_id == camera_id)\
                        .order_by(EventModel.id.desc())\
                        .first()
                    
                    if latest_event:
                        # Import and use attendance module
                        from brain.modules.attendance.service import AttendanceModule
                        attendance = AttendanceModule(db)
                        attendance.process_event(latest_event)
                        
                except Exception as e:
                    logger.error(f"Attendance module error: {e}", exc_info=True)
            
        except Exception as e:
            logger.error(f"Database error: {e}")
            db.rollback()
        finally:
            db.close()
    
    def start(self):
        """Start the event processor"""
        logger.info(f"Connecting to MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
        self.client.connect(self.mqtt_host, self.mqtt_port, 60)
        
        # Start the loop (blocking)
        logger.info("Starting MQTT loop...")
        self.client.loop_forever()

if __name__ == "__main__":
    # For testing
    logging.basicConfig(level=logging.INFO)
    processor = EventProcessor()
    processor.start()