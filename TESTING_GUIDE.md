# 🧪 ZKTeco ADMS Event-Driven Testing Guide

สำหรับทดสอบระบบ Event-Driven attendance notifications

## 🚀 Quick Start

```bash
# Make script executable
chmod +x test_scenarios.sh

# Run interactive test menu
./test_scenarios.sh
```

## 📋 Test Scenarios

ทดสอบได้หลายรูปแบบผ่าน interactive menu:

### 1. 📱 Event-Driven (Photo after Attendance)
**Expected: ⚡ 3-5 second response**
- Choose option 1 in script menu

### 2. ⏳ 60-Second Timeout (Text-only) 
**Expected: 📝 Text-only after 60 seconds**
- Choose option 2 in script menu (be patient!)

### 3. ⚡ Photo Before Attendance (Instant)
**Expected: 🚀 Instant response**
- Choose option 3 in script menu

### 4. 🔥 Rapid-Fire Stress Test
**Expected: 🎯 All scenarios work concurrently**
- Choose option 4 in script menu

### 5. 🏥 Health Check
**Expected: ✅ System status**
- Choose option 5 in script menu

## 📊 Performance Expectations

| Scenario | Expected Response Time | Telegram Notification |
|----------|----------------------|---------------------|
| Event-Driven | 3-5 seconds | ✅ With photo |
| Photo First | Instant | ✅ With photo |
| 60s Timeout | 60 seconds | 📝 Text only |
| Health Check | < 1 second | ❌ None |

## 🔧 Configuration

### Required Files
- `IMG_1030.jpg` - Sample photo for testing (must exist)
- Docker containers running (`docker-compose up -d`)

### Environment Variables
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_GROUP_CHAT_ID=your_chat_id
```

## 🐛 Troubleshooting

### ❌ "Internal Server Error"
```bash
# Check logs
docker-compose logs app --tail 20
```

### ❌ "Photo file not found"
```bash
# Ensure IMG_1030.jpg exists
ls -la IMG_1030.jpg
```

### ❌ "No Telegram notification"
- Check bot token and chat ID in docker-compose.yml
- Verify bot is added to test chat
- Check logs for Telegram API errors

### ❌ "Database error"
```bash
# Restart containers
docker-compose down && docker-compose up -d
```

## 📝 Logs Monitoring

**Real-time logs:**
```bash
docker-compose logs app -f
```

**Key log messages:**
- `No photo found for X, adding to pending notifications...` - Event-Driven setup
- `Found pending notification for user X, triggering immediate notification` - Event-Driven trigger
- `Photo sent to Telegram chat` - Successful notification

## 🎯 Testing Tips

1. **Sequential Testing**: Test scenarios individually first
2. **Watch Logs**: Keep logs open to see Event-Driven triggers  
3. **Check Telegram**: Verify notifications arrive as expected
4. **Photo Files**: Use different user IDs for each test to avoid conflicts

---

**🎉 Happy Testing! ใช้ `test_scenarios.sh` สำหรับการทดสอบ!**