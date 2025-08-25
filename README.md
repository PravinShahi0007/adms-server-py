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

### Environment Configuration

Create `.env` file (copy from `.env.example`):
```bash
cp .env.example .env
# Edit .env with your settings
```

### Production Docker Compose

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  app:
    build: .
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/adms_db
      - INTERNAL_API_URL=https://your-api.com
      - LOG_LEVEL=INFO
    ports:
      - "8080:8080"
    restart: always
    depends_on:
      - db
  
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: adms_db
      POSTGRES_USER: user
      POSTGRES_PASSWORD: strong_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://adms_user:adms_password@localhost:5432/adms_db` |
| `INTERNAL_API_URL` | Your internal API endpoint | `http://localhost:3000` |
| `COMM_KEY` | Device communication key | `""` |
| `LOG_LEVEL` | Logging level | `INFO` |

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