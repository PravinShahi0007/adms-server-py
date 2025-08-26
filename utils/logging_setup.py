"""
Logging configuration for ZKTeco ADMS Server

Centralizes logging setup and configuration.
Extracted from main.py to improve code organization.
"""

import logging
from .config import config


def setup_logging():
    """Setup logging configuration"""
    # Enhanced logging configuration
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set uvicorn logger to show more details
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(logging.DEBUG)
    
    # Log invalid HTTP requests from uvicorn
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.setLevel(logging.INFO)
    
    return logging.getLogger(__name__)