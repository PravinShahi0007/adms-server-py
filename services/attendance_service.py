"""
AttendanceService - Handles attendance data processing for ZKTeco ADMS Server

This service manages parsing, saving, and forwarding attendance records.
Extracted from main.py to improve code organization.
"""

import httpx
import logging
from datetime import datetime
from typing import List, Dict, Any
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from models import AttendanceRecord

logger = logging.getLogger(__name__)


class AttendanceService:
    """Service for managing attendance data processing"""
    
    def __init__(self, internal_api_url: str):
        self.internal_api_url = internal_api_url
    
    def parse_attlog_data(self, data_text: str) -> List[Dict[str, Any]]:
        """
        Parse ATTLOG data format:
        Two formats supported:
        1. ATTLOG\tuser_id\ttimestamp\tverify_mode\tin_out\tworkcode
        2. user_id\ttimestamp\tverify_mode\tin_out\tworkcode\t... (direct format)
        """
        records = []
        
        for line in data_text.strip().split('\n'):
            if not line.strip():
                continue
                
            try:
                parts = line.split('\t')
                
                # Check if line starts with ATTLOG
                if line.startswith('ATTLOG') and len(parts) >= 6:
                    record = {
                        'user_id': parts[1],
                        'timestamp': parts[2], 
                        'verify_mode': int(parts[3]),
                        'in_out': int(parts[4]),
                        'workcode': parts[5] if parts[5] else '0'
                    }
                    records.append(record)
                    logger.debug(f"Parsed ATTLOG record: {record}")
                    
                # Handle direct format: user_id\ttimestamp\tverify_mode\tin_out\tworkcode\t...
                elif len(parts) >= 5 and not line.startswith('ATTLOG'):
                    record = {
                        'user_id': parts[0],
                        'timestamp': parts[1], 
                        'verify_mode': int(parts[2]),
                        'in_out': int(parts[3]),
                        'workcode': parts[4] if parts[4] else '0'
                    }
                    records.append(record)
                    logger.debug(f"Parsed direct record: {record}")
                    
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse line: {line}, error: {e}")
                
        return records
    
    async def save_attendance_records(
        self, 
        db: Session, 
        records: List[Dict[str, Any]], 
        device_serial: str, 
        raw_data: str, 
        background_tasks: BackgroundTasks,
        photo_service,
        notification_service
    ) -> int:
        """Save attendance records to database and send Telegram notifications"""
        saved_count = 0
        
        for record in records:
            try:
                # Check for duplicate record
                existing = db.query(AttendanceRecord).filter(
                    AttendanceRecord.device_serial == device_serial,
                    AttendanceRecord.user_id == record['user_id'],
                    AttendanceRecord.timestamp == datetime.fromisoformat(record['timestamp'].replace(' ', 'T'))
                ).first()
                
                if not existing:
                    attendance_record = AttendanceRecord(
                        device_serial=device_serial,
                        user_id=record['user_id'],
                        timestamp=datetime.fromisoformat(record['timestamp'].replace(' ', 'T')),
                        verify_mode=record['verify_mode'],
                        in_out=record['in_out'],
                        workcode=record['workcode'],
                        raw_data=raw_data
                    )
                    db.add(attendance_record)
                    saved_count += 1
                    
                    # Send Telegram notification using BackgroundTasks (non-blocking)
                    try:
                        # Quick check for immediate photo
                        photo_path = photo_service.find_latest_photo(device_serial, record['user_id'], record['timestamp'])
                        
                        if photo_path:
                            # Photo exists - send immediately via background task
                            background_tasks.add_task(
                                notification_service.send_notification_with_photo,
                                db, record['user_id'], device_serial,
                                datetime.fromisoformat(record['timestamp'].replace(' ', 'T')),
                                record['in_out'], record['verify_mode'], photo_path
                            )
                            logger.info(f"Queued immediate notification with photo for user {record['user_id']}")
                        else:
                            # No photo - store in pending notifications for event-driven trigger
                            logger.info(f"No photo found for {record['user_id']}, adding to pending notifications...")
                            
                            notification_service.add_pending_notification(
                                record['user_id'],
                                datetime.fromisoformat(record['timestamp'].replace(' ', 'T')),
                                device_serial,
                                record['timestamp'],
                                record['in_out'],
                                record['verify_mode'],
                                db
                            )
                            
                            # Queue timeout handler as background task
                            background_tasks.add_task(
                                notification_service.handle_notification_timeout_sync,
                                record['user_id'], device_serial,
                                datetime.fromisoformat(record['timestamp'].replace(' ', 'T')),
                                record['in_out'], record['verify_mode']
                            )
                            
                    except Exception as e:
                        logger.error(f"Failed to process notification for user {record['user_id']}: {e}")
                        
            except Exception as e:
                logger.error(f"Failed to save attendance record: {e}")
        
        db.commit()
        return saved_count
    
    async def forward_to_internal_api(self, records: List[Dict[str, Any]]):
        """Forward parsed attendance records to internal API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.internal_api_url}/api/attendance/bulk",
                    json={
                        "records": records,
                        "timestamp": datetime.now().isoformat(),
                        "source": "zkteco_push"
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                logger.info(f"Successfully forwarded {len(records)} records to internal API")
        except Exception as e:
            logger.error(f"Failed to forward to internal API: {e}")
            # Don't raise - we still want to return OK to the device