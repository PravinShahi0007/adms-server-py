import asyncio
import logging
import os
from typing import Optional
from datetime import datetime
import httpx
from sqlalchemy.orm import Session
from models import Employee, AttendanceRecord

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.group_chat_id = os.getenv("TELEGRAM_GROUP_CHAT_ID")
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
    async def send_message(self, chat_id: str, message: str) -> bool:
        """Send text message to Telegram"""
        if not self.bot_token:
            logger.warning("Telegram bot token not configured")
            return False
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "HTML"
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                logger.info(f"Message sent to Telegram chat {chat_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    async def send_photo(self, chat_id: str, photo_path: str, caption: str = "") -> bool:
        """Send photo to Telegram"""
        if not self.bot_token:
            logger.warning("Telegram bot token not configured")
            return False
            
        if not os.path.exists(photo_path):
            logger.error(f"Photo file not found: {photo_path}")
            return False
            
        try:
            async with httpx.AsyncClient() as client:
                with open(photo_path, 'rb') as photo_file:
                    files = {"photo": photo_file}
                    data = {
                        "chat_id": chat_id,
                        "caption": caption,
                        "parse_mode": "HTML"
                    }
                    
                    response = await client.post(
                        f"{self.api_url}/sendPhoto",
                        files=files,
                        data=data,
                        timeout=30.0
                    )
                    response.raise_for_status()
                    logger.info(f"Photo sent to Telegram chat {chat_id}")
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to send Telegram photo: {e}")
            return False
    
    async def send_attendance_notification(
        self, 
        db: Session, 
        user_id: str, 
        device_serial: str,
        timestamp: datetime,
        in_out: int,
        verify_mode: int,
        photo_path: Optional[str] = None
    ):
        """Send attendance notification with employee details"""
        
        # Get employee information
        employee = db.query(Employee).filter(Employee.user_id == user_id).first()
        
        if not employee:
            employee_name = f"Unknown ({user_id})"
            department = "Unknown"
        else:
            employee_name = employee.name
            department = employee.department or "Unknown"
        
        # Determine attendance type based on scan history for the day
        attendance_type = self.determine_attendance_type(db, user_id, device_serial, timestamp)
        
        # Format verify method
        verify_methods = {
            0: "ลายนิ้วมือ",
            1: "รหัสผ่าน", 
            2: "ใบหน้า",
            3: "บัตร",
            4: "รหัสผ่าน + ลายนิ้วมือ"
        }
        verify_method = verify_methods.get(verify_mode, f"อื่นๆ ({verify_mode})")
        
        # Format timestamp
        time_str = timestamp.strftime("%d/%m/%Y %H:%M:%S")
        
        # Create notification message
        message = f"""
🏢 <b>แจ้งเตือนการลงเวลา</b>

👤 <b>ชื่อ:</b> {employee_name}
🏷️ <b>รหัส:</b> {user_id}
🏢 <b>แผนก:</b> {department}

{attendance_type}
🕐 <b>เวลา:</b> {time_str}
🔐 <b>วิธีสแกน:</b> {verify_method}
📱 <b>เครื่อง:</b> {device_serial}
        """.strip()
        
        if not self.group_chat_id:
            logger.warning("Telegram group chat ID not configured")
            return False
        
        # Send notification to group
        success = False
        if photo_path and os.path.exists(photo_path):
            # Send with photo
            success = await self.send_photo(self.group_chat_id, photo_path, message)
        else:
            # Send text only
            success = await self.send_message(self.group_chat_id, message)
        
        # Also send to personal chat if configured
        if employee and employee.telegram_chat_id:
            personal_message = f"""
👋 <b>สวัสดี {employee.name}</b>

{attendance_type} เรียบร้อยแล้ว
🕐 <b>เวลา:</b> {time_str}
🔐 <b>วิธีสแกน:</b> {verify_method}
            """.strip()
            
            if photo_path and os.path.exists(photo_path):
                await self.send_photo(employee.telegram_chat_id, photo_path, personal_message)
            else:
                await self.send_message(employee.telegram_chat_id, personal_message)
        
        return success

    def determine_attendance_type(self, db: Session, user_id: str, device_serial: str, timestamp: datetime) -> str:
        """Determine if this is check-in or check-out based on scan history for the day"""
        from datetime import date
        
        # Get today's date from the timestamp
        scan_date = timestamp.date()
        
        # Count existing scans for this user on this date (before current timestamp)
        existing_scans = db.query(AttendanceRecord).filter(
            AttendanceRecord.user_id == user_id,
            AttendanceRecord.device_serial == device_serial,
            AttendanceRecord.timestamp >= datetime.combine(scan_date, datetime.min.time()),
            AttendanceRecord.timestamp < timestamp  # Before current scan
        ).count()
        
        # Simple logic: Even count = เข้างาน (0, 2, 4...), Odd count = ออกงาน (1, 3, 5...)
        if existing_scans % 2 == 0:
            return "🟢 เข้างาน"
        else:
            return "🔴 ออกงาน"

# Helper function to get employee by user_id
def get_employee_by_user_id(db: Session, user_id: str) -> Optional[Employee]:
    """Get employee information by user_id"""
    return db.query(Employee).filter(Employee.user_id == user_id, Employee.is_active == True).first()

# Helper function to create or update employee
def upsert_employee(db: Session, user_id: str, name: str, **kwargs) -> Employee:
    """Create or update employee record"""
    employee = db.query(Employee).filter(Employee.user_id == user_id).first()
    
    if employee:
        # Update existing
        employee.name = name
        employee.updated_at = datetime.utcnow()
        for key, value in kwargs.items():
            if hasattr(employee, key):
                setattr(employee, key, value)
    else:
        # Create new
        employee = Employee(
            user_id=user_id,
            name=name,
            **kwargs
        )
        db.add(employee)
    
    db.commit()
    return employee