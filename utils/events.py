"""
Event System for ZKTeco ADMS Server
Provides event-driven architecture to replace direct service coupling.
Created for Phase 3: Architecture Improvements
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Callable, Awaitable
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

@dataclass
class PhotoUploadedEvent:
    """Event raised when a photo is uploaded"""
    saved_path: str
    photo_filename: str
    device_serial: str
    timestamp: datetime
    user_id: str = None
    
    def __post_init__(self):
        """Extract user_id from filename if not provided"""
        if not self.user_id:
            import re
            match = re.match(r'\d{14}-(\d+)\.jpg', self.photo_filename)
            if match:
                self.user_id = match.group(1)

@dataclass 
class AttendanceRecordedEvent:
    """Event raised when attendance is recorded"""
    user_id: str
    device_serial: str
    timestamp: datetime
    in_out: int
    verify_mode: int
    workcode: str
    db_session: Session

class EventBus:
    """
    Event bus for decoupled communication between services.
    Replaces direct service-to-service calls with event-driven patterns.
    """
    
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
    
    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to an event type"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Subscribed handler to event: {event_type}")
    
    async def publish(self, event_type: str, event_data: Any):
        """Publish an event to all subscribers"""
        if event_type not in self._handlers:
            logger.debug(f"No handlers for event: {event_type}")
            return
        
        logger.debug(f"Publishing event: {event_type}")
        
        for handler in self._handlers[event_type]:
            try:
                if hasattr(handler, '__call__'):
                    # Check if it's an async function
                    if hasattr(handler, '__code__') and handler.__code__.co_flags & 0x0080:
                        await handler(event_data)
                    else:
                        handler(event_data)
                        
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}")
    
    async def publish_photo_uploaded(self, event: PhotoUploadedEvent):
        """Publish photo uploaded event"""
        await self.publish('photo_uploaded', event)
    
    async def publish_attendance_recorded(self, event: AttendanceRecordedEvent):
        """Publish attendance recorded event"""
        await self.publish('attendance_recorded', event)

# Global event bus instance
event_bus = EventBus()