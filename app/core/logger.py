import logging
import re
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "foxsi.log"

# Regex patterns for sanitizing sensitive data
SENSITIVE_PATTERNS = [
    re.compile(r"(api[_-]?key[:=]\s*)([a-zA-Z0-9_\-]{8,})", re.IGNORECASE),
    re.compile(r"(password[:=]\s*)([^\s,]+)", re.IGNORECASE),
    re.compile(r"(token[:=]\s*)([a-zA-Z0-9_\-\.]{12,})", re.IGNORECASE),
    re.compile(r"(secret[:=]\s*)([^\s,]+)", re.IGNORECASE),
]


class SanitizingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.msg)
        for pattern in SENSITIVE_PATTERNS:
            msg = pattern.sub(r"\1[REDACTED]", msg)
        record.msg = msg
        return True


def setup_logger(name: str = "foxsi", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding duplicate handlers if already configured
    if not logger.handlers:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10 MB per log
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s:%(funcName)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_fmt)
        file_handler.addFilter(SanitizingFilter())
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler.setFormatter(console_fmt)
        console_handler.addFilter(SanitizingFilter())
        logger.addHandler(console_handler)

    return logger


logger = setup_logger()
