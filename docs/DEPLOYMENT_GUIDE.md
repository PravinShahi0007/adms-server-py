# ZKTeco ADMS Server - Deployment Guide

## 🚀 Overview

This guide covers deployment options for ZKTeco ADMS Server from development to production environments.

## 🐳 Docker Deployment (Recommended)

### Prerequisites
- Docker Engine 20.0+
- Docker Compose 2.0+
- Minimum 2GB RAM, 10GB storage

### Quick Start

1. **Clone Repository**
```bash
git clone <repository-url>
cd adms-server
```

2. **Environment Configuration**
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Start Services**
```bash
docker-compose up -d
```

4. **Verify Deployment**
```bash
curl http://localhost:8080/health
```

### Docker Compose Services

#### Production Stack
```yaml
services:
  app:                    # FastAPI application
  postgres:              # PostgreSQL database
  nginx:                # Reverse proxy + SSL
  adminer:              # Database admin (optional)
```

#### Service Configuration

**App Service:**
```yaml
app:
  build: .
  ports:
    - "8080:8080"
  environment:
    - DATABASE_URL=postgresql://user:pass@postgres:5432/adms
    - TELEGRAM_BOT_TOKEN=your_bot_token
    - CHAT_ID=your_chat_id
  volumes:
    - ./photos:/app/photos
  depends_on:
    - postgres
```

**Database Service:**
```yaml
postgres:
  image: postgres:15
  environment:
    - POSTGRES_DB=adms
    - POSTGRES_USER=adms_user
    - POSTGRES_PASSWORD=secure_password
  volumes:
    - postgres_data:/var/lib/postgresql/data
```

**Nginx Service:**
```yaml
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf
    - ./ssl:/etc/nginx/ssl
```

## 🔧 Environment Configuration

### Required Variables

```bash
# Database
DATABASE_URL=postgresql://username:password@host:5432/database

# Telegram Integration
TELEGRAM_BOT_TOKEN=1234567890:ABCDefGhIjKlMnOpQrStUvWxYz
CHAT_ID=-1001234567890

# Security (Optional)
COMM_KEY=your-secure-communication-key

# Internal API (Optional)
INTERNAL_API_URL=http://your-internal-api:3000

# Logging
LOG_LEVEL=INFO

# Storage
PHOTO_STORAGE_PATH=/app/photos
```

### Optional Variables

```bash
# Performance
WORKERS=4                    # Gunicorn workers
MAX_CONNECTIONS=100          # Database connection pool

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=9090

# Development
DEBUG=false
RELOAD=false
```

## 🌐 Production Deployment

### 1. Server Requirements

**Minimum:**
- 2 CPU cores
- 4GB RAM
- 50GB storage
- Ubuntu 20.04+ or CentOS 8+

**Recommended:**
- 4 CPU cores
- 8GB RAM
- 100GB SSD storage
- Load balancer ready

### 2. Security Setup

#### SSL/TLS Configuration
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    location / {
        proxy_pass http://app:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Firewall Rules
```bash
# Allow SSH
ufw allow 22/tcp

# Allow HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Database (internal only)
ufw allow from 172.18.0.0/16 to any port 5432

# Enable firewall
ufw --force enable
```

### 3. Database Setup

#### PostgreSQL Configuration
```sql
-- Create database and user
CREATE DATABASE adms;
CREATE USER adms_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE adms TO adms_user;

-- Performance tuning
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
```

#### Database Backup
```bash
# Automated backup script
#!/bin/bash
BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)

pg_dump -h postgres -U adms_user adms > $BACKUP_DIR/adms_$DATE.sql
find $BACKUP_DIR -name "adms_*.sql" -mtime +7 -delete
```

### 4. Monitoring & Logging

#### Health Check Script
```bash
#!/bin/bash
HEALTH_URL="http://localhost:8080/health"
RESPONSE=$(curl -s $HEALTH_URL | jq -r '.status')

if [ "$RESPONSE" != "healthy" ]; then
    echo "Service unhealthy, restarting..."
    docker-compose restart app
    # Send alert notification
fi
```

#### Log Management
```yaml
# docker-compose.yml logging configuration
services:
  app:
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"
```

## 🔄 CI/CD Pipeline

### GitHub Actions Example

```yaml
name: Deploy to Production

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to server
      uses: appleboy/ssh-action@v0.1.5
      with:
        host: ${{ secrets.HOST }}
        username: ${{ secrets.USERNAME }}
        key: ${{ secrets.SSH_KEY }}
        script: |
          cd /opt/adms-server
          git pull origin main
          docker-compose down
          docker-compose build --no-cache
          docker-compose up -d
          
    - name: Health Check
      run: |
        sleep 30
        curl -f http://${{ secrets.HOST }}/health || exit 1
```

### GitLab CI Example

```yaml
stages:
  - test
  - build
  - deploy

test:
  stage: test
  script:
    - python -m pytest tests/

build:
  stage: build
  script:
    - docker build -t adms-server:$CI_COMMIT_SHA .
    
deploy:
  stage: deploy
  script:
    - docker-compose down
    - docker-compose up -d
  only:
    - main
```

## 📊 Load Balancer Setup

### Nginx Load Balancer
```nginx
upstream adms_backend {
    server adms-app-1:8080;
    server adms-app-2:8080;
    server adms-app-3:8080;
}

server {
    listen 80;
    location / {
        proxy_pass http://adms_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Docker Swarm (Optional)
```yaml
version: '3.8'
services:
  app:
    image: adms-server:latest
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
    networks:
      - adms-network
```

## 🔍 Troubleshooting

### Common Issues

#### 1. Database Connection Errors
```bash
# Check database connectivity
docker-compose exec app python -c "
from database import engine
try:
    engine.connect()
    print('Database OK')
except Exception as e:
    print(f'Database Error: {e}')
"
```

#### 2. Photo Storage Issues
```bash
# Check photo directory permissions
ls -la photos/
# Should show: drwxrwxr-x app app photos/

# Fix permissions
sudo chown -R app:app photos/
sudo chmod -R 755 photos/
```

#### 3. Telegram Bot Issues
```bash
# Test bot token
curl "https://api.telegram.org/bot<TOKEN>/getMe"

# Test chat access
curl "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d "chat_id=<CHAT_ID>&text=Test message"
```

#### 4. High Memory Usage
```bash
# Monitor container resources
docker stats

# Check for memory leaks
docker-compose exec app python -c "
import psutil
process = psutil.Process()
print(f'Memory: {process.memory_info().rss / 1024 / 1024:.2f} MB')
"
```

### Log Analysis

```bash
# View application logs
docker-compose logs -f app

# Filter for errors
docker-compose logs app | grep ERROR

# Database logs
docker-compose logs postgres

# Real-time monitoring
docker-compose logs -f --tail=100 app
```

## 📋 Maintenance

### Regular Tasks

#### Daily
- Monitor health endpoint
- Check log file sizes
- Verify backup completion

#### Weekly
- Review error logs
- Update security patches
- Performance monitoring

#### Monthly
- Database maintenance
- Photo storage cleanup
- Security audit

### Backup Strategy

```bash
#!/bin/bash
# Full backup script

# Database backup
pg_dump -h postgres -U adms_user adms > backup/db_$(date +%Y%m%d).sql

# Photo backup
tar -czf backup/photos_$(date +%Y%m%d).tar.gz photos/

# Config backup
tar -czf backup/config_$(date +%Y%m%d).tar.gz .env docker-compose.yml

# Cleanup old backups (keep 30 days)
find backup/ -type f -mtime +30 -delete
```

### Update Procedure

```bash
# 1. Create backup
./backup.sh

# 2. Pull updates
git pull origin main

# 3. Update containers
docker-compose down
docker-compose build --no-cache  
docker-compose up -d

# 4. Verify deployment
curl http://localhost:8080/health

# 5. Monitor logs
docker-compose logs -f app
```

## 🎯 Performance Optimization

### Database Tuning
```sql
-- Index optimization
CREATE INDEX CONCURRENTLY idx_attendance_timestamp 
ON attendance_records(timestamp);

CREATE INDEX CONCURRENTLY idx_device_serial 
ON attendance_records(device_serial);

-- Connection pooling
ALTER SYSTEM SET max_connections = '200';
ALTER SYSTEM SET shared_buffers = '512MB';
```

### Application Tuning
```yaml
# docker-compose.yml
app:
  environment:
    - WORKERS=4                    # Match CPU cores
    - MAX_CONNECTIONS=50          # Database pool size
    - WORKER_CLASS=uvicorn.workers.UvicornWorker
```

### Resource Monitoring
```bash
# Container resource usage
docker stats --no-stream

# Database performance
docker-compose exec postgres psql -U adms_user -d adms -c "
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY total_time DESC LIMIT 10;
"
```

This deployment guide ensures reliable, secure, and scalable deployment of the ZKTeco ADMS Server across different environments.