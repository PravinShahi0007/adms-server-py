# ZKTeco ADMS Push Server - API Documentation

## Overview
ZKTeco ADMS Push Server is a FastAPI-based server that processes attendance data and photos from ZKTeco devices with enterprise-grade architecture featuring dependency injection and event-driven patterns.

## Architecture
- **Dependency Injection**: Centralized service management
- **Event-Driven**: Photo uploads trigger notifications via event bus
- **Microservices Pattern**: Separated concerns into dedicated services
- **Background Tasks**: Non-blocking notification processing

## API Endpoints

### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "database": "healthy", 
  "timestamp": "2025-08-27T00:00:00.000000"
}
```

### Device Heartbeat
```http
GET /iclock/getrequest?SN={device_serial}
```

**Parameters:**
- `SN` (string): Device serial number
- `key` (optional): Communication key for authentication

**Response:** `OK`

**Description:** Device heartbeat endpoint. Updates device last_seen timestamp.

### Device Registration
```http
POST /iclock/register?SN={device_serial}
```

**Parameters:**
- `SN` (string): Device serial number

**Response:** `OK`

**Description:** Registers or updates device information in database.

### Attendance Data Upload
```http
POST /iclock/cdata?SN={device_serial}
Content-Type: text/plain
```

**Body Format:**
```
ATTLOG\tuser_id\ttimestamp\tverify_mode\tin_out\tworkcode
```

**Example:**
```
ATTLOG	001	2025-08-27 08:30:00	1	0	0
ATTLOG	002	2025-08-27 08:31:00	1	1	0
```

**Response:** `OK`

**Process Flow:**
1. Parse attendance records
2. Save to database
3. Check for existing photos
4. If photo exists → Send notification immediately
5. If no photo → Add to pending notifications with 10s timeout
6. Forward to internal API (if configured)

### Photo Upload (Multipart)
```http
POST /iclock/cdata?SN={device_serial}&table=ATTPHOTO
Content-Type: multipart/form-data
```

**Form Fields:**
- `AttPhoto`: Photo file
- `sn`: Device serial number  
- `stamps`: Photo filename (format: YYYYMMDDHHMISS-{user_id}.jpg)

**Response:** `OK`

**Process Flow:**
1. Save photo to storage
2. Publish PhotoUploadedEvent
3. Event triggers pending notification check
4. Send notification if user has pending attendance

### Photo Upload (Binary)
```http
POST /iclock/fdata?SN={device_serial}&table=ATTPHOTO
Content-Type: application/octet-stream
```

**Response:** `OK`

**Description:** Alternative photo upload endpoint for binary data.

## Event System

### PhotoUploadedEvent
Triggered when a photo is uploaded:

```python
@dataclass
class PhotoUploadedEvent:
    saved_path: str
    photo_filename: str
    device_serial: str
    timestamp: datetime
    user_id: str  # Extracted from filename
```

### Event Flow
```
Photo Upload → PhotoUploadedEvent → NotificationService.handle_photo_uploaded_event()
```

## Authentication

### Communication Key
Optional authentication via `COMM_KEY` environment variable.

**Methods:**
- Query parameter: `?key=your_comm_key`
- Header: `X-Comm-Key: your_comm_key`

## Configuration

### Environment Variables
- `DATABASE_URL`: PostgreSQL connection string
- `TELEGRAM_BOT_TOKEN`: Telegram bot token
- `CHAT_ID`: Telegram chat ID for notifications
- `INTERNAL_API_URL`: Forward API endpoint (optional)
- `COMM_KEY`: Authentication key (optional)
- `LOG_LEVEL`: Logging level (default: INFO)
- `PHOTO_STORAGE_PATH`: Photo storage directory

### Service Dependencies
- PostgreSQL database
- Telegram Bot API
- File system access for photo storage
- Internal API (optional)

## Response Codes

| Code | Description |
|------|-------------|
| 200 | Success - Returns "OK" for device endpoints |
| 200 | Success - Returns JSON for health endpoint |
| 500 | Internal server error |

## Error Handling

All endpoints return `200 OK` to devices even on internal errors to prevent device-side issues. Errors are logged for monitoring.

## Background Processing

### Notification Flow
1. **Immediate**: If photo exists at attendance time
2. **Event-driven**: Photo uploaded later triggers notification
3. **Timeout**: 10-second fallback for text-only notification

### Background Tasks
- Photo upload event processing
- Notification timeouts
- API forwarding
- Photo matching

## Database Schema

### Tables
- `devices`: Device registration and heartbeats
- `attendance_records`: Attendance data with photos
- `device_logs`: Device activity logs  
- `employees`: Employee information

## Integration

### ZKTeco Device Setup
Configure device to push data to:
- Server URL: `http://your-server:8080/iclock/`
- Communication Key: Set `COMM_KEY` if authentication required

### Telegram Integration
1. Create bot via @BotFather
2. Set `TELEGRAM_BOT_TOKEN`
3. Get chat ID and set `CHAT_ID`
4. Bot will send attendance notifications with photos

## Monitoring

### Health Endpoint
Regular health checks verify:
- Application status
- Database connectivity
- Current timestamp

### Logging
Structured logging with:
- Request/response details
- Processing times
- Error tracking
- Service interactions