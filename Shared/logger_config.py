"""
Logger Configuration - Centralized logging setup for the entire system
"""

import logging
import logging.handlers
import os
from pathlib import Path
from datetime import datetime

def setup_logging(name: str = None) -> logging.Logger:
    """Setup comprehensive logging configuration"""
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Get logger
    logger = logging.getLogger(name or __name__)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)
    
    # Main log file (all operations)
    main_handler = logging.handlers.RotatingFileHandler(
        log_dir / "scraper_main.log",
        maxBytes=50*1024*1024,  # 50MB
        backupCount=5
    )
    main_handler.setLevel(logging.DEBUG)
    main_handler.setFormatter(detailed_formatter)
    logger.addHandler(main_handler)
    
    # Error log file (errors and warnings only)
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "errors.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=3
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(detailed_formatter)
    logger.addHandler(error_handler)
    
    # Performance log (timing and metrics)
    if name and any(keyword in name.lower() for keyword in ['processor', 'extractor', 'manager']):
        performance_handler = logging.handlers.RotatingFileHandler(
            log_dir / "performance.log",
            maxBytes=20*1024*1024,  # 20MB
            backupCount=3
        )
        performance_handler.setLevel(logging.INFO)
        performance_handler.setFormatter(detailed_formatter)
        
        # Create a filter for performance metrics
        class PerformanceFilter(logging.Filter):
            def filter(self, record):
                return any(keyword in record.getMessage().lower() 
                          for keyword in ['processing time', 'duration', 'completed', 'performance'])
        
        performance_handler.addFilter(PerformanceFilter())
        logger.addHandler(performance_handler)
    
    # Shopify operations log
    if name and 'shopify' in name.lower():
        shopify_handler = logging.handlers.RotatingFileHandler(
            log_dir / "shopify_operations.log",
            maxBytes=20*1024*1024,  # 20MB
            backupCount=3
        )
        shopify_handler.setLevel(logging.DEBUG)
        shopify_handler.setFormatter(detailed_formatter)
        logger.addHandler(shopify_handler)
    
    # Image processing log
    if name and 'image' in name.lower():
        image_handler = logging.handlers.RotatingFileHandler(
            log_dir / "image_processing.log",
            maxBytes=20*1024*1024,  # 20MB
            backupCount=3
        )
        image_handler.setLevel(logging.DEBUG)
        image_handler.setFormatter(detailed_formatter)
        logger.addHandler(image_handler)
    
    # Pattern learning log
    if name and 'pattern' in name.lower():
        pattern_handler = logging.handlers.RotatingFileHandler(
            log_dir / "pattern_learning.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=3
        )
        pattern_handler.setLevel(logging.DEBUG)
        pattern_handler.setFormatter(detailed_formatter)
        logger.addHandler(pattern_handler)
    
    return logger

def log_batch_summary(batch_id: str, results: dict):
    """Log daily batch summary"""
    
    summary_logger = logging.getLogger("batch_summary")
    summary_logger.setLevel(logging.INFO)
    
    # Create handler if it doesn't exist
    if not summary_logger.handlers:
        handler = logging.handlers.RotatingFileHandler(
            "logs/daily_summary.log",
            maxBytes=5*1024*1024,  # 5MB
            backupCount=30  # Keep 30 days
        )
        
        formatter = logging.Formatter(
            '[%(asctime)s] BATCH_SUMMARY: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        handler.setFormatter(formatter)
        summary_logger.addHandler(handler)
    
    # Create summary message
    summary = (
        f"Batch {batch_id} - "
        f"Total: {results.get('total_urls', 0)}, "
        f"Success: {results.get('successful_count', 0)}, "
        f"Failed: {results.get('failed_count', 0)}, "
        f"Manual Review: {results.get('manual_review_count', 0)}, "
        f"Success Rate: {results.get('success_rate', 0):.1f}%, "
        f"Duration: {results.get('duration_minutes', 0):.1f}min"
    )
    
    summary_logger.info(summary)

def setup_structured_logging():
    """Setup structured logging for metrics and analytics"""
    
    # Disable some noisy third-party loggers
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)
    
    # Set root logger level
    logging.getLogger().setLevel(logging.WARNING)

# Initialize structured logging when module is imported
setup_structured_logging()