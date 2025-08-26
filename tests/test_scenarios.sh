#!/bin/bash

# ZKTeco ADMS Event-Driven Test Scenarios
# =========================================

SERVER_URL="http://localhost:8080"
PHOTO_FILE="IMG_1030.jpg"
DEVICE_SN="TEST123"

echo "🚀 ZKTeco ADMS Event-Driven Test Scenarios"
echo "=========================================="

# Function to generate timestamp
get_timestamp() {
    date +"%Y-%m-%d %H:%M:%S"
}

# Function to generate filename timestamp
get_filename_timestamp() {
    date +"%Y%m%d%H%M%S"
}

# Test Scenario 1: Event-Driven (Photo after Attendance)
test_event_driven() {
    echo ""
    echo "📋 Test 1: Event-Driven (รูปมาหลัง attendance)"
    echo "============================================"
    
    USER_ID="101"
    TIMESTAMP=$(get_timestamp)
    FILENAME_TS=$(get_filename_timestamp)
    
    echo "👤 User: $USER_ID"
    echo "⏰ Sending attendance first..."
    
    # Send attendance
    curl -X POST "$SERVER_URL/iclock/cdata?SN=$DEVICE_SN" \
         -H "Content-Type: text/plain" \
         --data "ATTLOG	$USER_ID	$TIMESTAMP	1	0	0" \
         -w "\n⏱️  Attendance Response Time: %{time_total}s\n"
    
    echo "⏳ Waiting 3 seconds before sending photo..."
    sleep 3
    
    echo "📷 Sending photo (should trigger immediate Event-Driven notification)..."
    
    # Send photo
    curl -X POST "$SERVER_URL/iclock/cdata" \
         -F "sn=$DEVICE_SN" \
         -F "table=ATTPHOTO" \
         -F "stamps=${FILENAME_TS}-${USER_ID}.jpg" \
         -F "photodata=@$PHOTO_FILE" \
         -w "\n⏱️  Photo Response Time: %{time_total}s\n"
    
    echo "✅ Event-Driven test completed - Check Telegram for IMMEDIATE notification!"
}

# Test Scenario 2: 60-Second Timeout (Text-only notification)
test_timeout() {
    echo ""
    echo "📋 Test 2: 60-Second Timeout (Text-only notification)"
    echo "==================================================="
    
    USER_ID="102"
    TIMESTAMP=$(get_timestamp)
    
    echo "👤 User: $USER_ID"
    echo "⏰ Sending attendance (NO photo will be sent)..."
    
    # Send attendance only
    curl -X POST "$SERVER_URL/iclock/cdata?SN=$DEVICE_SN" \
         -H "Content-Type: text/plain" \
         --data "ATTLOG	$USER_ID	$TIMESTAMP	1	1	0" \
         -w "\n⏱️  Attendance Response Time: %{time_total}s\n"
    
    echo "⏳ Waiting for 60-second timeout..."
    echo "📱 You should receive a TEXT-ONLY notification after 60 seconds"
    echo "💡 Cancel with Ctrl+C if you don't want to wait"
    
    # Wait and show countdown
    for i in {60..1}; do
        echo -ne "\r⏱️  Timeout in: ${i}s   "
        sleep 1
    done
    echo -ne "\r✅ 60-second timeout completed!              \n"
}

# Test Scenario 3: Photo Before Attendance
test_photo_first() {
    echo ""
    echo "📋 Test 3: Photo Before Attendance (instant notification)"
    echo "======================================================="
    
    USER_ID="103"
    TIMESTAMP=$(get_timestamp)
    FILENAME_TS=$(get_filename_timestamp)
    
    echo "👤 User: $USER_ID"
    echo "📷 Sending photo FIRST..."
    
    # Send photo first
    curl -X POST "$SERVER_URL/iclock/cdata" \
         -F "sn=$DEVICE_SN" \
         -F "table=ATTPHOTO" \
         -F "stamps=${FILENAME_TS}-${USER_ID}.jpg" \
         -F "photodata=@$PHOTO_FILE" \
         -w "\n⏱️  Photo Response Time: %{time_total}s\n"
    
    echo "⏳ Waiting 5 seconds before sending attendance..."
    sleep 5
    
    echo "⏰ Sending attendance (should trigger INSTANT notification)..."
    
    # Send attendance
    curl -X POST "$SERVER_URL/iclock/cdata?SN=$DEVICE_SN" \
         -H "Content-Type: text/plain" \
         --data "ATTLOG	$USER_ID	$TIMESTAMP	1	0	0" \
         -w "\n⏱️  Attendance Response Time: %{time_total}s\n"
    
    echo "✅ Photo-first test completed - Check Telegram for INSTANT notification!"
}

# Test Scenario 4: Rapid-Fire Multiple Users
test_rapid_fire() {
    echo ""
    echo "📋 Test 4: Rapid-Fire Multiple Users"
    echo "===================================="
    
    echo "🔥 Sending multiple users rapidly with mixed scenarios..."
    
    FILENAME_TS=$(get_filename_timestamp)
    
    # User 201: Event-Driven (2s delay)
    echo "👤 User 201: Event-Driven scenario"
    curl -X POST "$SERVER_URL/iclock/cdata?SN=$DEVICE_SN" \
         -H "Content-Type: text/plain" \
         --data "ATTLOG	201	$(get_timestamp)	1	0	0" &
    
    sleep 2
    
    curl -X POST "$SERVER_URL/iclock/cdata" \
         -F "sn=$DEVICE_SN" \
         -F "table=ATTPHOTO" \
         -F "stamps=${FILENAME_TS}-201.jpg" \
         -F "photodata=@$PHOTO_FILE" &
    
    # User 202: Photo first
    echo "👤 User 202: Photo first scenario"
    curl -X POST "$SERVER_URL/iclock/cdata" \
         -F "sn=$DEVICE_SN" \
         -F "table=ATTPHOTO" \
         -F "stamps=${FILENAME_TS}-202.jpg" \
         -F "photodata=@$PHOTO_FILE" &
    
    sleep 1
    
    curl -X POST "$SERVER_URL/iclock/cdata?SN=$DEVICE_SN" \
         -H "Content-Type: text/plain" \
         --data "ATTLOG	202	$(get_timestamp)	1	1	0" &
    
    # User 203: Only attendance (will timeout)
    echo "👤 User 203: Timeout scenario"
    curl -X POST "$SERVER_URL/iclock/cdata?SN=$DEVICE_SN" \
         -H "Content-Type: text/plain" \
         --data "ATTLOG	203	$(get_timestamp)	1	0	0" &
    
    wait
    echo "✅ Rapid-fire test completed - Check Telegram for multiple notifications!"
}

# Test Scenario 5: Health Check
test_health() {
    echo ""
    echo "📋 Test 5: System Health Check"
    echo "==============================="
    
    echo "🏥 Checking system health..."
    curl -X GET "$SERVER_URL/health" -w "\n⏱️  Response Time: %{time_total}s\n"
}

# Main menu
show_menu() {
    echo ""
    echo "🎯 Select test scenario:"
    echo "========================"
    echo "1) Event-Driven (Photo after Attendance) - ⚡ Fast"
    echo "2) 60-Second Timeout (Text-only) - ⏳ Slow"  
    echo "3) Photo Before Attendance - ⚡ Instant"
    echo "4) Rapid-Fire Multiple Users - 🔥 Stress"
    echo "5) Health Check - 🏥 Quick"
    echo "6) Run All Tests - 🧪 Complete"
    echo "0) Exit"
    echo ""
    read -p "Enter choice [0-6]: " choice
}

# Detect script directory and set photo file path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
PHOTO_FILE="$SCRIPT_DIR/IMG_1030.jpg"

# Check if photo file exists
if [ ! -f "$PHOTO_FILE" ]; then
    echo "❌ Error: Photo file '$PHOTO_FILE' not found!"
    echo "💡 Please make sure 'IMG_1030.jpg' exists in tests/ directory"
    exit 1
fi

# Main loop
while true; do
    show_menu
    
    case $choice in
        1)
            test_event_driven
            ;;
        2)
            test_timeout
            ;;
        3)
            test_photo_first
            ;;
        4)
            test_rapid_fire
            ;;
        5)
            test_health
            ;;
        6)
            echo "🧪 Running ALL tests..."
            test_health
            test_event_driven
            test_photo_first
            test_rapid_fire
            echo "⚠️  Skipping timeout test (takes 60s) - run manually if needed"
            echo "✅ All tests completed!"
            ;;
        0)
            echo "👋 Goodbye!"
            exit 0
            ;;
        *)
            echo "❌ Invalid option. Please try again."
            ;;
    esac
    
    echo ""
    read -p "Press Enter to continue..."
done