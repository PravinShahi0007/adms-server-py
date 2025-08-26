"""
BackgroundTaskService - Unified background task coordination for ZKTeco ADMS Server
This service manages all background tasks and provides unified coordination.
Created for Phase 2: Eliminate Duplications
"""
import logging
from fastapi import BackgroundTasks
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class BackgroundTaskService:
    """Unified background task coordination service"""
    
    def __init__(self, notification_service):
        self.notification_service = notification_service
        
    def schedule_photo_notification_trigger(
        self, 
        background_tasks: BackgroundTasks,
        saved_path: str, 
        photo_filename: str, 
        device_serial: str
    ):
        """Schedule a background task to trigger pending notifications when photo is uploaded"""
        background_tasks.add_task(
            self.notification_service.trigger_pending_notifications_sync,
            saved_path, 
            photo_filename, 
            device_serial
        )
        logger.debug(f"Scheduled photo notification trigger for {photo_filename}")
    
    def schedule_notification_timeout(
        self,
        background_tasks: BackgroundTasks,
        user_id: str,
        device_serial: str,
        timestamp: datetime,
        in_out: int,
        verify_mode: int
    ):
        """Schedule a timeout handler for pending notifications (10 seconds)"""
        background_tasks.add_task(
            self.notification_service.handle_notification_timeout_sync,
            user_id,
            device_serial, 
            timestamp,
            in_out,
            verify_mode
        )
        logger.debug(f"Scheduled notification timeout for user {user_id}")
    
    def schedule_notification_with_photo(
        self,
        background_tasks: BackgroundTasks,
        user_id: str,
        device_serial: str,
        timestamp: datetime,
        in_out: int,
        verify_mode: int,
        photo_path: str
    ):
        """Schedule sending a notification with photo"""
        background_tasks.add_task(
            self.notification_service.send_notification_with_photo,
            user_id,
            device_serial,
            timestamp, 
            in_out,
            verify_mode,
            photo_path
        )
        logger.debug(f"Scheduled notification with photo for user {user_id}")