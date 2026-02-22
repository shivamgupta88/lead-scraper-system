"""Logging configuration using loguru"""

import sys
from loguru import logger
from pathlib import Path
from config.settings import settings


def setup_logger():
    """Configure loguru logger with file and console output"""

    # Remove default handler
    logger.remove()

    # Console handler with color
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True
    )

    # Ensure log directory exists
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # File handler with rotation
    logger.add(
        settings.log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="100 MB",
        retention="7 days",
        compression="zip"
    )

    # Error log file
    error_log = log_path.parent / "errors.log"
    logger.add(
        str(error_log),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="50 MB",
        retention="14 days"
    )

    logger.info("Logger initialized")
    return logger


# Initialize logger
log = setup_logger()
