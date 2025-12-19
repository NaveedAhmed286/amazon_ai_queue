import os
import logging
import sys

def setup_logger():
    """Setup resilient application logger that won't crash"""
    logger = logging.getLogger("amazon_ai_agent")
    
    # SAFELY get log level - default to INFO
    try:
        log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        
        # Map string to integer level SAFELY
        level_map = {
            "DEBUG": 10,     # logging.DEBUG
            "INFO": 20,      # logging.INFO  
            "WARNING": 30,   # logging.WARNING
            "ERROR": 40,     # logging.ERROR
            "CRITICAL": 50   # logging.CRITICAL
        }
        
        # Get level or default to INFO (20)
        log_level = level_map.get(log_level_str, 20)
        
        # Ensure it's an integer
        log_level = int(log_level)
        
    except Exception:
        # If anything fails, use INFO (20)
        log_level = 20
    
    # SAFELY set level
    try:
        logger.setLevel(log_level)
    except Exception as e:
        # If setLevel fails, use basic config
        logging.basicConfig(level=log_level)
        logger.setLevel(log_level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create simple handler that won't crash
    handler = logging.StreamHandler(sys.stdout)
    
    # Simple formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    # Add handler
    logger.addHandler(handler)
    
    # Don't propagate to avoid double logging
    logger.propagate = False
    
    # Log success
    logger.info(f"✅ Logger initialized successfully at level: {log_level}")
    
    return logger

# Create global logger instance
logger = setup_logger()

# Also configure root logger to catch any stray logs
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - ROOT - %(levelname)s - %(message)s'
)
