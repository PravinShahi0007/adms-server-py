from fastapi import FastAPI, Request, Response, Depends, BackgroundTasks
from fastapi.responses import PlainTextResponse
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from database import get_db, create_tables
from models import Device, AttendanceRecord, DeviceLog, Employee
from starlette.middleware.base import BaseHTTPMiddleware
import traceback
from contextlib import asynccontextmanager

# Import new services and utilities
from services import NotificationService, PhotoService, DeviceService, AttendanceService
from utils.config import config
from utils.logging_setup import setup_logging

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
    
    if config.COMM_KEY:
        logger.info("COMM_KEY authentication enabled")
    else:
        logger.info("No COMM_KEY - authentication disabled")
    logger.info("Database tables created successfully")
    
    yield
    
    # Shutdown (if needed)
    logger.info("ZKTeco ADMS Push Server shutting down")

app = FastAPI(title="ZKTeco ADMS Push Server", version="1.0.0", lifespan=lifespan)

# Initialize services
notification_service = NotificationService()
photo_service = PhotoService()
device_service = DeviceService()
attendance_service = AttendanceService(config.INTERNAL_API_URL)

def cleanup_expired_pending_notifications():
    """Remove pending notifications older than 5 minutes"""
    return notification_service.cleanup_expired_pending_notifications()

async def trigger_pending_notifications(saved_path: str, photo_filename: str, device_serial: str, db):
    """Event-driven trigger when a photo is uploaded - check for pending notifications"""
    await notification_service.trigger_pending_notifications(saved_path, photo_filename, device_serial, db)

def trigger_pending_notifications_sync(saved_path: str, photo_filename: str, device_serial: str):
    """Event-driven trigger when a photo is uploaded - check for pending notifications (sync version for BackgroundTasks)"""
    notification_service.trigger_pending_notifications_sync(saved_path, photo_filename, device_serial)

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
            
            # Selective logging - skip health checks and routine heartbeats
            if "/health" not in str(url) and "/iclock/getrequest" not in str(url):
                logger.info(f"[{client_ip}] {method} {url}")
                logger.debug(f"[{client_ip}] Headers: {headers}")
                
                if body:
                    # Log body content safely
                    try:
                        body_text = body.decode('utf-8', errors='replace')
                        logger.info(f"[{client_ip}] Body ({len(body)} bytes): {repr(body_text[:500])}")
                    except Exception:
                        logger.info(f"[{client_ip}] Body ({len(body)} bytes): [binary data]")
            else:
                # Minimal logging for routine requests
                logger.debug(f"[{client_ip}] {method} {url}")
            
            # Process request
            response = await call_next(request)
            
            # Log response - skip routine requests
            duration = (datetime.now() - start_time).total_seconds() * 1000
            if "/health" not in str(url) and "/iclock/getrequest" not in str(url):
                logger.info(f"[{client_ip}] {method} {url} -> {response.status_code} ({duration:.2f}ms)")
            else:
                logger.debug(f"[{client_ip}] {method} {url} -> {response.status_code} ({duration:.2f}ms)")
            
            return response
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"[{client_ip}] {method} {url} -> ERROR ({duration:.2f}ms): {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

# Add the middleware
app.add_middleware(RequestLoggingMiddleware)

# Setup logging
logger = setup_logging()

def validate_comm_key(request: Request) -> bool:
    """Validate communication key if configured"""
    request_key = request.query_params.get("key") or request.headers.get("X-Comm-Key")
    return config.validate_comm_key(request_key)


@app.get("/iclock/getrequest")
async def get_request(request: Request, SN: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Handle device heartbeat and command requests
    Device periodically calls this to check for pending commands
    """
    # Device heartbeat (reduced logging)
    logger.debug(f"Device heartbeat from SN: {SN}")
    client_ip = request.client.host
    
    # Log device activity
    device_service.log_device_event(db, SN, "heartbeat", client_ip, f"Heartbeat from {SN}")
    
    # Update device last seen
    if SN:
        device_service.update_device_heartbeat(db, SN, client_ip)
    
    return PlainTextResponse("OK")

@app.get("/iclock/cdata")
async def cdata_get(request: Request, SN: Optional[str] = None, options: Optional[str] = None, 
                   language: Optional[str] = None, pushver: Optional[str] = None, 
                   PushOptionsFlag: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Handle GET requests from ZKTeco devices (device registration/heartbeat)
    """
    client_ip = request.client.host
    device_serial = SN
    
    logger.info(f"Device {device_serial} heartbeat from {client_ip}")
    
    if device_serial:
        # Update device heartbeat
        device_service.update_device_heartbeat(db, device_serial, client_ip)
    
    # Return OK response for device
    return PlainTextResponse("OK")

@app.post("/iclock/cdata")
async def cdata(request: Request, background_tasks: BackgroundTasks, SN: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Handle attendance data upload from device
    Receives ATTLOG records in plain text format OR photo data
    """
    raw_data = await request.body()
    client_ip = request.client.host
    
    logger.info(f"Received data: {len(raw_data)} bytes from {client_ip}")
    
    device_serial = SN or device_service.extract_device_serial(request)
    
    # Check if it's photo data (multipart form data) or plain text
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        # Handle photo upload
        form = await request.form()
        sn = form.get("sn", device_serial)
        table = form.get("table")
        stamps = form.get("stamps")
        photo_file = form.get("photodata")
        
        if table == "ATTPHOTO" and stamps and photo_file:
            logger.info(f"Received photo upload: sn={sn}, stamps={stamps}")
            
            # Save photo and trigger notifications using BackgroundTasks
            saved_path = await photo_service.save_photo(photo_file, stamps, sn)
            background_tasks.add_task(trigger_pending_notifications_sync, saved_path, stamps, sn)
            
            return PlainTextResponse("OK")
        else:
            logger.warning(f"Invalid photo upload data: table={table}, stamps={stamps}")
            return PlainTextResponse("OK")
    
    # Handle text data (attendance records)
    try:
        data_text = raw_data.decode('utf-8')
        logger.debug(f"Raw text data: {data_text}")
        
        # Parse and save attendance records
        records = attendance_service.parse_attlog_data(data_text)
        logger.info(f"Parsed {len(records)} attendance records")
        
        if records:
            saved_count = await attendance_service.save_attendance_records(
                db, records, device_serial, data_text, background_tasks, 
                photo_service, notification_service
            )
            logger.info(f"Saved {saved_count} new attendance records")
            
            # Log successful data upload
            device_service.log_device_event(db, device_serial, "data_upload", client_ip, 
                           f"Uploaded {len(records)} records")
            
            # Forward to internal API
            await attendance_service.forward_to_internal_api(records)
            
    except Exception as e:
        logger.error(f"Error processing attendance data: {e}")
        device_service.log_device_event(db, device_serial, "error", client_ip, str(e))
    
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
    
    device_serial = SN or device_service.extract_device_serial(request)
    
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
            saved_path = await photo_service.save_photo_file(raw_data, device_serial, photo_filename, photo_info)
            
            if saved_path:
                logger.info(f"Photo saved to: {saved_path}")
                device_service.log_device_event(db, device_serial, "photo_upload", client_ip, 
                               f"Uploaded and saved photo: {photo_filename} -> {saved_path}")
                
                # Event-driven trigger: Check for pending notifications
                await trigger_pending_notifications(saved_path, photo_filename, device_serial, db)
            else:
                device_service.log_device_event(db, device_serial, "photo_upload_failed", client_ip, 
                               f"Failed to save photo: {photo_filename}")
            
        else:
            logger.info(f"Unhandled file data table: {table}")
            
    except Exception as e:
        logger.error(f"Error processing file data: {e}")
        device_service.log_device_event(db, device_serial, "error", client_ip, str(e))
    
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
        device_service.register_device(db, SN, client_ip)
        device_service.log_device_event(db, SN, "register", client_ip, f"Device registered")
    
    return PlainTextResponse("OK")


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


async def save_attendance_records(db: Session, records: list, device_serial: str, raw_data: str, background_tasks: BackgroundTasks) -> int:
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
                    photo_path = find_latest_photo(device_serial, record['user_id'], record['timestamp'])
                    
                    if photo_path:
                        # Photo exists - send immediately via background task
                        background_tasks.add_task(
                            send_notification_with_photo,
                            db, record['user_id'], device_serial,
                            datetime.fromisoformat(record['timestamp'].replace(' ', 'T')),
                            record['in_out'], record['verify_mode'], photo_path
                        )
                        logger.info(f"Queued immediate notification with photo for user {record['user_id']}")
                    else:
                        # No photo - store in pending notifications for event-driven trigger
                        logger.info(f"No photo found for {record['user_id']}, adding to pending notifications...")
                        
                        with pending_notifications_lock:
                            pending_notifications[record['user_id']] = {
                                'attendance_time': datetime.fromisoformat(record['timestamp'].replace(' ', 'T')),
                                'device_serial': device_serial,
                                'timestamp_str': record['timestamp'],
                                'in_out': record['in_out'],
                                'verify_mode': record['verify_mode'],
                                'db': db,
                                'created_at': datetime.now()
                            }
                        
                        # Queue timeout handler as background task
                        background_tasks.add_task(
                            handle_notification_timeout_sync,
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

async def send_smart_notification(
    db: Session,
    telegram_notifier,
    user_id: str,
    device_serial: str,
    timestamp: datetime,
    in_out: int,
    verify_mode: int,
    timestamp_str: str
):
    """Send notification with Smart Delay - immediate if photo exists, delayed retry if not"""
    import asyncio
    from datetime import datetime
    
    # First attempt - check for photo immediately
    photo_path = find_latest_photo(device_serial, user_id, timestamp_str)
    
    if photo_path:
        # Photo found - send immediately
        logger.info(f"Photo found immediately for {user_id}: {photo_path}")
        await telegram_notifier.send_attendance_notification(
            db=db,
            user_id=user_id,
            device_serial=device_serial,
            timestamp=timestamp,
            in_out=in_out,
            verify_mode=verify_mode,
            photo_path=photo_path
        )
    else:
        # No photo found - store in pending notifications for event-driven trigger
        logger.info(f"No photo found for {user_id}, adding to pending notifications...")
        
        # Store attendance data for later processing when photo arrives
        pending_notifications[user_id] = {
            'attendance_time': timestamp,
            'device_serial': device_serial,
            'timestamp_str': timestamp_str,
            'in_out': in_out,
            'verify_mode': verify_mode,
            'db': db,
            'created_at': datetime.now()
        }
        
        # Create background task for timeout handling (non-blocking)
        asyncio.create_task(handle_notification_timeout(
            user_id, telegram_notifier, db, device_serial, timestamp, in_out, verify_mode
        ))

def send_notification_with_photo(
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
        
        loop.run_until_complete(telegram_notifier.send_attendance_notification(
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
    user_id: str,
    device_serial: str,
    timestamp: datetime,
    in_out: int,
    verify_mode: int
):
    """Handle 60-second timeout for pending notifications (sync function for BackgroundTasks)"""
    import asyncio
    import time
    
    try:
        # Wait 10 seconds for photo to arrive
        time.sleep(10)
        
        # Check if still pending (photo might have arrived and removed it) - thread-safe
        with pending_notifications_lock:
            if user_id in pending_notifications:
                # Remove from pending before processing
                del pending_notifications[user_id]
                should_send_notification = True
            else:
                should_send_notification = False
                
        if should_send_notification:
            logger.info(f"No photo arrived for {user_id} after 10 seconds, sending text-only notification")
            
            # Create new event loop for this background task
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Send text-only notification
            loop.run_until_complete(telegram_notifier.send_attendance_notification(
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
    user_id: str,
    telegram_notifier,
    db: Session,
    device_serial: str,
    timestamp: datetime,
    in_out: int,
    verify_mode: int
):
    """Handle 60-second timeout for pending notifications (legacy async version)"""
    import asyncio
    
    # Wait 60 seconds
    await asyncio.sleep(60)
    
    # Check if still pending (photo might have arrived and removed it)
    if user_id in pending_notifications:
        logger.info(f"No photo arrived for {user_id} after 60 seconds, sending text-only notification")
        # Remove from pending
        del pending_notifications[user_id]
        
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
            
        # Look for photos with exact user_id match at the end of filename
        import glob
        import re
        
        # First priority: Find photos that end with -{user_id}.jpg
        photos = glob.glob(f"{photo_dir}/*-{user_id}.jpg")
        
        if photos:
            # Sort by filename timestamp (most recent first)
            photos.sort(reverse=True)
            
            # Find photo closest to attendance time (within 3 minutes)
            for photo in photos:
                # Extract timestamp from filename: YYYYMMDDHHMISS-{user_id}.jpg
                filename = os.path.basename(photo)
                match = re.match(r'(\d{14})-\d+\.jpg', filename)
                if match:
                    photo_time_str = match.group(1)
                    try:
                        photo_time = datetime.strptime(photo_time_str, "%Y%m%d%H%M%S")
                        time_diff = abs((attendance_time - photo_time).total_seconds())
                        
                        # Return photo if within 3 minutes (180 seconds)
                        if time_diff <= 180:
                            return photo
                    except ValueError:
                        continue
            
            # If no photo within 3 minutes, don't return old photos
            # This prevents mixing up old photos with new attendance
            
        return None
    except Exception as e:
        logger.error(f"Error finding photo: {e}")
        return None

async def save_photo(photo_file, photo_filename: str, device_serial: str) -> Optional[str]:
    """Save photo from form upload data"""
    try:
        if not photo_file:
            logger.error("No photo file provided")
            return None
            
        # Read photo content
        photo_data = await photo_file.read()
        
        # Create directory structure: photos/device_serial/YYYY-MM-DD/
        from datetime import datetime
        import re
        
        # Extract timestamp from filename: YYYYMMDDHHMISS-XX.jpg
        match = re.match(r'(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})-(\d+)\.jpg', photo_filename)
        if match:
            year, month, day = match.groups()[:3]
            date_folder = f"{year}-{month}-{day}"
        else:
            # Fallback to current date
            date_folder = datetime.now().strftime("%Y-%m-%d")
        
        photo_dir = f"photos/{device_serial}/{date_folder}"
        os.makedirs(photo_dir, exist_ok=True)
        
        # Save photo file
        photo_path = f"{photo_dir}/{photo_filename}"
        with open(photo_path, 'wb') as f:
            f.write(photo_data)
        
        logger.info(f"Saved photo: {photo_path}")
        return photo_path
        
    except Exception as e:
        logger.error(f"Error saving photo: {e}")
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