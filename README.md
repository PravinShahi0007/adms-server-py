# ZKTeco ADMS Push Server

📖 **[English](README.md)** | 🇹🇭 **[ไทย](README.th.md)**

FastAPI server for receiving attendance data from ZKTeco devices using Push/ADMS mode with PostgreSQL database.

## Features

- Handles ZKTeco Push SDK protocol (`/iclock/*` endpoints)
- PostgreSQL database for data persistence
- Parses and stores ATTLOG records
- Device registration and heartbeat monitoring
- Forwards data to internal API
- Health check with database status
- Comprehensive logging and audit trail
- Docker containerized deployment
- Adminer web interface for database management

## Quick Start with Docker

1. Clone and navigate to the project:
```bash
git clone <repository-url>
cd adms-server
```

2. Start the services:
```bash
docker-compose up -d
```

This will start:
- **App**: FastAPI server on `http://localhost:8080`
- **Database**: PostgreSQL on `http://localhost:5432`
- **Adminer**: Database web interface on `http://localhost:8081`

## Manual Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export DATABASE_URL="postgresql://adms_user:adms_password@localhost:5432/adms_db"
export INTERNAL_API_URL="http://your-api:3000"
export COMM_KEY="your-comm-key"
```

3. Run the server:
```bash
python main.py
```

## ZKTeco Device Configuration

Configure your ZKTeco device:

1. **Network Settings**: Set IP, Gateway, TCP port (usually 4370)
2. **ADMS/Push Settings**:
   - Server Address: `your-server-ip`
   - Server Port: `8080` (or your port)
   - Comm Key: (if using authentication)

## API Endpoints

### Device Communication

- `GET /iclock/getrequest?SN=<serial>` - Device heartbeat/command check
- `POST /iclock/cdata` - Attendance data upload  
- `GET|POST /iclock/register?SN=<serial>` - Device registration

### Monitoring

- `GET /health` - Health check endpoint

## ATTLOG Format

Devices send attendance data in this format:
```
ATTLOG\tuser_id\ttimestamp\tverify_mode\tin_out\tworkcode
```

Example:
```
ATTLOG	1001	2025-08-25 09:00:01	1	0	0
```

Fields:
- `user_id`: Employee ID
- `timestamp`: Attendance timestamp
- `verify_mode`: Verification method (1=fingerprint, etc.)
- `in_out`: Entry type (0=in, 1=out)
- `workcode`: Work code (optional)

## Testing

Test the endpoints manually:

```bash
# Test heartbeat
curl "http://localhost:8080/iclock/getrequest?SN=TEST123"

# Test attendance upload
curl -X POST "http://localhost:8080/iclock/cdata" \
  --data-binary $'ATTLOG\t1001\t2025-08-25 09:00:01\t1\t0\t0'

# Test registration  
curl "http://localhost:8080/iclock/register?SN=TEST123"

# Health check
curl "http://localhost:8080/health"
```

## Database Management

### Accessing the Database

**Via Adminer (Web Interface):**
- URL: `http://localhost:8081`
- System: PostgreSQL
- Server: `db`
- Username: `adms_user`
- Password: `adms_password`
- Database: `adms_db`

**Via psql (Command Line):**
```bash
docker exec -it zkteco-adms-db psql -U adms_user -d adms_db
```

### Database Schema

**Tables:**
- `devices` - Device registration and status
- `attendance_records` - Attendance data from devices
- `device_logs` - Device activity logs
- `processing_queue` - Queue for data processing

**Useful Queries:**
```sql
-- Get device statistics
SELECT * FROM get_device_stats();

-- View recent attendance records
SELECT * FROM attendance_records ORDER BY timestamp DESC LIMIT 10;

-- Check device activity
SELECT * FROM device_logs WHERE event_type = 'heartbeat' 
ORDER BY created_at DESC LIMIT 10;
```

## Production Deployment

### Quick Production Deploy Command

```bash
ssh 172.31.30.159 'cd /home/supatpong/adms-server && git pull && sudo docker-compose down && sudo docker-compose build && sudo mkdir -p /mnt/kpspdrive/attendance_photo && sudo chmod 755 /mnt/kpspdrive/attendance_photo && sudo docker-compose -f docker-compose.prod.yml up -d'
```

### Manual Production Deployment Steps

1. SSH to production server:
```bash
ssh 172.31.30.159
cd /home/supatpong/adms-server
```

2. Update and deploy:
```bash
# Pull latest changes
git pull

# Stop current services
sudo docker-compose down

# Rebuild images with latest code
sudo docker-compose build

# Create and set permissions for NAS photo storage
sudo mkdir -p /mnt/kpspdrive/attendance_photo
sudo chmod 755 /mnt/kpspdrive/attendance_photo

# Start production services
sudo docker-compose -f docker-compose.prod.yml up -d
```

3. Verify deployment:
```bash
# Check container status
sudo docker-compose -f docker-compose.prod.yml ps

# View logs
sudo docker-compose -f docker-compose.prod.yml logs -f app

# Test health endpoint
curl http://localhost:8080/health
```

### Environment Configuration

**Local Development** (`docker-compose.yml`):
- Environment: `ENVIRONMENT=local`
- Photo storage: `./photos` (local directory)
- Database: Development PostgreSQL

**Production** (`docker-compose.prod.yml`):
- Environment: `ENVIRONMENT=production`
- Photo storage: `/mnt/kpspdrive/attendance_photo` (NAS storage)
- Database: Production PostgreSQL

### Photo Storage Structure

Photos are automatically organized by device and date:
```
photos/
├── WAE4242800114/           # Device serial number
│   ├── 2025-08-25/         # Date folder
│   │   ├── 20250825173554-02.jpg
│   │   └── 20250825173600-02.jpg
│   └── 2025-08-26/
└── OTHER_DEVICE_SN/
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://adms_user:adms_password@localhost:5432/adms_db` |
| `INTERNAL_API_URL` | Your internal API endpoint | `http://localhost:3000` |
| `COMM_KEY` | Device communication key | `""` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for notifications | `""` |
| `TELEGRAM_GROUP_CHAT_ID` | Telegram group chat ID | `""` |

## Telegram Notifications

### Setup Telegram Bot

1. **Create a Bot:**
   - Message @BotFather on Telegram
   - Use `/newbot` command
   - Get your bot token

2. **Get Group Chat ID:**
   - Add bot to your group
   - Send a message in the group
   - Visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - Find your group chat ID (negative number)

3. **Configure Environment:**
   ```bash
   TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   TELEGRAM_GROUP_CHAT_ID=-123456789
   ```

### Employee Management

Add employees to receive notifications:

```bash
# Add employee
python employee_manager.py add "01" "John Doe" "IT" "Developer" "+66812345678" "john@company.com"

# List employees  
python employee_manager.py list

# Delete employee
python employee_manager.py delete "01"
```

### Notification Features

- ✅ **Group Notifications:** All attendance events sent to group chat
- ✅ **Personal Notifications:** Optional personal messages to employees  
- ✅ **Photo Attachments:** Attendance photos sent with notifications
- ✅ **Rich Messages:** Formatted messages with employee details
- ✅ **Multi-language:** Thai language support

## Monitoring & Logging

### Application Logs
View logs in real-time:
```bash
docker-compose logs -f app
```

### Database Monitoring
Check database performance:
```bash
docker exec -it zkteco-adms-db psql -U adms_user -d adms_db -c "SELECT * FROM get_device_stats();"
```

### Health Checks
- App health: `http://localhost:8080/health`
- Database health: Included in health endpoint response

## Troubleshooting

### Common Issues

1. **Database connection failed**
   ```bash
   docker-compose logs db
   docker-compose restart db
   ```

2. **App can't connect to database**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

3. **Device not sending data**
   - Check device network settings
   - Verify server IP/port configuration
   - Check logs: `docker-compose logs -f app`

### Data Backup

```bash
# Backup database
docker exec zkteco-adms-db pg_dump -U adms_user adms_db > backup.sql

# Restore database
docker exec -i zkteco-adms-db psql -U adms_user adms_db < backup.sql
```