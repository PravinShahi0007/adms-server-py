"""
Event handlers for background task processing
Provides sync wrappers for event handlers that need to run in background tasks.
Created for Phase 3: Architecture Improvements
"""
import asyncio
import logging
from datetime import datetime
from utils.events import PhotoUploadedEvent

logger = logging.getLogger(__name__)

class BackgroundEventHandlers:
    """Sync wrappers for event handlers to be used with FastAPI BackgroundTasks"""
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
    
    def handle_photo_uploaded_sync(self, saved_path: str, photo_filename: str, device_serial: str):
        """Sync wrapper to handle photo uploaded event in background"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            photo_event = PhotoUploadedEvent(
                saved_path=saved_path,
                photo_filename=photo_filename, 
                device_serial=device_serial,
                timestamp=datetime.now()
            )
            loop.run_until_complete(self.event_bus.publish_photo_uploaded(photo_event))
            logger.debug(f"Background task: Published photo uploaded event for {photo_filename}")
        except Exception as e:
            logger.error(f"Background task: Error handling photo uploaded event: {e}")
        finally:
            loop.close()