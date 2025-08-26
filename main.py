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
from utils.config import config
from utils.logging_setup import setup_logging
from utils import container, event_bus, PhotoUploadedEvent

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

# Initialize service container with dependency injection
container.initialize()

# Get services from DI container
notification_service = container.get_notification_service()
photo_service = container.get_photo_service()
device_service = container.get_device_service()
attendance_service = container.get_attendance_service()
background_task_service = container.get_background_task_service()
background_event_handlers = container.get_background_event_handlers()

# Wrapper functions removed - calling services directly

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
            background_tasks.add_task(
                background_event_handlers.handle_photo_uploaded_sync,
                saved_path, stamps, sn
            )
            
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
                photo_service, notification_service, background_task_service
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
                
                # Event-driven trigger: Publish photo uploaded event
                photo_event = PhotoUploadedEvent(
                    saved_path=saved_path,
                    photo_filename=photo_filename,
                    device_serial=device_serial,
                    timestamp=datetime.now()
                )
                await event_bus.publish_photo_uploaded(photo_event)
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
    
    # Run FastAPI on port 8080 for ZKTeco ADMS protocol
    logger.info("Starting ZKTeco ADMS FastAPI Server on port 8080")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8080, 
        log_level="info",
        access_log=True
    )