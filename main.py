from fastapi import FastAPI, Request, Response, Depends
from fastapi.responses import PlainTextResponse
import httpx
import logging
from datetime import datetime
from typing import Optional
import os
from sqlalchemy.orm import Session
from database import get_db, create_tables
from models import Device, AttendanceRecord, DeviceLog, Employee
from telegram_notify import TelegramNotifier
from starlette.middleware.base import BaseHTTPMiddleware
import traceback
from contextlib import asynccontextmanager

# Lifespan event handler for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    import time
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            create_tables()
            break
        except Exception as e:
            retry_count += 1
            logger.warning(f"Database connection failed (attempt {retry_count}/{max_retries}): {e}")
            if retry_count >= max_retries:
                logger.error("Failed to connect to database after maximum retries")
                raise
            time.sleep(2)
    
    if COMM_KEY:
        logger.info("COMM_KEY authentication enabled")
    else:
        logger.info("No COMM_KEY - authentication disabled")
    logger.info("Database tables created successfully")
    
    yield
    
    # Shutdown (if needed)
    logger.info("ZKTeco ADMS Push Server shutting down")

app = FastAPI(title="ZKTeco ADMS Push Server", version="1.0.0", lifespan=lifespan)

# Initialize Telegram notifier
telegram_notifier = TelegramNotifier()

# Request logging middleware
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()
        client_ip = request.client.host if request.client else "unknown"
        
        try:
            # Log all incoming requests
            method = request.method
            url = str(request.url)
            headers = dict(request.headers)
            
            # Read request body for detailed logging
            body = b""
            if request.method in ["POST", "PUT", "PATCH"]:
                try:
                    body = await request.body()
                    # Recreate request with body for downstream processing
                    async def receive():
                        return {"type": "http.request", "body": body}
                    request._receive = receive
                except Exception as e:
                    logger.warning(f"[{client_ip}] Could not read request body: {e}")
            
            # Enhanced logging for all requests
            logger.info(f"[{client_ip}] {method} {url}")
            logger.info(f"[{client_ip}] Headers: {headers}")
            
            if body:
                # Log body content safely
                try:
                    body_text = body.decode('utf-8', errors='replace')
                    logger.info(f"[{client_ip}] Body ({len(body)} bytes): {repr(body_text[:500])}")
                except Exception:
                    logger.info(f"[{client_ip}] Body ({len(body)} bytes): [binary data]")
            
            # Process request
            response = await call_next(request)
            
            # Log response
            duration = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"[{client_ip}] {method} {url} -> {response.status_code} ({duration:.2f}ms)")
            
            return response
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"[{client_ip}] {method} {url} -> ERROR ({duration:.2f}ms): {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

# Add the middleware
app.add_middleware(RequestLoggingMiddleware)

log_level = os.getenv("LOG_LEVEL", "INFO")

# Enhanced logging configuration
logging.basicConfig(
    level=getattr(logging, log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Set uvicorn logger to show more details
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.setLevel(logging.DEBUG)

# Log invalid HTTP requests from uvicorn
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.setLevel(logging.INFO)

INTERNAL_API_URL = os.getenv("INTERNAL_API_URL", "http://localhost:3000")
COMM_KEY = os.getenv("COMM_KEY", "")

def validate_comm_key(request: Request) -> bool:
    """Validate communication key if configured"""
    if not COMM_KEY:  # No key required
        return True
    
    # Check key in query parameters or headers
    request_key = request.query_params.get("key") or request.headers.get("X-Comm-Key")
    return request_key == COMM_KEY


@app.get("/iclock/getrequest")
async def get_request(request: Request, SN: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Handle device heartbeat and command requests
    Device periodically calls this to check for pending commands
    """
    logger.info(f"Device heartbeat from SN: {SN}")
    client_ip = request.client.host
    
    # Log device activity
    log_device_event(db, SN, "heartbeat", client_ip, f"Heartbeat from {SN}")
    
    # Update device last seen
    if SN:
        update_device_heartbeat(db, SN, client_ip)
    
    return PlainTextResponse("OK")

@app.post("/iclock/cdata")
async def cdata(request: Request, SN: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Handle attendance data upload from device
    Receives ATTLOG records in plain text format
    """
    raw_data = await request.body()
    data_text = raw_data.decode('utf-8')
    client_ip = request.client.host
    
    logger.info(f"Received attendance data: {len(data_text)} bytes from {client_ip}")
    logger.debug(f"Raw data: {data_text}")
    
    device_serial = SN or extract_device_serial(request)
    
    try:
        # Parse and save attendance records
        records = parse_attlog_data(data_text)
        logger.info(f"Parsed {len(records)} attendance records")
        
        if records:
            saved_count = await save_attendance_records(db, records, device_serial, data_text)
            logger.info(f"Saved {saved_count} new attendance records")
            
            # Log successful data upload
            log_device_event(db, device_serial, "data_upload", client_ip, 
                           f"Uploaded {len(records)} records")
            
            # Forward to internal API
            await forward_to_internal_api(records)
            
    except Exception as e:
        logger.error(f"Error processing attendance data: {e}")
        log_device_event(db, device_serial, "error", client_ip, str(e))
    
    return PlainTextResponse("OK")

@app.post("/iclock/fdata")
async def fdata(request: Request, SN: Optional[str] = None, table: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Handle file data upload from device (photos, etc.)
    Device calls this to upload photos and other file data
    """
    raw_data = await request.body()
    client_ip = request.client.host
    
    logger.info(f"Received file data: {len(raw_data)} bytes from {client_ip}, table={table}, SN={SN}")
    
    device_serial = SN or extract_device_serial(request)
    
    try:
        if table == "ATTPHOTO":
            # Parse photo upload data
            data_text = raw_data.decode('utf-8', errors='replace')
            lines = data_text.split('\n')
            
            photo_info = {}
            for line in lines[:4]:  # First few lines contain metadata
                if '=' in line:
                    key, value = line.split('=', 1)
                    photo_info[key] = value
            
            photo_filename = photo_info.get('PIN', 'unknown')
            logger.info(f"Photo upload from {device_serial}: {photo_filename}")
            
            # Save photo to NAS storage
            saved_path = await save_photo_file(raw_data, device_serial, photo_filename, photo_info)
            
            if saved_path:
                logger.info(f"Photo saved to: {saved_path}")
                log_device_event(db, device_serial, "photo_upload", client_ip, 
                               f"Uploaded and saved photo: {photo_filename} -> {saved_path}")
            else:
                log_device_event(db, device_serial, "photo_upload_failed", client_ip, 
                               f"Failed to save photo: {photo_filename}")
            
        else:
            logger.info(f"Unhandled file data table: {table}")
            
    except Exception as e:
        logger.error(f"Error processing file data: {e}")
        log_device_event(db, device_serial, "error", client_ip, str(e))
    
    return PlainTextResponse("OK")

@app.get("/iclock/register")
@app.post("/iclock/register")
async def register(request: Request, SN: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Handle device registration
    Device calls this when it starts up or reconnects
    """
    logger.info(f"Device registration from SN: {SN}")
    client_ip = request.client.host
    
    # Register or update device
    if SN:
        register_device(db, SN, client_ip)
        log_device_event(db, SN, "register", client_ip, f"Device registered")
    
    return PlainTextResponse("OK")

def parse_attlog_data(data_text: str) -> list:
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

async def forward_to_internal_api(records: list):
    """
    Forward parsed attendance records to internal API
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{INTERNAL_API_URL}/api/attendance/bulk",
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

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Test database connection
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    return {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }

def extract_device_serial(request: Request) -> Optional[str]:
    """Extract device serial number from request"""
    return request.query_params.get("SN")

def register_device(db: Session, serial_number: str, ip_address: str):
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

def update_device_heartbeat(db: Session, serial_number: str, ip_address: str):
    """Update device heartbeat timestamp"""
    device = db.query(Device).filter(Device.serial_number == serial_number).first()
    
    if device:
        device.last_heartbeat = datetime.now()
        device.ip_address = ip_address
        device.is_active = True
        db.commit()

async def save_attendance_records(db: Session, records: list, device_serial: str, raw_data: str) -> int:
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
                
                # Send Telegram notification for new attendance record
                try:
                    await telegram_notifier.send_attendance_notification(
                        db=db,
                        user_id=record['user_id'],
                        device_serial=device_serial,
                        timestamp=datetime.fromisoformat(record['timestamp'].replace(' ', 'T')),
                        in_out=record['in_out'],
                        verify_mode=record['verify_mode'],
                        photo_path=find_latest_photo(device_serial, record['user_id'], record['timestamp'])
                    )
                except Exception as e:
                    logger.error(f"Failed to send Telegram notification: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to save attendance record: {e}")
    
    db.commit()
    return saved_count

def find_latest_photo(device_serial: str, user_id: str, timestamp_str: str) -> Optional[str]:
    """Find the most recent photo for a user around the time of attendance"""
    try:
        # Parse timestamp
        attendance_time = datetime.fromisoformat(timestamp_str.replace(' ', 'T'))
        date_str = attendance_time.strftime("%Y-%m-%d")
        
        # Check photos directory
        env = os.getenv("ENVIRONMENT", "local")
        if env == "production":
            photo_base = "/app/photos"
        else:
            photo_base = "/app/photos"
            
        photo_dir = f"{photo_base}/{device_serial}/{date_str}"
        
        if not os.path.exists(photo_dir):
            return None
            
        # Look for photos taken around the same time
        import glob
        photos = glob.glob(f"{photo_dir}/*{user_id}*.jpg")
        
        if not photos:
            # Look for any photo taken around the same time (within 1 minute)
            attendance_time_str = attendance_time.strftime("%Y%m%d%H%M")
            photos = glob.glob(f"{photo_dir}/{attendance_time_str}*.jpg")
            
        if photos:
            # Return the most recent photo
            photos.sort(key=os.path.getmtime, reverse=True)
            return photos[0]
            
        return None
    except Exception as e:
        logger.error(f"Error finding photo: {e}")
        return None

async def save_photo_file(raw_data: bytes, device_serial: str, photo_filename: str, photo_info: dict) -> Optional[str]:
    """Save photo file to NAS storage"""
    import re
    
    try:
        # Find where JPEG data starts (after metadata lines)
        data_text = raw_data.decode('utf-8', errors='ignore')
        jpeg_start = data_text.find('\x00\xff\xd8\xff')  # JPEG file signature
        
        if jpeg_start == -1:
            # Alternative search for JPEG header
            jpeg_start = raw_data.find(b'\xff\xd8\xff')
            if jpeg_start != -1:
                jpeg_data = raw_data[jpeg_start:]
            else:
                logger.error(f"Could not find JPEG data in photo upload")
                return None
        else:
            jpeg_data = raw_data[jpeg_start + 1:]  # Skip the null byte
        
        # Create directory structure: photos/device_serial/YYYY-MM-DD/
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Use different photo storage path based on environment
        env = os.getenv("ENVIRONMENT", "local")
        if env == "production":
            photo_base = "/app/photos"  # Maps to /mnt/kpspdrive/attendance_photo
        else:
            photo_base = "/app/photos"  # Maps to ./photos for local
            
        photo_dir = f"{photo_base}/{device_serial}/{today}"
        
        # Create directory if it doesn't exist
        os.makedirs(photo_dir, exist_ok=True)
        
        # Clean filename for filesystem
        safe_filename = re.sub(r'[^\w\-_.]', '_', photo_filename)
        if not safe_filename.lower().endswith('.jpg'):
            safe_filename += '.jpg'
        
        photo_path = f"{photo_dir}/{safe_filename}"
        
        # Save JPEG data to file
        with open(photo_path, 'wb') as f:
            f.write(jpeg_data)
        
        logger.info(f"Saved photo: {photo_path} ({len(jpeg_data)} bytes)")
        return photo_path
        
    except Exception as e:
        logger.error(f"Failed to save photo file: {e}")
        return None

def log_device_event(db: Session, device_serial: str, event_type: str, 
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

# Custom exception handler for invalid HTTP requests
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    client_ip = request.client.host if request.client else "unknown"
    
    # Try to get request body for debugging
    try:
        body = await request.body()
        body_text = body.decode('utf-8', errors='replace') if body else ""
    except Exception:
        body_text = "[Could not read body]"
    
    logger.error(f"[{client_ip}] Unhandled exception: {exc}")
    logger.error(f"[{client_ip}] Request URL: {request.url}")
    logger.error(f"[{client_ip}] Request method: {request.method}")
    logger.error(f"[{client_ip}] Request headers: {dict(request.headers)}")
    logger.error(f"[{client_ip}] Request body: {repr(body_text[:500])}")
    logger.error(f"[{client_ip}] Traceback: {traceback.format_exc()}")
    
    return PlainTextResponse("Internal Server Error", status_code=500)

# Add catch-all route to log unmatched requests
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"], include_in_schema=False)
async def catch_all(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path
    query = str(request.query_params)
    headers = dict(request.headers)
    
    # Get request body
    try:
        body = await request.body()
        body_text = body.decode('utf-8', errors='replace') if body else ""
    except Exception:
        body_text = "[Could not read body]"
    
    logger.warning(f"[{client_ip}] UNMATCHED ROUTE: {method} {path}")
    logger.warning(f"[{client_ip}] Query params: {query}")
    logger.warning(f"[{client_ip}] Headers: {headers}")
    if body_text:
        logger.warning(f"[{client_ip}] Body: {repr(body_text[:500])}")
    
    # Check if it looks like a ZKTeco request
    if any(keyword in path.lower() for keyword in ['iclock', 'zkeco', 'attendance', 'device']):
        logger.info(f"[{client_ip}] This looks like a ZKTeco device request!")
    
    return PlainTextResponse("Not Found", status_code=404)

if __name__ == "__main__":
    import uvicorn
    import threading
    from tcp_server import start_tcp_server
    
    logger.info("Starting ZKTeco ADMS Push Server with enhanced logging")
    
    # Run FastAPI on port 8080 for ZKTeco ADMS protocol
    logger.info("Starting ZKTeco ADMS FastAPI Server on port 8080")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8080, 
        log_level="info",
        access_log=True
    )