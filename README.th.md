# ZKTeco ADMS Push Server

เซิร์ฟเวอร์ FastAPI สำหรับรับข้อมูลการเข้า-ออกงานจากเครื่อง ZKTeco ด้วยโหมด Push/ADMS พร้อมฐานข้อมูล PostgreSQL

## คุณสมบัติ

- รองรับโปรโตคอล ZKTeco Push SDK (`/iclock/*` endpoints)
- ฐานข้อมูล PostgreSQL สำหรับจัดเก็บข้อมูล
- แปลงและบันทึกข้อมูล ATTLOG records
- ติดตามการลงทะเบียนและ heartbeat ของเครื่อง
- ส่งต่อข้อมูลไปยัง Internal API
- ตรวจสอบสถานะระบบและฐานข้อมูล
- บันทึก log และ audit trail ครบถ้วน
- ใช้ Docker containerization
- Adminer web interface สำหรับจัดการฐานข้อมูล

## เริ่มต้นใช้งานด้วย Docker

1. Clone และเข้าไปยังโปรเจ็ค:
```bash
git clone https://github.com/taesaeng28/adms-server.git
cd adms-server
```

2. เริ่มต้น services:
```bash
docker-compose up -d
```

จะเริ่มต้น services ดังนี้:
- **App**: `http://localhost:8080` - FastAPI server
- **Database**: `localhost:5432` - PostgreSQL 
- **Adminer**: `http://localhost:8081` - Web interface สำหรับจัดการฐานข้อมูล

## การติดตั้งแบบ Manual

1. ติดตั้ง dependencies:
```bash
pip install -r requirements.txt
```

2. ตั้งค่า environment variables:
```bash
export DATABASE_URL="postgresql://adms_user:adms_password@localhost:5432/adms_db"
export INTERNAL_API_URL="http://your-api:3000"
export COMM_KEY="your-comm-key"
```

3. เริ่มต้น server:
```bash
python main.py
```

## การตั้งค่าเครื่อง ZKTeco

ตั้งค่าเครื่อง ZKTeco ของคุณ:

1. **การตั้งค่าเครือข่าย**: ตั้งค่า IP, Gateway, TCP port (มักจะเป็น 4370)
2. **การตั้งค่า ADMS/Push**:
   - Server Address: `ip-ของ-server-คุณ`
   - Server Port: `8080` (หรือพอร์ตที่คุณใช้)
   - Comm Key: (ถ้าใช้ authentication)

## API Endpoints

### การสื่อสารกับเครื่อง

- `GET /iclock/getrequest?SN=<serial>` - Device heartbeat/ตรวจสอบคำสั่ง
- `POST /iclock/cdata` - อัปโหลดข้อมูลการเข้า-ออกงาน
- `GET|POST /iclock/register?SN=<serial>` - การลงทะเบียนเครื่อง

### การติดตาม

- `GET /health` - ตรวจสอบสถานะระบบ

## รูปแบบ ATTLOG

เครื่องจะส่งข้อมูลการเข้า-ออกงานในรูปแบบ:
```
ATTLOG\tuser_id\ttimestamp\tverify_mode\tin_out\tworkcode
```

ตัวอย่าง:
```
ATTLOG	1001	2025-08-25 09:00:01	1	0	0
```

ฟิลด์ต่างๆ:
- `user_id`: รหัสพนักงาน
- `timestamp`: เวลาที่เข้า-ออกงาน
- `verify_mode`: วิธีการยืนยันตัวตน (1=ลายนิ้วมือ, ฯลฯ)
- `in_out`: ประเภทการเข้า-ออก (0=เข้า, 1=ออก)
- `workcode`: รหัสงาน (ถ้ามี)

## การทดสอบ

ทดสอบ endpoints ด้วยตนเอง:

```bash
# ทดสอบ heartbeat
curl "http://localhost:8080/iclock/getrequest?SN=TEST123"

# ทดสอบการอัปโหลดข้อมูลการเข้า-ออกงาน
curl -X POST "http://localhost:8080/iclock/cdata?SN=TEST123" \
  --data-binary $'ATTLOG\t1001\t2025-08-25 09:00:01\t1\t0\t0'

# ทดสอบการลงทะเบียน
curl "http://localhost:8080/iclock/register?SN=TEST123"

# ตรวจสอบสถานะ
curl "http://localhost:8080/health"
```

## การจัดการฐานข้อมูล

### การเข้าถึงฐานข้อมูล

**ผ่าน Adminer (Web Interface):**
- URL: `http://localhost:8081`
- ระบบ: PostgreSQL
- Server: `db`
- Username: `adms_user`
- Password: `adms_password`
- Database: `adms_db`

**ผ่าน psql (Command Line):**
```bash
docker exec -it zkteco-adms-db psql -U adms_user -d adms_db
```

### โครงสร้างฐานข้อมูล

**ตารางต่างๆ:**
- `devices` - การลงทะเบียนและสถานะเครื่อง
- `attendance_records` - ข้อมูลการเข้า-ออกงานจากเครื่อง
- `device_logs` - บันทึกกิจกรรมของเครื่อง
- `processing_queue` - คิวสำหรับประมวลผลข้อมูล

**คำสั่ง SQL ที่มีประโยชน์:**
```sql
-- ดูสถิติเครื่อง
SELECT * FROM get_device_stats();

-- ดูข้อมูลการเข้า-ออกงานล่าสุด
SELECT * FROM attendance_records ORDER BY timestamp DESC LIMIT 10;

-- ตรวจสอบกิจกรรมเครื่อง
SELECT * FROM device_logs WHERE event_type = 'heartbeat' 
ORDER BY created_at DESC LIMIT 10;
```

## การใช้งานใน Production

### การตั้งค่า Environment

สร้างไฟล์ `.env` (คัดลอกจาก `.env.example`):
```bash
cp .env.example .env
# แก้ไข .env ตามการตั้งค่าของคุณ
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

## ตัวแปร Environment

| ตัวแปร | รายละเอียด | ค่าเริ่มต้น |
|--------|------------|-------------|
| `DATABASE_URL` | Connection string ของ PostgreSQL | `postgresql://adms_user:adms_password@localhost:5432/adms_db` |
| `INTERNAL_API_URL` | API endpoint ปลายทางของคุณ | `http://localhost:3000` |
| `COMM_KEY` | รหัสสื่อสารกับเครื่อง | `""` |
| `LOG_LEVEL` | ระดับการบันทึก log | `INFO` |

## การติดตาม & Logging

### Application Logs
ดู logs แบบ real-time:
```bash
docker-compose logs -f app
```

### การติดตามฐานข้อมูล
ตรวจสอบ performance ของฐานข้อมูล:
```bash
docker exec -it zkteco-adms-db psql -U adms_user -d adms_db -c "SELECT * FROM get_device_stats();"
```

### Health Checks
- สถานะ App: `http://localhost:8080/health`
- สถานะฐานข้อมูล: รวมอยู่ใน health endpoint response

## การแก้ปัญหา

### ปัญหาที่พบบ่อย

1. **ฐานข้อมูลเชื่อมต่อไม่ได้**
   ```bash
   docker-compose logs db
   docker-compose restart db
   ```

2. **App เชื่อมต่อฐานข้อมูลไม่ได้**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

3. **เครื่องไม่ส่งข้อมูล**
   - ตรวจสอบการตั้งค่าเครือข่ายของเครื่อง
   - ตรวจสอบการตั้งค่า server IP/port
   - ดู logs: `docker-compose logs -f app`

### การสำรองข้อมูล

```bash
# สำรองฐานข้อมูล
docker exec zkteco-adms-db pg_dump -U adms_user adms_db > backup.sql

# คืนค่าฐานข้อมูล
docker exec -i zkteco-adms-db psql -U adms_user adms_db < backup.sql
```

## การสนับสนุน

หากพบปัญหาหรือต้องการความช่วยเหลือ:
- เปิด issue ใน GitHub repository
- ตรวจสอบ logs สำหรับข้อผิดพลาด
- ใช้ Adminer เพื่อตรวจสอบข้อมูลในฐานข้อมูล

---

📖 **[English Documentation](README.md)** | 🇹🇭 **ไทย**