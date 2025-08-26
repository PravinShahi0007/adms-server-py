"""
NotificationService - Handles all notification logic for ZKTeco ADMS Server

This service manages pending notifications, event-driven triggers, and timeout handling.
Extracted from main.py to improve code organization.
"""

import asyncio
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from database import SessionLocal
from telegram_notify import TelegramNotifier

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing attendance notifications and photo matching"""
    
    def __init__(self):
        self.telegram_notifier = TelegramNotifier()
        # Global in-memory store for pending notifications
        # Key: user_id, Value: attendance data waiting for photo
        self.pending_notifications: Dict[str, Dict[str, Any]] = {}
        self.pending_notifications_lock = threading.Lock()
    
    def cleanup_expired_pending_notifications(self) -> int:
        """Remove pending notifications older than 5 minutes"""
        current_time = datetime.now()
        expired_keys = []
        
        with self.pending_notifications_lock:
            for user_id, data in self.pending_notifications.items():
                if current_time - data['created_at'] > timedelta(minutes=5):
                    expired_keys.append(user_id)
            
            for key in expired_keys:
                del self.pending_notifications[key]
                logger.info(f"Cleaned up expired pending notification for user {key}")
        
        return len(expired_keys)
    
    async def trigger_pending_notifications(self, saved_path: str, photo_filename: str, device_serial: str, db: Session):
        """Event-driven trigger when a photo is uploaded - check for pending notifications"""
        import re
        
        try:
            # Extract user_id from photo filename: YYYYMMDDHHMISS-{user_id}.jpg
            match = re.match(r'\d{14}-(\d+)\.jpg', photo_filename)
            if not match:
                logger.debug(f"Could not extract user_id from photo filename: {photo_filename}")
                return
                
            user_id = match.group(1)
            logger.info(f"Photo uploaded for user {user_id}, checking pending notifications...")
            
            # Debug: Show current pending notifications
            logger.info(f"Current pending notifications: {list(self.pending_notifications.keys())}")
            logger.info(f"Looking for user_id: '{user_id}' (type: {type(user_id)})")
            
            # Check if this user has a pending notification
            if user_id in self.pending_notifications:
                pending_data = self.pending_notifications[user_id]
                logger.info(f"Found pending notification for user {user_id}, triggering immediate notification")
                
                # Send notification immediately with the new photo
                await self.telegram_notifier.send_attendance_notification(
                    db=pending_data['db'],
                    user_id=user_id,
                    device_serial=device_serial,
                    timestamp=pending_data['attendance_time'],
                    in_out=pending_data['in_out'],
                    verify_mode=pending_data['verify_mode'],
                    photo_path=saved_path
                )
                
                # Remove from pending notifications
                del self.pending_notifications[user_id]
                logger.info(f"Removed user {user_id} from pending notifications")
            else:
                logger.info(f"No pending notification found for user {user_id}")
                logger.info(f"Available pending users: {list(self.pending_notifications.keys())}")
                
        except Exception as e:
            logger.error(f"Error in trigger_pending_notifications: {e}")
    
    def trigger_pending_notifications_sync(self, saved_path: str, photo_filename: str, device_serial: str):
        """Event-driven trigger when a photo is uploaded - check for pending notifications (sync version for BackgroundTasks)"""
        import re
        import time
        
        try:
            # Small delay to ensure attendance records are processed first in rapid-fire scenarios
            time.sleep(0.1)
            # Extract user_id from photo filename: YYYYMMDDHHMISS-{user_id}.jpg
            match = re.match(r'\d{14}-(\d+)\.jpg', photo_filename)
            if not match:
                logger.debug(f"Could not extract user_id from photo filename: {photo_filename}")
                return
                
            user_id = match.group(1)
            logger.info(f"Background task: Photo uploaded for user {user_id}, checking pending notifications...")
            
            # Debug: Show current pending notifications
            logger.info(f"Current pending notifications: {list(self.pending_notifications.keys())}")
            logger.info(f"Looking for user_id: '{user_id}' (type: {type(user_id)})")
            
            # Check if this user has a pending notification (thread-safe)
            with self.pending_notifications_lock:
                if user_id in self.pending_notifications:
                    pending_data = self.pending_notifications[user_id].copy()  # Copy data before releasing lock
                    # Remove from pending notifications immediately
                    del self.pending_notifications[user_id]
                    found_pending = True
                else:
                    found_pending = False
            
            if found_pending:
                logger.info(f"Found pending notification for user {user_id}, triggering immediate notification")
                
                # Create new event loop for background task
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Send notification immediately with the new photo
                loop.run_until_complete(self.telegram_notifier.send_attendance_notification(
                    db=SessionLocal(),  # Create new session for background task
                    user_id=user_id,
                    device_serial=device_serial,
                    timestamp=pending_data['attendance_time'],
                    in_out=pending_data['in_out'],
                    verify_mode=pending_data['verify_mode'],
                    photo_path=saved_path
                ))
                
                loop.close()
                logger.info(f"Background task: Removed user {user_id} from pending notifications")
            else:
                logger.info(f"Background task: No pending notification found for user {user_id}")
                logger.info(f"Available pending users: {list(self.pending_notifications.keys())}")
                
        except Exception as e:
            logger.error(f"Background task: Error in trigger_pending_notifications_sync: {e}")
    
    def send_notification_with_photo(
        self,
        db: Session,
        user_id: str,
        device_serial: str, 
        timestamp: datetime,
        in_out: int,
        verify_mode: int,
        photo_path: str
    ):
        """Send notification with photo (sync function for BackgroundTasks)"""
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            loop.run_until_complete(self.telegram_notifier.send_attendance_notification(
                db=db,
                user_id=user_id,
                device_serial=device_serial,
                timestamp=timestamp,
                in_out=in_out,
                verify_mode=verify_mode,
                photo_path=photo_path
            ))
            
            loop.close()
            logger.info(f"Background task: Sent notification with photo for user {user_id}")
            
        except Exception as e:
            logger.error(f"Background task: Failed to send notification for user {user_id}: {e}")
    
    def handle_notification_timeout_sync(
        self,
        user_id: str,
        device_serial: str,
        timestamp: datetime,
        in_out: int,
        verify_mode: int
    ):
        """Handle 10-second timeout for pending notifications (sync function for BackgroundTasks)"""
        import time
        
        try:
            # Wait 10 seconds for photo to arrive
            time.sleep(10)
            
            # Check if still pending (photo might have arrived and removed it) - thread-safe
            with self.pending_notifications_lock:
                if user_id in self.pending_notifications:
                    # Remove from pending before processing
                    del self.pending_notifications[user_id]
                    should_send_notification = True
                else:
                    should_send_notification = False
                    
            if should_send_notification:
                logger.info(f"No photo arrived for {user_id} after 10 seconds, sending text-only notification")
                
                # Create new event loop for this background task
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Send text-only notification
                loop.run_until_complete(self.telegram_notifier.send_attendance_notification(
                    db=SessionLocal(),  # Create new session for background task
                    user_id=user_id,
                    device_serial=device_serial,
                    timestamp=timestamp,
                    in_out=in_out,
                    verify_mode=verify_mode,
                    photo_path=None
                ))
                
                loop.close()
                logger.info(f"Background task: Sent timeout notification for user {user_id}")
            else:
                logger.info(f"Background task: Notification for {user_id} already sent via event trigger")
                
        except Exception as e:
            logger.error(f"Background task: Failed timeout handling for user {user_id}: {e}")
    
    async def handle_notification_timeout(
        self,
        user_id: str,
        telegram_notifier,
        db: Session,
        device_serial: str,
        timestamp: datetime,
        in_out: int,
        verify_mode: int
    ):
        """Handle 60-second timeout for pending notifications (legacy async version)"""
        # Wait 60 seconds
        await asyncio.sleep(60)
        
        # Check if still pending (photo might have arrived and removed it)
        if user_id in self.pending_notifications:
            logger.info(f"No photo arrived for {user_id} after 60 seconds, sending text-only notification")
            # Remove from pending
            del self.pending_notifications[user_id]
            
            # Send text-only notification
            await telegram_notifier.send_attendance_notification(
                db=db,
                user_id=user_id,
                device_serial=device_serial,
                timestamp=timestamp,
                in_out=in_out,
                verify_mode=verify_mode,
                photo_path=None
            )
        else:
            logger.info(f"Notification for {user_id} already sent via event trigger")
    
    def add_pending_notification(
        self,
        user_id: str,
        attendance_time: datetime,
        device_serial: str,
        timestamp_str: str,
        in_out: int,
        verify_mode: int,
        db: Session
    ):
        """Add a notification to pending queue"""
        with self.pending_notifications_lock:
            self.pending_notifications[user_id] = {
                'attendance_time': attendance_time,
                'device_serial': device_serial,
                'timestamp_str': timestamp_str,
                'in_out': in_out,
                'verify_mode': verify_mode,
                'db': db,
                'created_at': datetime.now()
            }
        logger.info(f"Added pending notification for user {user_id}")