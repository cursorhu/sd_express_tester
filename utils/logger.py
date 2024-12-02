import logging
import os
import sys
from datetime import datetime

def get_app_dir():
    """Get application directory"""
    if getattr(sys, 'frozen', False):
        # If running as executable
        return os.path.dirname(sys.executable)
    else:
        # If in development environment
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def setup_logger(level=logging.INFO):
    """Setup logger, avoid duplicate handlers"""
    logger = logging.getLogger('sd_express_tester')
    
    # If logger already has handlers, it's already initialized
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # Create logs directory
    log_dir = os.path.join(get_app_dir(), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure log filename (by date and time)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f'sd_express_tester_{timestamp}.log')
    
    # Create file handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set formatter
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Write initial log entries
    logger.info("="*50)
    logger.info("Program started")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Log level: {logging.getLevelName(level)}")
    logger.info("="*50)
    
    return logger

# Global logger instance
logger = setup_logger()

def get_logger(name=None):
    """Get logger instance"""
    if name:
        child_logger = logging.getLogger(name)
        # Ensure child logger inherits settings from parent logger
        child_logger.parent = logger
        return child_logger
    return logger

def update_log_level(level):
    """Update log level"""
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    level_num = level_map.get(level.upper(), logging.INFO)
    logger.setLevel(level_num)
    for handler in logger.handlers:
        handler.setLevel(level_num)
    logger.info(f"Log level updated to: {level}") 