"""
Dependency Injection container for ZKTeco ADMS Server
Manages service dependencies and lifecycle.
Created for Phase 3: Architecture Improvements
"""
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from utils.config import config
from services.telegram_service import TelegramNotifier
from .events import event_bus

logger = logging.getLogger(__name__)

@dataclass 
class ServiceContainer:
    """
    Dependency injection container for services.
    Manages service creation, dependencies, and lifecycle.
    """
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._initialized = False
    
    def initialize(self):
        """Initialize all services with their dependencies"""
        if self._initialized:
            return
            
        logger.info("Initializing service container...")
        
        # Initialize core dependencies first
        self._services['telegram_notifier'] = TelegramNotifier()
        self._services['event_bus'] = event_bus
        
        # Initialize services with dependencies
        from services.notification_service import NotificationService
        from services.photo_service import PhotoService
        from services.device_service import DeviceService
        from services.attendance_service import AttendanceService
        from services.background_task_service import BackgroundTaskService
        
        # Create services
        self._services['notification_service'] = NotificationService(
            telegram_notifier=self._services['telegram_notifier']
        )
        self._services['photo_service'] = PhotoService()
        self._services['device_service'] = DeviceService()
        self._services['attendance_service'] = AttendanceService(config.INTERNAL_API_URL)
        self._services['background_task_service'] = BackgroundTaskService(
            notification_service=self._services['notification_service']
        )
        
        # Initialize event handlers
        from services.event_handlers import BackgroundEventHandlers
        self._services['background_event_handlers'] = BackgroundEventHandlers(
            event_bus=self._services['event_bus']
        )
        
        # Setup event subscriptions
        self._setup_event_subscriptions()
        
        self._initialized = True
        logger.info("Service container initialized successfully")
    
    def _setup_event_subscriptions(self):
        """Setup event bus subscriptions between services"""
        logger.info("Setting up event subscriptions...")
        
        # Subscribe NotificationService to photo upload events
        event_bus.subscribe(
            'photo_uploaded', 
            self._services['notification_service'].handle_photo_uploaded_event
        )
        
        logger.info("Event subscriptions setup complete")
    
    def get_service(self, service_name: str) -> Any:
        """Get a service by name"""
        if not self._initialized:
            self.initialize()
        
        if service_name not in self._services:
            raise ValueError(f"Service '{service_name}' not found")
            
        return self._services[service_name]
    
    def get_notification_service(self):
        """Get NotificationService instance"""
        return self.get_service('notification_service')
    
    def get_photo_service(self):
        """Get PhotoService instance"""
        return self.get_service('photo_service')
    
    def get_device_service(self):
        """Get DeviceService instance"""
        return self.get_service('device_service')
    
    def get_attendance_service(self):
        """Get AttendanceService instance"""
        return self.get_service('attendance_service')
    
    def get_background_task_service(self):
        """Get BackgroundTaskService instance"""
        return self.get_service('background_task_service')
    
    def get_background_event_handlers(self):
        """Get BackgroundEventHandlers instance"""
        return self.get_service('background_event_handlers')

# Global service container instance
container = ServiceContainer()