import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional


class StructuredLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "props"):
            log_data.update(record.props)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredLogFormatter())
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    def __init__(self, logger: logging.Logger, props: Optional[Dict[str, Any]] = None):
        super().__init__(logger, props or {})
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        kwargs_copy = kwargs.copy()
        if "extra" not in kwargs_copy:
            kwargs_copy["extra"] = {}
        if "props" not in kwargs_copy["extra"]:
            kwargs_copy["extra"]["props"] = {}
        
        kwargs_copy["extra"]["props"].update(self.extra)
        return msg, kwargs_copy