from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class Device(Base):
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, index=True)
    serial_number = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(200))
    ip_address = Column(String(45))
    model = Column(String(100))
    firmware_version = Column(String(50))
    last_heartbeat = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_device_serial_active', 'serial_number', 'is_active'),
    )

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    
    id = Column(Integer, primary_key=True, index=True)
    device_serial = Column(String(100), nullable=False, index=True)
    user_id = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    verify_mode = Column(Integer, nullable=False)  # 0=password, 1=fingerprint, 2=face, etc.
    in_out = Column(Integer, nullable=False)       # 0=in, 1=out, 2=break_out, 3=break_in, etc.
    workcode = Column(String(10), default='0')
    raw_data = Column(Text)
    processed = Column(Boolean, default=False, index=True)
    processed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_attendance_user_time', 'user_id', 'timestamp'),
        Index('idx_attendance_device_time', 'device_serial', 'timestamp'),
        Index('idx_attendance_processed', 'processed', 'created_at'),
    )

class DeviceLog(Base):
    __tablename__ = "device_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    device_serial = Column(String(100), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # heartbeat, register, data_upload, error
    ip_address = Column(String(45))
    message = Column(Text)
    request_data = Column(Text)
    response_data = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_device_log_type_time', 'event_type', 'created_at'),
        Index('idx_device_log_serial_time', 'device_serial', 'created_at'),
    )

class ProcessingQueue(Base):
    __tablename__ = "processing_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    attendance_record_id = Column(Integer, nullable=False, index=True)
    status = Column(String(20), default='pending', index=True)  # pending, processing, completed, failed
    retry_count = Column(Integer, default=0)
    last_error = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
    
    __table_args__ = (
        Index('idx_queue_status_created', 'status', 'created_at'),
    )

class Employee(Base):
    __tablename__ = "employees"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), unique=True, index=True, nullable=False)  # Employee ID from ZKTeco
    name = Column(String(200), nullable=False)
    department = Column(String(100))
    position = Column(String(100))
    phone = Column(String(20))
    email = Column(String(100))
    telegram_chat_id = Column(String(50))  # For personal notifications
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_employee_user_id', 'user_id', 'is_active'),
    )