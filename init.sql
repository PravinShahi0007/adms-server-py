-- ZKTeco ADMS Database Initialization Script
-- This script creates indexes and initial data for optimal performance

-- Create indexes for better query performance (if not already created by SQLAlchemy)
CREATE INDEX IF NOT EXISTS idx_devices_serial_active ON devices(serial_number, is_active);
CREATE INDEX IF NOT EXISTS idx_attendance_user_timestamp ON attendance_records(user_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_attendance_device_timestamp ON attendance_records(device_serial, timestamp);
CREATE INDEX IF NOT EXISTS idx_attendance_processed_created ON attendance_records(processed, created_at);
CREATE INDEX IF NOT EXISTS idx_device_logs_type_created ON device_logs(event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_device_logs_serial_created ON device_logs(device_serial, created_at);
CREATE INDEX IF NOT EXISTS idx_queue_status_created ON processing_queue(status, created_at);

-- Create a function to clean old logs (optional)
CREATE OR REPLACE FUNCTION clean_old_logs(days_to_keep INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM device_logs 
    WHERE created_at < NOW() - INTERVAL '1 day' * days_to_keep;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create a function to get device statistics
CREATE OR REPLACE FUNCTION get_device_stats(device_sn VARCHAR DEFAULT NULL)
RETURNS TABLE(
    serial_number VARCHAR,
    total_records BIGINT,
    last_record_time TIMESTAMP WITH TIME ZONE,
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    is_online BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.serial_number,
        COALESCE(COUNT(ar.id), 0) as total_records,
        MAX(ar.timestamp) as last_record_time,
        d.last_heartbeat,
        (d.last_heartbeat > NOW() - INTERVAL '5 minutes') as is_online
    FROM devices d
    LEFT JOIN attendance_records ar ON d.serial_number = ar.device_serial
    WHERE (device_sn IS NULL OR d.serial_number = device_sn)
    GROUP BY d.serial_number, d.last_heartbeat, d.is_active
    ORDER BY d.last_heartbeat DESC;
END;
$$ LANGUAGE plpgsql;

-- Insert some sample data for testing (optional)
-- INSERT INTO devices (serial_number, name, ip_address, model) 
-- VALUES ('TEST001', 'Test Device 1', '192.168.1.100', 'ZKTeco F18') 
-- ON CONFLICT (serial_number) DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO adms_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO adms_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO adms_user;