"""
Centralized JSON logging configuration.

Provides structured JSON log output compatible with Grafana/Loki/ELK.
All 553+ existing logger.info/error/etc calls work unchanged.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """JSON formatter with standardized field names."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['timestamp'] = self.formatTime(record)
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        if record.exc_info and not log_record.get('exc_info'):
            log_record['exception'] = self.formatException(record.exc_info)
        # Remove redundant fields (already mapped above)
        log_record.pop('levelname', None)
        log_record.pop('name', None)


def setup_logging(level: str = "INFO", log_dir: str = "logs") -> None:
    """
    Configure JSON structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files
    """
    formatter = CustomJsonFormatter(
        fmt='%(timestamp)s %(level)s %(logger)s %(message)s'
    )

    # Console handler (JSON to stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # File handler (JSON with rotation: 50MB per file, 5 backups)
    file_handler = RotatingFileHandler(
        f"{log_dir}/bot.log",
        maxBytes=50 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8',
    )
    file_handler.setFormatter(formatter)

    # Configure root logger
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.INFO)
