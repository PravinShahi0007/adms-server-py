"""
Configuration management for ZKTeco ADMS Server

Centralizes all environment variables and configuration settings.
Extracted from main.py to improve code organization.
"""

import os
from typing import Optional


class Config:
    """Centralized configuration class for ZKTeco ADMS Server"""
    
    def __init__(self):
        # Server Configuration
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        
        # API Configuration  
        self.INTERNAL_API_URL = os.getenv("INTERNAL_API_URL", "http://localhost:3000")
        self.COMM_KEY = os.getenv("COMM_KEY", "")
        
        # Telegram Configuration
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.CHAT_ID = os.getenv('CHAT_ID')
        
        # Environment Configuration
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
        
        # Database Configuration (handled by database.py)
        # Photo Storage Configuration (handled by PhotoService)
    
    def validate_comm_key(self, request_key: Optional[str]) -> bool:
        """Validate communication key if configured"""
        if not self.COMM_KEY:  # No key required
            return True
        return request_key == self.COMM_KEY


# Global config instance
config = Config()