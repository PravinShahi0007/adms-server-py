# ZKTeco ADMS Server - Architecture Documentation

## 🏗️ Overview

ZKTeco ADMS Server has evolved from a monolithic application to a clean, enterprise-grade architecture featuring dependency injection, event-driven patterns, and microservices principles.

## 🎯 Architecture Principles

### 1. **Dependency Injection (DI)**
- Centralized service management through `ServiceContainer`
- Loose coupling between components
- Easy testing and mocking
- Clear dependency relationships

### 2. **Event-Driven Architecture**
- Decoupled service communication via `EventBus`
- Photo upload events trigger notification processing
- Async event handling for performance
- Type-safe event structures

### 3. **Separation of Concerns**
- Each service has a single responsibility
- Clear boundaries between business logic
- Minimal cross-service dependencies
- Maintainable and testable code

### 4. **Background Processing**
- Non-blocking notification handling
- FastAPI BackgroundTasks integration
- Timeout management for pending notifications
- Event-driven photo matching

## 📁 Project Structure

```
adms-server/
├── main.py                          # FastAPI app + routes (~300 lines)
├── models.py                        # Database models
├── database.py                      # Database configuration
├── telegram_notify.py               # Telegram integration
│
├── services/                        # Business logic services
│   ├── __init__.py                  # Service exports
│   ├── notification_service.py      # Notification management
│   ├── photo_service.py            # Photo upload/storage
│   ├── device_service.py           # Device management
│   ├── attendance_service.py       # Attendance processing
│   ├── background_task_service.py  # Background coordination
│   └── event_handlers.py           # Event handling utilities
│
├── utils/                          # Infrastructure utilities
│   ├── __init__.py                 # Utility exports
│   ├── config.py                   # Configuration management
│   ├── logging_setup.py            # Logging configuration
│   ├── dependency_injection.py     # DI container
│   └── events.py                   # Event system
│
├── docs/                          # Documentation
│   ├── API_DOCUMENTATION.md       # API reference
│   ├── ARCHITECTURE.md            # This document
│   ├── DEPLOYMENT_GUIDE.md        # Deployment instructions
│   └── TESTING_GUIDE.md           # Testing procedures
│
└── tests/                         # Test suite (future)
    ├── __init__.py
    ├── unit/                      # Unit tests
    └── integration/               # Integration tests
```

## 🔧 Service Architecture

### Core Services

#### 1. **NotificationService**
**Responsibility:** Manages attendance notifications and photo matching

```python
class NotificationService:
    def __init__(self, telegram_notifier: TelegramNotifier)
    
    # Core methods:
    async def trigger_pending_notifications()
    def add_pending_notification()
    async def handle_photo_uploaded_event()  # Event handler
    def cleanup_expired_pending_notifications()
```

**Features:**
- Thread-safe pending notifications storage
- 10-second timeout for photo arrival
- Event-driven photo matching
- Automatic cleanup of expired notifications

#### 2. **PhotoService** 
**Responsibility:** Photo upload, storage, and file management

```python
class PhotoService:
    # Core methods:
    async def save_photo()
    async def save_photo_file()
    def find_latest_photo()
```

**Features:**
- NAS storage integration
- Filename pattern matching
- Photo metadata extraction
- Storage path organization

#### 3. **DeviceService**
**Responsibility:** Device registration and heartbeat management

```python
class DeviceService:
    # Core methods:
    def register_device()
    def update_device_heartbeat()
    def log_device_event()
    def extract_device_serial()
```

**Features:**
- Device lifecycle management
- Activity logging
- IP address tracking
- Serial number validation

#### 4. **AttendanceService**
**Responsibility:** Attendance data processing and API forwarding

```python
class AttendanceService:
    # Core methods:
    def parse_attlog_data()
    async def save_attendance_records()
    async def forward_to_internal_api()
```

**Features:**
- Multiple attendance data formats
- Database persistence
- Duplicate detection
- External API integration

#### 5. **BackgroundTaskService**
**Responsibility:** Background task coordination

```python
class BackgroundTaskService:
    # Core methods:
    def schedule_photo_notification_trigger()
    def schedule_notification_timeout()
    def schedule_notification_with_photo()
```

**Features:**
- Unified task scheduling
- Service method coordination
- Error handling and logging

## 🔄 Event System

### EventBus Architecture

```python
class EventBus:
    def subscribe(event_type: str, handler: Callable)
    async def publish(event_type: str, event_data: Any)
    async def publish_photo_uploaded(event: PhotoUploadedEvent)
```

### Event Types

#### PhotoUploadedEvent
```python
@dataclass
class PhotoUploadedEvent:
    saved_path: str
    photo_filename: str  
    device_serial: str
    timestamp: datetime
    user_id: str  # Auto-extracted from filename
```

### Event Flow Diagram

```
Photo Upload Request
        ↓
PhotoService.save_photo()
        ↓
PhotoUploadedEvent published
        ↓
EventBus.publish_photo_uploaded()
        ↓
NotificationService.handle_photo_uploaded_event()
        ↓
Check pending notifications
        ↓
Send Telegram notification
```

## 🏭 Dependency Injection

### ServiceContainer

```python
class ServiceContainer:
    def initialize()                    # Setup all services
    def get_service(name: str)         # Generic service access
    def get_notification_service()     # Typed service getters
    def _setup_event_subscriptions()   # Wire event handlers
```

### Dependency Graph

```
ServiceContainer
├── TelegramNotifier (external)
├── EventBus
├── NotificationService ← TelegramNotifier
├── PhotoService
├── DeviceService  
├── AttendanceService
├── BackgroundTaskService ← NotificationService
└── BackgroundEventHandlers ← EventBus
```

### Service Lifecycle

1. **Initialization Phase:** Container creates all services
2. **Wiring Phase:** Dependencies injected into services
3. **Subscription Phase:** Event handlers registered
4. **Runtime Phase:** Services interact via DI and events

## 📊 Data Flow

### Attendance Processing Flow

```
Device → /iclock/cdata → AttendanceService.parse_attlog_data()
                                    ↓
                         save_attendance_records()
                                    ↓
                    Database + Notification Decision
                                    ↓
    ┌─────────────────────────────────────────────┐
    ↓                                             ↓
Photo Exists                                No Photo
    ↓                                             ↓
Send Immediate                          Add to Pending
Notification                           + Start 10s Timer
```

### Photo Matching Flow

```
Photo Upload → PhotoService.save_photo()
                         ↓
              PhotoUploadedEvent
                         ↓
         NotificationService.handle_photo_uploaded_event()
                         ↓
              Check pending notifications
                         ↓
         ┌──────────────────────────┐
         ↓                          ↓
   User Found                   No Match
         ↓                          ↓
Send Notification             Log + Ignore
& Remove from Pending
```

## 🔒 Error Handling Strategy

### Service Level
- Each service handles its own errors
- Graceful degradation for non-critical failures
- Comprehensive logging for debugging

### API Level  
- Always return 200 OK to devices
- Internal errors logged but don't break device communication
- Health endpoint for service monitoring

### Background Tasks
- Isolated error handling per task
- Failed tasks don't affect other operations
- Error tracking and alerting

## 🚀 Performance Considerations

### Async Processing
- Non-blocking notification handling
- Event-driven architecture reduces coupling
- Background tasks for heavy operations

### Database
- Connection pooling via SQLAlchemy
- Indexed queries for performance
- Separate sessions for background tasks

### Memory Management
- Thread-safe data structures
- Automatic cleanup of expired notifications
- Minimal global state

## 🔍 Testing Strategy

### Unit Testing
- Service isolation via DI
- Mock external dependencies
- Event system testing

### Integration Testing
- Full request/response cycles
- Database integration
- Event propagation testing

### End-to-End Testing
- Device simulation
- Complete workflow validation
- Performance benchmarking

## 📈 Scalability Considerations

### Horizontal Scaling
- Stateless services design
- External state storage (database, files)
- Load balancer compatibility

### Vertical Scaling
- Async processing patterns
- Efficient resource utilization
- Background task optimization

### Future Enhancements
- Redis for distributed notifications
- Message queues for high-volume processing
- Microservices deployment options

## 🛠️ Maintenance

### Code Organization
- Clear service boundaries
- Minimal cross-dependencies  
- Comprehensive documentation

### Debugging
- Structured logging with context
- Service interaction tracing
- Error reporting and monitoring

### Updates
- Service versioning considerations
- Backward compatibility maintenance
- Database migration strategies