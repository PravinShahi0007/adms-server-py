"""
DeviceService - Handles device management for ZKTeco ADMS Server

This service manages device registration, heartbeats, and logging.
Extracted from main.py to improve code organization.
"""

import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from models import Device, DeviceLog

logger = logging.getLogger(__name__)


class DeviceService:
    """Service for managing ZKTeco devices"""
    
    def __init__(self):
        pass
    
    def extract_device_serial(self, request) -> Optional[str]:
        """Extract device serial number from request"""
        return request.query_params.get("SN")
    
    def register_device(self, db: Session, serial_number: str, ip_address: str):
        """Register or update device information"""
        device = db.query(Device).filter(Device.serial_number == serial_number).first()
        
        if device:
            device.ip_address = ip_address
            device.last_heartbeat = datetime.now()
            device.is_active = True
            device.updated_at = datetime.now()
        else:
            device = Device(
                serial_number=serial_number,
                ip_address=ip_address,
                last_heartbeat=datetime.now(),
                is_active=True
            )
            db.add(device)
        
        db.commit()
        logger.info(f"Device {serial_number} registered/updated")
    
    def update_device_heartbeat(self, db: Session, serial_number: str, ip_address: str):
        """Update device heartbeat timestamp"""
        device = db.query(Device).filter(Device.serial_number == serial_number).first()
        
        if device:
            device.last_heartbeat = datetime.now()
            device.ip_address = ip_address
            device.is_active = True
            db.commit()
    
    def log_device_event(self, db: Session, device_serial: str, event_type: str, 
                        ip_address: str, message: str):
        """Log device events"""
        try:
            device_log = DeviceLog(
                device_serial=device_serial or "unknown",
                event_type=event_type,
                ip_address=ip_address,
                message=message
            )
            db.add(device_log)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log device event: {e}")