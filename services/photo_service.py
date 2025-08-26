"""
PhotoService - Handles all photo management for ZKTeco ADMS Server

This service manages photo uploads, storage, and matching with attendance records.
Extracted from main.py to improve code organization.
"""

import os
import logging
import re
import glob
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class PhotoService:
    """Service for managing photo uploads and matching"""
    
    def __init__(self):
        self.env = os.getenv("ENVIRONMENT", "local")
        if self.env == "production":
            self.photo_base = "/app/photos"  # Maps to /mnt/kpspdrive/attendance_photo
        else:
            self.photo_base = "/app/photos"  # Maps to ./photos for local
    
    async def save_photo(self, photo_file, photo_filename: str, device_serial: str) -> Optional[str]:
        """Save photo from form upload data"""
        try:
            if not photo_file:
                logger.error("No photo file provided")
                return None
                
            # Read photo content
            photo_data = await photo_file.read()
            
            # Create directory structure: photos/device_serial/YYYY-MM-DD/
            # Extract timestamp from filename: YYYYMMDDHHMISS-XX.jpg
            match = re.match(r'(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})-(\d+)\.jpg', photo_filename)
            if match:
                year, month, day = match.groups()[:3]
                date_folder = f"{year}-{month}-{day}"
            else:
                # Fallback to current date
                date_folder = datetime.now().strftime("%Y-%m-%d")
            
            photo_dir = f"photos/{device_serial}/{date_folder}"
            os.makedirs(photo_dir, exist_ok=True)
            
            # Save photo file
            photo_path = f"{photo_dir}/{photo_filename}"
            with open(photo_path, 'wb') as f:
                f.write(photo_data)
            
            logger.info(f"Saved photo: {photo_path}")
            return photo_path
            
        except Exception as e:
            logger.error(f"Error saving photo: {e}")
            return None
    
    async def save_photo_file(self, raw_data: bytes, device_serial: str, photo_filename: str, photo_info: dict) -> Optional[str]:
        """Save photo file to NAS storage"""
        try:
            # Find where JPEG data starts (after metadata lines)
            data_text = raw_data.decode('utf-8', errors='ignore')
            jpeg_start = data_text.find('\x00\xff\xd8\xff')  # JPEG file signature
            
            if jpeg_start == -1:
                # Alternative search for JPEG header
                jpeg_start = raw_data.find(b'\xff\xd8\xff')
                if jpeg_start != -1:
                    jpeg_data = raw_data[jpeg_start:]
                else:
                    logger.error(f"Could not find JPEG data in photo upload")
                    return None
            else:
                jpeg_data = raw_data[jpeg_start + 1:]  # Skip the null byte
            
            # Create directory structure: photos/device_serial/YYYY-MM-DD/
            today = datetime.now().strftime("%Y-%m-%d")
            photo_dir = f"{self.photo_base}/{device_serial}/{today}"
            
            # Create directory if it doesn't exist
            os.makedirs(photo_dir, exist_ok=True)
            
            # Clean filename for filesystem
            safe_filename = re.sub(r'[^\w\-_.]', '_', photo_filename)
            if not safe_filename.lower().endswith('.jpg'):
                safe_filename += '.jpg'
            
            photo_path = f"{photo_dir}/{safe_filename}"
            
            # Save JPEG data to file
            with open(photo_path, 'wb') as f:
                f.write(jpeg_data)
            
            logger.info(f"Saved photo: {photo_path} ({len(jpeg_data)} bytes)")
            return photo_path
            
        except Exception as e:
            logger.error(f"Failed to save photo file: {e}")
            return None
    
    def find_latest_photo(self, device_serial: str, user_id: str, timestamp_str: str) -> Optional[str]:
        """Find the most recent photo for a user around the time of attendance"""
        try:
            # Parse timestamp
            attendance_time = datetime.fromisoformat(timestamp_str.replace(' ', 'T'))
            date_str = attendance_time.strftime("%Y-%m-%d")
            
            # Check photos directory
            photo_dir = f"{self.photo_base}/{device_serial}/{date_str}"
            
            if not os.path.exists(photo_dir):
                return None
                
            # Look for photos with exact user_id match at the end of filename
            # First priority: Find photos that end with -{user_id}.jpg
            photos = glob.glob(f"{photo_dir}/*-{user_id}.jpg")
            
            if photos:
                # Sort by filename timestamp (most recent first)
                photos.sort(reverse=True)
                
                # Find photo closest to attendance time (within 3 minutes)
                for photo in photos:
                    # Extract timestamp from filename: YYYYMMDDHHMISS-{user_id}.jpg
                    filename = os.path.basename(photo)
                    match = re.match(r'(\d{14})-\d+\.jpg', filename)
                    if match:
                        photo_time_str = match.group(1)
                        try:
                            photo_time = datetime.strptime(photo_time_str, "%Y%m%d%H%M%S")
                            time_diff = abs((attendance_time - photo_time).total_seconds())
                            
                            # Return photo if within 3 minutes (180 seconds)
                            if time_diff <= 180:
                                return photo
                        except ValueError:
                            continue
                
                # If no photo within 3 minutes, don't return old photos
                # This prevents mixing up old photos with new attendance
                
            return None
        except Exception as e:
            logger.error(f"Error finding photo: {e}")
            return None