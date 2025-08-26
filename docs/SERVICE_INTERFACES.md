# ZKTeco ADMS Server - Service Interfaces Documentation

## 🔧 Overview

This document provides comprehensive interface documentation for all services in the ZKTeco ADMS Server, including method signatures, parameters, return values, and usage examples.

## 📋 Service Container Interface

### ServiceContainer

Central dependency injection container managing service lifecycle and dependencies.

```python
class ServiceContainer:
    def initialize() -> None
    def get_service(service_name: str) -> Any
    def get_notification_service() -> NotificationService
    def get_photo_service() -> PhotoService  
    def get_device_service() -> DeviceService
    def get_attendance_service() -> AttendanceService
    def get_background_task_service() -> BackgroundTaskService
    def get_background_event_handlers() -> BackgroundEventHandlers
```

**Usage:**
```python
from utils import container

# Initialize container
container.initialize()

# Get services
notification_service = container.get_notification_service()
photo_service = container.get_photo_service()
```

---

## 🔔 NotificationService

Manages attendance notifications and photo matching with thread-safe pending notification storage.

### Constructor
```python
def __init__(self, telegram_notifier: Optional[TelegramNotifier] = None)
```

**Parameters:**
- `telegram_notifier`: Optional TelegramNotifier instance (uses DI when None)

### Methods

#### cleanup_expired_pending_notifications
```python
def cleanup_expired_pending_notifications(self) -> int
```
**Returns:** Number of expired notifications removed  
**Description:** Removes pending notifications older than 5 minutes

#### trigger_pending_notifications
```python
async def trigger_pending_notifications(
    self,
    saved_path: str, 
    photo_filename: str, 
    device_serial: str, 
    db: Session
) -> None
```
**Parameters:**
- `saved_path`: Full path to saved photo file
- `photo_filename`: Original photo filename with user ID
- `device_serial`: Device serial number
- `db`: Database session

**Description:** Event-driven trigger when photo is uploaded - checks for pending notifications

#### trigger_pending_notifications_sync
```python  
def trigger_pending_notifications_sync(
    self,
    saved_path: str, 
    photo_filename: str, 
    device_serial: str
) -> None
```
**Description:** Sync wrapper for background tasks - creates new event loop and DB session

#### add_pending_notification
```python
def add_pending_notification(
    self,
    user_id: str,
    attendance_time: datetime, 
    device_serial: str,
    timestamp_str: str,
    in_out: int,
    verify_mode: int,
    db: Session
) -> None
```
**Parameters:**
- `user_id`: Employee user ID
- `attendance_time`: Parsed attendance timestamp
- `device_serial`: Device serial number
- `timestamp_str`: Original timestamp string
- `in_out`: Entry (0) or exit (1)
- `verify_mode`: Verification method used
- `db`: Database session

**Description:** Thread-safe addition of notification to pending queue

#### handle_photo_uploaded_event
```python
async def handle_photo_uploaded_event(self, event: PhotoUploadedEvent) -> None
```
**Parameters:**
- `event`: PhotoUploadedEvent instance with photo details

**Description:** Event handler for photo uploaded events

#### Background Task Methods

```python
def send_notification_with_photo(
    self,
    user_id: str,
    device_serial: str,
    timestamp: datetime,
    in_out: int, 
    verify_mode: int,
    photo_path: str
) -> None
```

```python
def handle_notification_timeout_sync(
    self,
    user_id: str,
    device_serial: str,
    timestamp: datetime,
    in_out: int,
    verify_mode: int
) -> None
```

**Usage Example:**
```python
# Add pending notification
notification_service.add_pending_notification(
    user_id="001",
    attendance_time=datetime.now(),
    device_serial="ABC123", 
    timestamp_str="2025-08-27 08:30:00",
    in_out=0,
    verify_mode=1,
    db=db_session
)

# Trigger photo check
await notification_service.trigger_pending_notifications(
    saved_path="/photos/20250827083000-001.jpg",
    photo_filename="20250827083000-001.jpg", 
    device_serial="ABC123",
    db=db_session
)
```

---

## 📸 PhotoService

Handles photo upload, storage, and file management operations.

### Methods

#### save_photo
```python
async def save_photo(
    self,
    photo_file: UploadFile,
    stamps: str,
    sn: str
) -> Optional[str]
```
**Parameters:**
- `photo_file`: FastAPI UploadFile object
- `stamps`: Photo filename from device
- `sn`: Device serial number

**Returns:** Saved file path or None if failed  
**Description:** Save multipart photo upload to storage

#### save_photo_file  
```python
async def save_photo_file(
    self,
    raw_data: bytes,
    device_serial: str, 
    photo_filename: str,
    photo_info: str
) -> Optional[str]
```
**Parameters:**
- `raw_data`: Binary photo data
- `device_serial`: Device serial number
- `photo_filename`: Target filename
- `photo_info`: Additional photo metadata

**Returns:** Saved file path or None if failed  
**Description:** Save binary photo data to storage

#### find_latest_photo
```python
def find_latest_photo(
    self,
    device_serial: str,
    user_id: str, 
    timestamp: str
) -> Optional[str]
```
**Parameters:**
- `device_serial`: Device serial number
- `user_id`: Employee user ID
- `timestamp`: Attendance timestamp

**Returns:** Path to matching photo or None  
**Description:** Find latest photo matching user and timestamp

**Usage Example:**
```python
# Save uploaded photo
saved_path = await photo_service.save_photo(
    photo_file=upload_file,
    stamps="20250827083000-001.jpg",
    sn="ABC123"
)

# Find existing photo
photo_path = photo_service.find_latest_photo(
    device_serial="ABC123",
    user_id="001", 
    timestamp="2025-08-27 08:30:00"
)
```

---

## 📱 DeviceService

Manages device registration, heartbeats, and activity logging.

### Methods

#### register_device
```python
def register_device(
    self,
    db: Session,
    serial_number: str,
    ip_address: str
) -> None
```
**Parameters:**
- `db`: Database session
- `serial_number`: Device serial number
- `ip_address`: Device IP address

**Description:** Register or update device information in database

#### update_device_heartbeat
```python
def update_device_heartbeat(
    self,
    db: Session,
    serial_number: str,
    ip_address: str  
) -> None
```
**Description:** Update device last heartbeat timestamp

#### log_device_event
```python
def log_device_event(
    self,
    db: Session,
    device_serial: str,
    event_type: str,
    ip_address: str,
    description: str
) -> None
```
**Parameters:**
- `event_type`: Event category (heartbeat, data_upload, photo_upload, error)
- `description`: Human-readable event description

**Description:** Log device activity to database

#### extract_device_serial  
```python
def extract_device_serial(self, request: Request) -> Optional[str]
```
**Parameters:**
- `request`: FastAPI Request object

**Returns:** Device serial from query parameters or None  
**Description:** Extract device serial number from request

**Usage Example:**
```python
# Register device
device_service.register_device(
    db=db_session,
    serial_number="ABC123",
    ip_address="192.168.1.100"
)

# Log activity
device_service.log_device_event(
    db=db_session,
    device_serial="ABC123", 
    event_type="data_upload",
    ip_address="192.168.1.100",
    description="Uploaded 5 attendance records"
)
```

---

## 📊 AttendanceService

Processes attendance data parsing, database storage, and API forwarding.

### Constructor
```python
def __init__(self, internal_api_url: str)
```

### Methods

#### parse_attlog_data
```python
def parse_attlog_data(self, data_text: str) -> List[Dict[str, Any]]
```
**Parameters:**
- `data_text`: Raw attendance data from device

**Returns:** List of parsed attendance records  
**Supported Formats:**
1. `ATTLOG\tuser_id\ttimestamp\tverify_mode\tin_out\tworkcode`
2. `user_id\ttimestamp\tverify_mode\tin_out\tworkcode` (direct)

#### save_attendance_records
```python
async def save_attendance_records(
    self,
    db: Session,
    records: List[Dict[str, Any]],
    device_serial: str, 
    raw_data: str,
    background_tasks: BackgroundTasks,
    photo_service: PhotoService,
    notification_service: NotificationService,
    background_task_service: BackgroundTaskService
) -> int
```
**Returns:** Number of records saved (excluding duplicates)  
**Description:** Save records to database and trigger notifications

#### forward_to_internal_api
```python
async def forward_to_internal_api(self, records: List[Dict[str, Any]]) -> None
```
**Description:** Forward attendance records to configured internal API

**Usage Example:**
```python
# Parse attendance data
raw_data = "ATTLOG\t001\t2025-08-27 08:30:00\t1\t0\t0"
records = attendance_service.parse_attlog_data(raw_data)

# Save to database
saved_count = await attendance_service.save_attendance_records(
    db=db_session,
    records=records,
    device_serial="ABC123",
    raw_data=raw_data,
    background_tasks=background_tasks,
    photo_service=photo_service,
    notification_service=notification_service, 
    background_task_service=background_task_service
)
```

---

## 🔄 BackgroundTaskService

Unified coordination of background tasks across services.

### Constructor
```python
def __init__(self, notification_service: NotificationService)
```

### Methods

#### schedule_photo_notification_trigger
```python
def schedule_photo_notification_trigger(
    self,
    background_tasks: BackgroundTasks,
    saved_path: str,
    photo_filename: str,
    device_serial: str
) -> None
```

#### schedule_notification_timeout
```python
def schedule_notification_timeout(
    self,
    background_tasks: BackgroundTasks,
    user_id: str,
    device_serial: str, 
    timestamp: datetime,
    in_out: int,
    verify_mode: int
) -> None
```

#### schedule_notification_with_photo
```python
def schedule_notification_with_photo(
    self,
    background_tasks: BackgroundTasks,
    user_id: str,
    device_serial: str,
    timestamp: datetime,
    in_out: int,
    verify_mode: int,
    photo_path: str
) -> None
```

**Usage Example:**
```python
# Schedule photo notification trigger
background_task_service.schedule_photo_notification_trigger(
    background_tasks=background_tasks,
    saved_path="/photos/photo.jpg",
    photo_filename="20250827083000-001.jpg",
    device_serial="ABC123"
)

# Schedule timeout handler
background_task_service.schedule_notification_timeout(
    background_tasks=background_tasks,
    user_id="001",
    device_serial="ABC123",
    timestamp=datetime.now(),
    in_out=0, 
    verify_mode=1
)
```

---

## 📡 Event System Interfaces

### EventBus
```python
class EventBus:
    def subscribe(self, event_type: str, handler: Callable) -> None
    async def publish(self, event_type: str, event_data: Any) -> None
    async def publish_photo_uploaded(self, event: PhotoUploadedEvent) -> None
```

### PhotoUploadedEvent
```python
@dataclass
class PhotoUploadedEvent:
    saved_path: str
    photo_filename: str
    device_serial: str
    timestamp: datetime
    user_id: str = None  # Auto-extracted from filename
```

**Usage Example:**
```python
# Create and publish event
event = PhotoUploadedEvent(
    saved_path="/photos/20250827083000-001.jpg",
    photo_filename="20250827083000-001.jpg",
    device_serial="ABC123",
    timestamp=datetime.now()
)

await event_bus.publish_photo_uploaded(event)

# Subscribe to events
event_bus.subscribe(
    'photo_uploaded',
    notification_service.handle_photo_uploaded_event
)
```

---

## 🔧 Background Event Handlers

### BackgroundEventHandlers
```python
class BackgroundEventHandlers:
    def __init__(self, event_bus: EventBus)
    
    def handle_photo_uploaded_sync(
        self,
        saved_path: str,
        photo_filename: str,
        device_serial: str
    ) -> None
```

**Description:** Provides sync wrappers for event handlers to be used with FastAPI BackgroundTasks

**Usage Example:**
```python
# Schedule background event handling
background_tasks.add_task(
    background_event_handlers.handle_photo_uploaded_sync,
    saved_path="/photos/photo.jpg",
    photo_filename="20250827083000-001.jpg", 
    device_serial="ABC123"
)
```

---

## 🎯 Configuration Interfaces

### Config
```python
class Config:
    # Database
    DATABASE_URL: str
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str  
    CHAT_ID: str
    
    # Security
    COMM_KEY: str
    
    # API
    INTERNAL_API_URL: str
    
    # Storage
    PHOTO_STORAGE_PATH: str
    
    # Logging
    LOG_LEVEL: str
    
    def validate_comm_key(self, request_key: str) -> bool
```

**Usage Example:**
```python
from utils.config import config

# Access configuration
if config.COMM_KEY:
    # Authentication enabled
    pass
    
database_url = config.DATABASE_URL
```

---

## 📝 Error Handling Patterns

All services follow consistent error handling:

```python
try:
    result = await service_operation()
    logger.info(f"Operation completed successfully: {result}")
    return result
except SpecificException as e:
    logger.error(f"Specific error in {operation_name}: {e}")
    # Handle specific case
    raise
except Exception as e:
    logger.error(f"Unexpected error in {operation_name}: {e}")
    # Graceful degradation or re-raise
```

## 🔄 Thread Safety

Services with thread-safe operations:
- **NotificationService**: Pending notifications with lock
- **DatabaseOperations**: Session-per-thread pattern
- **BackgroundTasks**: Isolated execution contexts

## 📊 Performance Considerations

- Use async methods for I/O operations
- Create new database sessions for background tasks
- Close resources in finally blocks
- Batch operations when processing multiple records
- Use connection pooling for database access

This interface documentation provides all necessary information for developers to integrate with and extend the ZKTeco ADMS Server services.