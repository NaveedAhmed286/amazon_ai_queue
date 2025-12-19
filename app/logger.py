import os
import logging
import sys
from datetime import datetime

def setup_logger():
    """Setup resilient application logger"""
    logger = logging.getLogger("amazon_ai_agent")
    
    # Get log level from environment or default to INFO
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Map string level to logging constant
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    
    # Use INFO if level not found in map
    log_level_num = level_map.get(log_level, logging.INFO)
    logger.setLevel(log_level_num)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level_num)
    
    # Formatter with colors for better readability
    class CustomFormatter(logging.Formatter):
        """Custom formatter with colors"""
        grey = "\x1b[38;20m"
        yellow = "\x1b[33;20m"
        red = "\x1b[31;20m"
        bold_red = "\x1b[31;1m"
        reset = "\x1b[0m"
        format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        
        FORMATS = {
            logging.DEBUG: grey + format_str + reset,
            logging.INFO: grey + format_str + reset,
            logging.WARNING: yellow + format_str + reset,
            logging.ERROR: red + format_str + reset,
            logging.CRITICAL: bold_red + format_str + reset
        }
        
        def format(self, record):
            log_fmt = self.FORMATS.get(record.levelno, self.format_str)
            formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
            return formatter.format(record)
    
    # Use custom formatter
    formatter = CustomFormatter()
    console_handler.setFormatter(formatter)
    
    # Add handler
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    # Log initialization
    logger.info(f"Logger initialized with level: {log_level}")
    
    return logger

# Create global logger instance
logger = setup_logger()

# Also set up root logger to catch any unhandled logs
root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)  # Only warnings and above for root
