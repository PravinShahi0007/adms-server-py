from fastapi import FastAPI, Request, Response, Depends
from fastapi.responses import PlainTextResponse
import httpx
import logging
from datetime import datetime
from typing import Optional
import os
from sqlalchemy.orm import Session
from database import get_db, create_tables
from models import Device, AttendanceRecord, DeviceLog
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
            saved_count = save_attendance_records(db, records, device_serial, data_text)
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
    ATTLOG\tuser_id\ttimestamp\tverify_mode\tin_out\tworkcode
    """
    records = []
    
    for line in data_text.strip().split('\n'):
        if not line.strip() or not line.startswith('ATTLOG'):
            continue
            
        try:
            parts = line.split('\t')
            if len(parts) >= 6:
                record = {
                    'user_id': parts[1],
                    'timestamp': parts[2], 
                    'verify_mode': int(parts[3]),
                    'in_out': int(parts[4]),
                    'workcode': parts[5] if parts[5] else '0'
                }
                records.append(record)
                logger.debug(f"Parsed record: {record}")
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

def save_attendance_records(db: Session, records: list, device_serial: str, raw_data: str) -> int:
    """Save attendance records to database"""
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
        except Exception as e:
            logger.error(f"Failed to save attendance record: {e}")
    
    db.commit()
    return saved_count

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
    
    logger.info("Starting ZKTeco ADMS Push Server with enhanced logging")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8080, 
        log_level="info",
        access_log=True
    )